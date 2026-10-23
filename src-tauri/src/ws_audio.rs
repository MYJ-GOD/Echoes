//! 本地 WS 音频面客户端（3.4 帧格式，ADR-010 壳侧音频职责）。
//!
//! 帧格式（与 sidecar `transport/local_ws.py` 对拍）：
//! `1B 方向 | 4B seq LE | 1B flags | PCM16 payload`；方向 0x01 壳→sidecar、
//! 0x02 sidecar→壳，flags bit0 = IS_FINAL。
//!
//! 为什么自带 current-thread tokio runtime：同一 WS 连接需要全双工（上行 PTT 帧
//! 与下行 TTS 帧并行），而壳内调用点是同步的 Tauri 命令/专用线程。专用线程内
//! `block_on(select!(读, 写))` 与 Tauri runtime 解耦，也便于无 Tauri 的单测对拍。

use std::time::Duration;

use futures_util::{SinkExt, StreamExt};
use tokio::sync::mpsc;
use tokio_tungstenite::tungstenite::Message;

pub const DIR_INPUT: u8 = 0x01;
pub const DIR_OUTPUT: u8 = 0x02;
pub const FLAG_FINAL: u8 = 0x01;

/// 解析后的音频帧（payload 借用原始缓冲区）。
#[derive(Debug, PartialEq, Eq)]
pub struct AudioFrame<'a> {
    pub direction: u8,
    pub seq: u32,
    pub flags: u8,
    pub payload: &'a [u8],
}

impl AudioFrame<'_> {
    pub fn is_final(&self) -> bool {
        self.flags & FLAG_FINAL != 0
    }
}

pub fn encode_frame(direction: u8, seq: u32, flags: u8, payload: &[u8]) -> Vec<u8> {
    let mut frame = Vec::with_capacity(6 + payload.len());
    frame.push(direction);
    frame.extend_from_slice(&seq.to_le_bytes());
    frame.push(flags);
    frame.extend_from_slice(payload);
    frame
}

pub fn decode_frame(raw: &[u8]) -> Result<AudioFrame<'_>, String> {
    if raw.len() < 6 {
        return Err(format!("音频帧过短: {}B（至少 6B 帧头）", raw.len()));
    }
    Ok(AudioFrame {
        direction: raw[0],
        seq: u32::from_le_bytes([raw[1], raw[2], raw[3], raw[4]]),
        flags: raw[5],
        payload: &raw[6..],
    })
}

/// PCM16 采样 → 小端字节流（WS payload 口径）。
pub fn pcm16_le(samples: &[i16]) -> Vec<u8> {
    samples.iter().flat_map(|s| s.to_le_bytes()).collect()
}

/// 小端字节流 → PCM16 采样（丢弃不足 2B 的尾巴）。
pub fn pcm16_from_le(payload: &[u8]) -> Vec<i16> {
    payload
        .chunks_exact(2)
        .map(|b| i16::from_le_bytes([b[0], b[1]]))
        .collect()
}

struct InputChunk {
    pcm: Vec<u8>,
    is_final: bool,
}

/// 壳→sidecar 音频上行端；克隆共享同一连接与 seq 序列。
#[derive(Clone)]
pub struct WsAudioClient {
    tx: mpsc::UnboundedSender<InputChunk>,
}

impl WsAudioClient {
    /// 连接 sidecar 的 WS 音频面；输出帧回调在 WS 线程上执行（实现必须快速返回）。
    /// 连接失败重试 5s（端口由 stderr 解析，正常时序下首连即成功）。
    pub fn connect(port: u16, on_output: impl FnMut(Vec<i16>) + Send + 'static) -> Self {
        let (tx, rx) = mpsc::unbounded_channel();
        std::thread::spawn(move || {
            let runtime = match tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
            {
                Ok(rt) => rt,
                Err(err) => {
                    log::error!("WS 音频运行时创建失败: {err}");
                    return;
                }
            };
            runtime.block_on(run(port, rx, on_output));
        });
        Self { tx }
    }

    /// 上行一段 PCM16（16k mono，已按 3 字节帧头在 WS 线程封装）。
    pub fn send_input(&self, pcm16_le: Vec<u8>, is_final: bool) {
        let _ = self.tx.send(InputChunk {
            pcm: pcm16_le,
            is_final,
        });
    }
}

async fn run(
    port: u16,
    mut rx: mpsc::UnboundedReceiver<InputChunk>,
    mut on_output: impl FnMut(Vec<i16>),
) {
    let url = format!("ws://127.0.0.1:{port}");
    let mut connected = None;
    for attempt in 1..=50 {
        match tokio_tungstenite::connect_async(&url).await {
            Ok((stream, _response)) => {
                connected = Some(stream);
                break;
            }
            Err(err) if attempt < 50 => {
                if attempt == 1 {
                    log::info!("WS 音频面连接中 {url}: {err}");
                }
                tokio::time::sleep(Duration::from_millis(100)).await;
            }
            Err(err) => {
                log::error!("WS 音频面连接失败 {url}: {err}");
                return;
            }
        }
    }
    let Some(ws) = connected else { return };
    log::info!("WS 音频面已连接 {url}");
    let (mut sink, mut stream) = ws.split();
    let mut seq: u32 = 0;

    loop {
        tokio::select! {
            outbound = rx.recv() => {
                let Some(chunk) = outbound else { break; }; // 壳退出
                let flags = if chunk.is_final { FLAG_FINAL } else { 0 };
                let frame = encode_frame(DIR_INPUT, seq, flags, &chunk.pcm);
                seq = seq.wrapping_add(1);
                if let Err(err) = sink.send(Message::Binary(frame.into())).await {
                    log::error!("WS 音频发送失败: {err}");
                    break;
                }
            }
            inbound = stream.next() => {
                match inbound {
                    Some(Ok(Message::Binary(data))) => match decode_frame(&data) {
                        Ok(frame) if frame.direction == DIR_OUTPUT => {
                            if frame.is_final() {
                                log::debug!("TTS 末帧 seq={}", frame.seq);
                            }
                            on_output(pcm16_from_le(frame.payload));
                        }
                        Ok(frame) => log::warn!(
                            "WS 音频帧方向异常已忽略: 0x{:02x} seq={}",
                            frame.direction, frame.seq
                        ),
                        Err(err) => log::warn!("WS 音频帧畸形已忽略: {err}"),
                    },
                    Some(Ok(Message::Close(_))) | None => break,
                    Some(Ok(_)) => {}
                    Some(Err(err)) => {
                        log::error!("WS 音频接收失败: {err}");
                        break;
                    }
                }
            }
        }
    }
    log::info!("WS 音频面已断开");
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc as std_mpsc;

    #[test]
    fn frame_roundtrip_preserves_header_and_payload() {
        let raw = encode_frame(DIR_INPUT, 7, FLAG_FINAL, &[1, 2, 3, 4]);
        let frame = decode_frame(&raw).expect("合法帧");
        assert_eq!(frame.direction, DIR_INPUT);
        assert_eq!(frame.seq, 7);
        assert!(frame.is_final());
        assert_eq!(frame.payload, &[1, 2, 3, 4]);
    }

    #[test]
    fn frame_rejects_short_header() {
        assert!(decode_frame(&[0x01, 0, 0]).is_err());
    }

    #[test]
    fn pcm16_le_roundtrip() {
        let samples = [0i16, 1, -1, i16::MIN, i16::MAX];
        assert_eq!(pcm16_from_le(&pcm16_le(&samples)), samples);
        assert_eq!(pcm16_from_le(&[0x01, 0x00, 0x02]), vec![1]); // 尾巴丢弃
    }

    /// 端到端对拍：mock WS server 收上行帧（方向/seq/flags/payload），回一帧下行，
    /// 客户端回调拿到 PCM16 —— 锁住全双工线程与 seq 单调口径。
    #[test]
    fn client_sends_frames_and_delivers_output() {
        let (port_tx, port_rx) = std_mpsc::channel::<u16>();
        let server = std::thread::spawn(move || {
            let runtime = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .expect("runtime");
            runtime.block_on(async move {
                let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
                    .await
                    .expect("bind");
                port_tx
                    .send(listener.local_addr().expect("addr").port())
                    .expect("port");
                let (tcp, _) = listener.accept().await.expect("accept");
                let mut ws = tokio_tungstenite::accept_async(tcp).await.expect("ws 握手");

                let first = ws.next().await.expect("上行帧 1").expect("合法帧 1");
                let Message::Binary(first) = first else {
                    panic!("上行帧应为 binary");
                };
                let first = decode_frame(&first).expect("解析帧 1");
                assert_eq!(first.direction, DIR_INPUT);
                assert_eq!(first.seq, 0);
                assert!(!first.is_final());
                assert_eq!(first.payload, &[1, 0, 2, 0]);

                ws.send(Message::Binary(
                    encode_frame(DIR_OUTPUT, 0, FLAG_FINAL, &[9, 0, 8, 0]).into(),
                ))
                .await
                .expect("下行帧");

                let last = ws.next().await.expect("上行帧 2").expect("合法帧 2");
                let Message::Binary(last) = last else {
                    panic!("上行帧应为 binary");
                };
                let last = decode_frame(&last).expect("解析帧 2");
                assert_eq!(last.seq, 1);
                assert!(last.is_final());
                assert!(last.payload.is_empty());
            });
        });

        let port = port_rx
            .recv_timeout(Duration::from_secs(5))
            .expect("server port");
        let (out_tx, out_rx) = std_mpsc::channel::<Vec<i16>>();
        let client = WsAudioClient::connect(port, move |pcm| {
            let _ = out_tx.send(pcm);
        });
        client.send_input(pcm16_le(&[1, 2]), false);
        client.send_input(Vec::new(), true);

        let pcm = out_rx
            .recv_timeout(Duration::from_secs(10))
            .expect("下行音频回调");
        assert_eq!(pcm, vec![9, 8]);
        server.join().expect("server");
    }
}
