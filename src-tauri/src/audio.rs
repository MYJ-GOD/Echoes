//! rodio 播放线程（ADR-010）+ 三跳打断的壳侧缓冲（3.4）+ 输出设备选择（R1e）。
//!
//! 设计要点（相对"逐帧 `Sink::append`"的两处改动）：
//! - **自己持有播放缓冲**（`VecDeque<f32>`）。三跳的前提是「壳侧在途音频缓冲
//!   上限 600ms」，只有自己持有缓冲，上限才是可断言的；`Sink::append` 把队列
//!   藏在 rodio 里，既看不到长度也无法部分丢弃。
//! - **打断 = 清空缓冲**（O(1)，不必停/重建 Sink）。`Sink::stop` 之后旧 Source
//!   会被丢弃，而我们的 Source 是常驻的（空队列出静音），所以清空的就是"在途"。
//!
//! 生产侧走**背压 + 丢弃**：缓冲满时先等（真实 TTS 远快于实时，等就是在给播放
//! 让路），等不到即丢帧并记日志——「超上限即背压丢弃」（3.4 三跳前提），
//! 绝不无界堆积（否则内存与破坏性延迟一起涨）。
//!
//! 输出设备（R1e）：`cpal` 只做枚举，rodio 的 `OutputStreamBuilder::from_device`
//! 负责把选定设备接进播放。设备名是唯一标识（cpal 没有稳定 id），同名设备按第一
//! 个命中处理。设备被拔掉时回退系统默认，播放线程**不退出**——否则用户插回耳机
//! 也只能重启应用。
//!
//! 设备不可用时只记日志并保持线程存活：消息面/PTT 采集不因播放设备缺失而崩。

use std::collections::VecDeque;
use std::sync::{mpsc, Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use cpal::traits::{DeviceTrait, HostTrait};
use rodio::{OutputStream, OutputStreamBuilder, Sink, Source};
use serde::Serialize;

const SAMPLE_RATE: u32 = 24_000;
/// 壳侧在途缓冲上限（3.4 三跳前提）：600ms。
const MAX_BUFFERED_SAMPLES: usize = (SAMPLE_RATE as usize * 600) / 1000;
/// 满缓冲时的等待上限：等播放腾位（背压），超时即丢帧（丢弃语义见模块注释）。
const PUSH_WAIT: Duration = Duration::from_millis(250);
const PUSH_POLL: Duration = Duration::from_millis(5);

/// 试听音（1e.6）：440Hz、700ms、0.22 幅度、两端 10ms 淡入淡出防爆音。
const TEST_TONE_HZ: f32 = 440.0;
const TEST_TONE_MS: usize = 700;
const TEST_TONE_AMP: f32 = 0.22;

/// 播放线程命令：换设备 / 调音量。通道本身也是线程保活（句柄全 drop 即退出）。
/// 换设备的具体 name 已写进 `Shared`，命令只负责唤醒线程重建输出流。
enum Command {
    Device,
    Volume(f32),
}

/// 输出设备视图（R1e 1e.3）：`id` 与 `name` 同值，仅用于前端 `<select>` 绑定。
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OutputDevice {
    pub id: String,
    pub name: String,
    pub is_default: bool,
}

/// 枚举系统输出设备；无设备时返回空表（不是错误：音频面可继续工作）。
pub fn list_output_devices() -> Result<Vec<OutputDevice>, String> {
    let host = cpal::default_host();
    let default_name = host
        .default_output_device()
        .and_then(|device| device.name().ok());
    let devices = host
        .output_devices()
        .map_err(|err| format!("枚举输出设备失败：{err}"))?;
    let mut out: Vec<OutputDevice> = Vec::new();
    for device in devices {
        let Ok(name) = device.name() else {
            continue;
        };
        // 同名设备（HDMI 多口等）去重：cpal 没有稳定 id，重复项选了也分不清
        if out.iter().any(|item| item.id == name) {
            continue;
        }
        out.push(OutputDevice {
            is_default: default_name.as_deref() == Some(name.as_str()),
            id: name.clone(),
            name,
        });
    }
    Ok(out)
}

fn find_output_device(name: &str) -> Option<cpal::Device> {
    cpal::default_host()
        .output_devices()
        .ok()?
        .find(|device| device.name().ok().as_deref() == Some(name))
}

/// 常驻播放源：从共享队列取样本，空队列出静音（源永不结束，故 Sink 不必重建）。
struct PcmQueue {
    shared: Arc<Shared>,
}

impl Iterator for PcmQueue {
    type Item = f32;

    fn next(&mut self) -> Option<f32> {
        // 锁中毒也要继续放音（播放线程不该因为一次 panic 永久静音）
        let mut buf = match self.shared.buf.lock() {
            Ok(guard) => guard,
            Err(poisoned) => poisoned.into_inner(),
        };
        Some(buf.pop_front().unwrap_or(0.0))
    }
}

impl Source for PcmQueue {
    fn current_span_len(&self) -> Option<usize> {
        None // 长度未知：源是常驻的
    }

    fn channels(&self) -> u16 {
        1
    }

    fn sample_rate(&self) -> u32 {
        SAMPLE_RATE
    }

    fn total_duration(&self) -> Option<Duration> {
        None
    }
}

/// 缓冲是否放得下这一帧（纯函数：上限口径便于单测锁定）。
///
/// 空缓冲时无条件接收：单帧是原子的，把一帧截成半帧的代价（半句话）比短暂超上限
/// 大得多；上限因此是「600ms + 至多一帧」，仍然有界。
fn fits(buffered: usize, incoming: usize) -> bool {
    buffered == 0 || buffered + incoming <= MAX_BUFFERED_SAMPLES
}

/// 播放端句柄：Clone 共享同一缓冲（Tauri State 与 WS 回调各持一份）。
#[derive(Clone)]
pub struct AudioPlayer {
    shared: Arc<Shared>,
    commands: Arc<mpsc::Sender<Command>>,
}

struct Shared {
    buf: Mutex<VecDeque<f32>>,
    dropped_frames: Mutex<u64>,
    /// `None` = 系统默认输出设备。
    device: Mutex<Option<String>>,
    volume: Mutex<f32>,
}

impl AudioPlayer {
    pub fn start() -> Self {
        let shared = Arc::new(Shared {
            buf: Mutex::new(VecDeque::with_capacity(MAX_BUFFERED_SAMPLES)),
            dropped_frames: Mutex::new(0),
            device: Mutex::new(None),
            volume: Mutex::new(1.0),
        });
        let (tx, rx) = mpsc::channel::<Command>();
        let borrowed = Arc::clone(&shared);
        thread::spawn(move || run(borrowed, rx));
        Self {
            shared,
            commands: Arc::new(tx),
        }
    }

    /// 无播放线程的句柄（单测用）：缓冲永不腾位，背压/丢弃路径可确定性断言。
    #[cfg(test)]
    fn headless() -> Self {
        let shared = Arc::new(Shared {
            buf: Mutex::new(VecDeque::with_capacity(MAX_BUFFERED_SAMPLES)),
            dropped_frames: Mutex::new(0),
            device: Mutex::new(None),
            volume: Mutex::new(1.0),
        });
        let (tx, _rx) = mpsc::channel::<Command>();
        Self {
            shared,
            commands: Arc::new(tx),
        }
    }

    /// 切换输出设备（`None` = 系统默认）。换设备会清掉在途缓冲：旧设备上的半句话
    /// 不应在新设备上接着播。重复设置同一设备不重建流（前端每次挂载都会回放持久化值）。
    pub fn set_device(&self, device: Option<String>) {
        let previous = self.shared.device_snapshot();
        self.shared.set_device(device.clone());
        if previous == device {
            return;
        }
        self.send(Command::Device);
    }

    /// 设置播放音量（0..=1，越界钳制）。
    pub fn set_volume(&self, volume: f32) {
        let volume = if volume.is_finite() {
            volume.clamp(0.0, 1.0)
        } else {
            1.0
        };
        self.shared.set_volume(volume);
        self.send(Command::Volume(volume));
    }

    /// 追加一帧 24k mono PCM16（空帧忽略）；满缓冲先等播放腾位，等不到即丢弃。
    pub fn push_pcm16(&self, pcm: &[i16]) {
        if pcm.is_empty() {
            return;
        }
        let deadline = Instant::now() + PUSH_WAIT;
        loop {
            {
                let mut buf = self.lock_buf();
                if fits(buf.len(), pcm.len()) {
                    buf.extend(pcm.iter().map(|&s| s as f32 / 32768.0));
                    return;
                }
            }
            if Instant::now() >= deadline {
                let mut dropped = self
                    .shared
                    .dropped_frames
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner());
                *dropped += 1;
                log::warn!(
                    "播放缓冲超上限（{}ms），丢弃一帧 {} 采样（累计 {} 帧，3.4 背压丢弃）",
                    MAX_BUFFERED_SAMPLES * 1000 / SAMPLE_RATE as usize,
                    pcm.len(),
                    *dropped
                );
                return;
            }
            thread::sleep(PUSH_POLL);
        }
    }

    /// 打断（三跳首跳）：清空在途缓冲，立即静音（≤100ms 预算）。
    pub fn flush(&self) {
        self.lock_buf().clear();
    }

    /// 试听音（1e.6）：走同一条播放链，能验证「选定设备 + 音量」是否真的生效。
    pub fn play_test_tone(&self) {
        const FADE_SAMPLES: usize = SAMPLE_RATE as usize / 100; // 10ms
        let total = SAMPLE_RATE as usize * TEST_TONE_MS / 1000;
        let mut pcm = Vec::with_capacity(total);
        for i in 0..total {
            let env = if i < FADE_SAMPLES {
                i as f32 / FADE_SAMPLES as f32
            } else if i + FADE_SAMPLES > total {
                (total - i) as f32 / FADE_SAMPLES as f32
            } else {
                1.0
            };
            let phase = i as f32 * TEST_TONE_HZ * std::f32::consts::TAU / SAMPLE_RATE as f32;
            pcm.push((phase.sin() * TEST_TONE_AMP * env * 32767.0) as i16);
        }
        self.push_pcm16(&pcm);
    }

    fn send(&self, command: Command) {
        // 播放线程不在（设备初始化失败后仍会等待命令，理论上只在退出时失败）
        if self.commands.send(command).is_err() {
            log::warn!("播放线程已退出，命令丢弃");
        }
    }

    #[cfg(test)]
    fn buffered_samples(&self) -> usize {
        self.lock_buf().len()
    }

    fn lock_buf(&self) -> std::sync::MutexGuard<'_, VecDeque<f32>> {
        self.shared
            .buf
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }
}

impl Shared {
    fn device_snapshot(&self) -> Option<String> {
        self.device
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
            .clone()
    }

    fn set_device(&self, device: Option<String>) {
        *self
            .device
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner()) = device;
    }

    fn volume_snapshot(&self) -> f32 {
        *self
            .volume
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    fn set_volume(&self, volume: f32) {
        *self
            .volume
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner()) = volume;
    }
}

/// 播放线程：建流 + 常驻 Source，然后处理命令直到句柄全部 drop。
fn run(shared: Arc<Shared>, rx: mpsc::Receiver<Command>) {
    let mut output = open_output(&shared);
    while let Ok(command) = rx.recv() {
        match command {
            Command::Device => {
                // 旧设备上的在途音频不迁移：换设备等于换一条输出链
                shared
                    .buf
                    .lock()
                    .unwrap_or_else(|poisoned| poisoned.into_inner())
                    .clear();
                drop(output.take());
                output = open_output(&shared);
            }
            Command::Volume(volume) => {
                if let Some((_, sink)) = &output {
                    sink.set_volume(volume);
                }
            }
        }
    }
    drop(output);
}

/// 按当前选定设备开流；失败只记日志并返回 `None`（线程保持存活，等下一次换设备）。
fn open_output(shared: &Arc<Shared>) -> Option<(OutputStream, Sink)> {
    let mut stream = match open_stream(shared) {
        Ok(stream) => stream,
        Err(err) => {
            log::error!("音频输出设备不可用（播放禁用）: {err}");
            return None;
        }
    };
    stream.log_on_drop(false);
    let sink = Sink::connect_new(stream.mixer());
    sink.set_volume(shared.volume_snapshot());
    sink.append(PcmQueue {
        shared: Arc::clone(shared),
    });
    sink.play();
    Some((stream, sink))
}

fn open_stream(shared: &Arc<Shared>) -> Result<OutputStream, rodio::StreamError> {
    let Some(wanted) = shared.device_snapshot() else {
        return OutputStreamBuilder::open_default_stream();
    };
    let Some(device) = find_output_device(&wanted) else {
        log::warn!("输出设备「{wanted}」不在（已拔出？），回退系统默认");
        return OutputStreamBuilder::open_default_stream();
    };
    OutputStreamBuilder::from_device(device).and_then(|builder| builder.open_stream())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 无设备环境下也验证"入队即写缓冲"与"打断即清空"（设备面由真机冒烟覆盖）。
    #[test]
    fn player_buffers_then_flush_clears() {
        let player = AudioPlayer::headless();
        player.push_pcm16(&[]); // 空帧忽略
        player.push_pcm16(&[0, 1, -1]);
        assert_eq!(player.buffered_samples(), 3);
        player.flush();
        assert_eq!(player.buffered_samples(), 0);
    }

    /// 真实播放线程能起（设备缺失时只记日志），命令面不阻塞调用方。
    #[test]
    fn player_accepts_commands_without_blocking() {
        let player = AudioPlayer::start();
        player.push_pcm16(&[0, 1, -1]);
        player.flush();
        player.set_device(None);
        player.set_volume(0.5);
    }

    /// 上限口径：600ms @24k = 14400 采样；空缓冲允许整帧（帧是原子的，不截断）。
    #[test]
    fn buffer_cap_allows_lone_frame_but_bounds_accumulation() {
        assert_eq!(MAX_BUFFERED_SAMPLES, 14_400);
        assert!(fits(0, MAX_BUFFERED_SAMPLES));
        assert!(fits(MAX_BUFFERED_SAMPLES - 2, 2));
        assert!(!fits(MAX_BUFFERED_SAMPLES - 2, 3));
        assert!(fits(0, MAX_BUFFERED_SAMPLES * 3), "单帧不截断");
        assert!(!fits(1, MAX_BUFFERED_SAMPLES));
    }

    /// 满缓冲 + 无人腾位 → 走背压等待后丢弃，绝不无界堆积、也不 panic。
    #[test]
    fn push_drops_frame_when_buffer_full_and_no_drain() {
        let player = AudioPlayer::headless();
        let full = vec![0i16; MAX_BUFFERED_SAMPLES];
        player.push_pcm16(&full);
        assert_eq!(player.buffered_samples(), MAX_BUFFERED_SAMPLES);

        let started = Instant::now();
        player.push_pcm16(&[1, 2, 3]);
        assert!(started.elapsed() >= PUSH_WAIT, "满缓冲应先等播放腾位");
        assert_eq!(
            player.buffered_samples(),
            MAX_BUFFERED_SAMPLES,
            "超上限的帧被丢弃"
        );
    }

    /// 试听音长度与淡入（首采样为 0，避免爆音）。
    #[test]
    fn test_tone_is_faded_and_has_expected_length() {
        let player = AudioPlayer::headless();
        player.play_test_tone();
        assert_eq!(player.buffered_samples(), SAMPLE_RATE as usize * TEST_TONE_MS / 1000);
        let buf = player.lock_buf();
        assert_eq!(buf[0], 0.0, "淡入首采样应为 0");
        assert!(buf.iter().any(|sample| sample.abs() > 0.1), "应有可闻幅度");
    }

    /// 音量钳制：越界与 NaN 都收敛到合法区间。
    #[test]
    fn volume_is_clamped() {
        let player = AudioPlayer::headless();
        player.set_volume(2.5);
        assert_eq!(player.shared.volume_snapshot(), 1.0);
        player.set_volume(-1.0);
        assert_eq!(player.shared.volume_snapshot(), 0.0);
        player.set_volume(f32::NAN);
        assert_eq!(player.shared.volume_snapshot(), 1.0);
    }

    /// 重复设置同一设备只是写状态，不触发流重建（前端挂载时会无条件回放持久化值）。
    #[test]
    fn setting_same_device_twice_is_a_noop() {
        let player = AudioPlayer::headless();
        player.set_device(Some("扬声器".into()));
        assert_eq!(player.shared.device_snapshot().as_deref(), Some("扬声器"));
        player.set_device(Some("扬声器".into()));
        assert_eq!(player.shared.device_snapshot().as_deref(), Some("扬声器"));
        player.set_device(None);
        assert_eq!(player.shared.device_snapshot(), None);
    }

    /// 设备枚举在无声卡环境也应返回 Ok（列表可为空）。
    #[test]
    fn device_enumeration_does_not_fail_without_hardware() {
        let devices = list_output_devices().expect("枚举不应依赖具体硬件");
        assert!(devices.iter().all(|item| !item.id.is_empty()));
    }
}
