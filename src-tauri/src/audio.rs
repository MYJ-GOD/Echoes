//! rodio 播放线程（ADR-010）+ 三跳打断的壳侧缓冲（3.4）。
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
//! 设备不可用只记日志并退出线程：消息面/PTT 采集不因播放设备缺失而崩。

use std::collections::VecDeque;
use std::sync::{mpsc, Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use rodio::{OutputStreamBuilder, Sink, Source};

const SAMPLE_RATE: u32 = 24_000;
/// 壳侧在途缓冲上限（3.4 三跳前提）：600ms。
const MAX_BUFFERED_SAMPLES: usize = (SAMPLE_RATE as usize * 600) / 1000;
/// 满缓冲时的等待上限：等播放腾位（背压），超时即丢帧（丢弃语义见模块注释）。
const PUSH_WAIT: Duration = Duration::from_millis(250);
const PUSH_POLL: Duration = Duration::from_millis(5);

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
    _keepalive: Arc<mpsc::Sender<()>>,
}

struct Shared {
    buf: Mutex<VecDeque<f32>>,
    dropped_frames: Mutex<u64>,
}

impl AudioPlayer {
    pub fn start() -> Self {
        let shared = Arc::new(Shared {
            buf: Mutex::new(VecDeque::with_capacity(MAX_BUFFERED_SAMPLES)),
            dropped_frames: Mutex::new(0),
        });
        let (tx, rx) = mpsc::channel::<()>();
        let borrowed = Arc::clone(&shared);
        thread::spawn(move || run(borrowed, rx));
        Self {
            shared,
            _keepalive: Arc::new(tx),
        }
    }

    /// 无播放线程的句柄（单测用）：缓冲永不腾位，背压/丢弃路径可确定性断言。
    #[cfg(test)]
    fn headless() -> Self {
        let shared = Arc::new(Shared {
            buf: Mutex::new(VecDeque::with_capacity(MAX_BUFFERED_SAMPLES)),
            dropped_frames: Mutex::new(0),
        });
        let (tx, _rx) = mpsc::channel::<()>();
        Self {
            shared,
            _keepalive: Arc::new(tx),
        }
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

/// 播放线程：建流 + 常驻 Source，然后等句柄全部 drop（stream/sink 必须活到最后）。
fn run(shared: Arc<Shared>, rx: mpsc::Receiver<()>) {
    let mut stream = match OutputStreamBuilder::open_default_stream() {
        Ok(stream) => stream,
        Err(err) => {
            log::error!("音频输出设备不可用（播放禁用）: {err}");
            return;
        }
    };
    stream.log_on_drop(false);
    let sink = Sink::connect_new(stream.mixer());
    sink.append(PcmQueue {
        shared: Arc::clone(&shared),
    });
    sink.play();
    while rx.recv().is_ok() {}
    drop(sink);
    drop(stream);
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
}
