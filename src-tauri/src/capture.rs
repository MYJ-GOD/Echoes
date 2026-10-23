//! PTT 采集重采样（§12 步骤 4）：前端 getUserMedia 48k PCM16 → 16k PCM16。
//!
//! 3:1 定比抽取 + 96 抽头 Hamming 窗低通（截止 6.96kHz）抑制 8k 以上折叠；
//! 跨 chunk 保留滤波器历史与抽取相位，分片边界不产生咔哒/相位断裂。
//! 采集设备在 WebView（getUserMedia），本模块只做纯 DSP，可在无设备环境单测。

pub const INPUT_RATE: u32 = 48_000;
pub const OUTPUT_RATE: u32 = 16_000;
const DECIMATION: usize = 3;
const TAPS: usize = 96;
/// 截止频率（cycles/sample）：0.145 × 48k ≈ 6.96kHz（16k Nyquist=8k）。
const CUTOFF: f64 = 0.145;

pub struct CaptureResampler {
    coeffs: Vec<f64>,
    /// 最近 TAPS 个输入样本（末位=当前样本）。
    history: Vec<f64>,
    phase: usize,
}

impl CaptureResampler {
    pub fn new() -> Self {
        debug_assert_eq!(
            INPUT_RATE,
            OUTPUT_RATE * DECIMATION as u32,
            "3:1 定比与采样率常量必须一致"
        );
        let mid = (TAPS - 1) as f64 / 2.0;
        let mut coeffs: Vec<f64> = (0..TAPS)
            .map(|n| {
                let x = n as f64 - mid;
                let sinc = if x.abs() < 1e-12 {
                    2.0 * CUTOFF
                } else {
                    (2.0 * std::f64::consts::PI * CUTOFF * x).sin() / (std::f64::consts::PI * x)
                };
                let window =
                    0.54 - 0.46 * (2.0 * std::f64::consts::PI * n as f64 / (TAPS - 1) as f64).cos();
                sinc * window
            })
            .collect();
        let sum: f64 = coeffs.iter().sum();
        for c in &mut coeffs {
            *c /= sum; // DC 增益归一到 1，避免语音整体衰减
        }
        Self {
            coeffs,
            history: vec![0.0; TAPS],
            phase: 0,
        }
    }

    /// 新一段 PTT 开始时清零历史（不残留上一句尾音）。
    pub fn reset(&mut self) {
        self.history.fill(0.0);
        self.phase = 0;
    }

    /// 输入 48k PCM16，输出 16k PCM16（输出长度 ≈ 输入/3）。
    pub fn push(&mut self, input: &[i16]) -> Vec<i16> {
        let mut output = Vec::with_capacity(input.len() / DECIMATION + 1);
        for &sample in input {
            self.history.rotate_left(1);
            self.history[TAPS - 1] = sample as f64;
            if self.phase == 0 {
                let filtered: f64 = self
                    .coeffs
                    .iter()
                    .zip(self.history.iter().rev())
                    .map(|(c, x)| c * x)
                    .sum();
                output.push(filtered.round().clamp(i16::MIN as f64, i16::MAX as f64) as i16);
            }
            self.phase = (self.phase + 1) % DECIMATION;
        }
        output
    }
}

impl Default for CaptureResampler {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sine(freq: f64, amplitude: f64, samples: usize) -> Vec<i16> {
        (0..samples)
            .map(|n| {
                (amplitude
                    * (2.0 * std::f64::consts::PI * freq * n as f64 / INPUT_RATE as f64).sin())
                .round() as i16
            })
            .collect()
    }

    fn rms(samples: &[i16]) -> f64 {
        let sum: f64 = samples.iter().map(|&s| (s as f64).powi(2)).sum();
        (sum / samples.len() as f64).sqrt()
    }

    #[test]
    fn output_length_is_ratio_three() {
        let mut resampler = CaptureResampler::new();
        assert_eq!(resampler.push(&vec![0; 4800]).len(), 1600);
    }

    #[test]
    fn chunk_boundaries_do_not_change_result() {
        let input = sine(1000.0, 8000.0, 4800);
        let mut whole = CaptureResampler::new();
        let expected = whole.push(&input);

        let mut split = CaptureResampler::new();
        let mut actual = split.push(&input[..1234]);
        actual.extend(split.push(&input[1234..3000]));
        actual.extend(split.push(&input[3000..]));

        assert_eq!(actual, expected);
    }

    #[test]
    fn dc_gain_is_unity_after_warmup() {
        let mut resampler = CaptureResampler::new();
        let output = resampler.push(&vec![1000; 4800]);
        let tail = &output[100..];
        assert!(tail.iter().all(|&s| (s - 1000).abs() <= 1));
    }

    #[test]
    fn speech_band_sine_passes_through() {
        let mut resampler = CaptureResampler::new();
        let output = resampler.push(&sine(1000.0, 8000.0, 24_000));
        let level = rms(&output[100..]);
        let expected = 8000.0 / 2f64.sqrt();
        assert!(
            (level - expected).abs() / expected < 0.06,
            "1kHz RMS {level:.0} 偏离 {expected:.0}"
        );
    }

    #[test]
    fn out_of_band_sine_is_attenuated() {
        let mut resampler = CaptureResampler::new();
        let output = resampler.push(&sine(12_000.0, 8000.0, 24_000));
        let level = rms(&output[100..]);
        assert!(level < 800.0, "12kHz 残余 RMS 过大: {level:.0}");
    }
}
