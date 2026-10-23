//! rodio 播放线程（ADR-010）：sidecar 下行 24k mono PCM16 逐帧入队。
//!
//! - 设备与 `OutputStream` 都 !Send（cpal 约束），因此整条生命周期钉在专用线程；
//! - `flush`（PTT 按下/打断首跳）= 停旧 Sink + 建新 Sink，旧缓冲立即失效
//!   （`Sink::stop` 置 stopped，5ms 周期检查即停；重建避免复用语义歧义）；
//! - 设备不可用只记日志并退出线程：消息面/PTT 采集不因播放设备缺失而崩。

use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;

use rodio::buffer::SamplesBuffer;
use rodio::{OutputStreamBuilder, Sink};

enum AudioCommand {
    Append(Vec<i16>),
    Flush,
}

/// 播放端句柄：Clone 共享同一命令队列（Tauri State 与 WS 回调各持一份）。
#[derive(Clone)]
pub struct AudioPlayer {
    tx: Sender<AudioCommand>,
}

impl AudioPlayer {
    pub fn start() -> Self {
        let (tx, rx) = mpsc::channel();
        thread::spawn(move || run(rx));
        Self { tx }
    }

    /// 追加一帧 24k mono PCM16（空帧忽略）。
    pub fn push_pcm16(&self, pcm: &[i16]) {
        if pcm.is_empty() {
            return;
        }
        let _ = self.tx.send(AudioCommand::Append(pcm.to_vec()));
    }

    /// 打断：清空在途播放（壳侧首跳，≤100ms）。
    pub fn flush(&self) {
        let _ = self.tx.send(AudioCommand::Flush);
    }
}

fn run(rx: Receiver<AudioCommand>) {
    let mut stream = match OutputStreamBuilder::open_default_stream() {
        Ok(stream) => stream,
        Err(err) => {
            log::error!("音频输出设备不可用（播放禁用）: {err}");
            return;
        }
    };
    stream.log_on_drop(false);
    let mut sink = Sink::connect_new(stream.mixer());

    while let Ok(command) = rx.recv() {
        match command {
            AudioCommand::Append(pcm) => {
                let samples: Vec<f32> = pcm.iter().map(|&s| s as f32 / 32768.0).collect();
                sink.append(SamplesBuffer::new(1, 24_000, samples));
            }
            AudioCommand::Flush => {
                sink.stop();
                sink = Sink::connect_new(stream.mixer());
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 无设备环境下也只能验证命令队列不 panic（设备面由真机冒烟覆盖）。
    #[test]
    fn player_accepts_commands_without_blocking() {
        let player = AudioPlayer::start();
        player.push_pcm16(&[]);
        player.push_pcm16(&[0, 1, -1]);
        player.flush();
    }
}
