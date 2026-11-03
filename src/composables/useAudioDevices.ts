/**
 * R1e 音频设备（1e.1 / 1e.2 / 1e.6）：
 * - 输入设备走 WebView2 的 `enumerateDevices`（Rust 只管 DSP，不碰采集）；
 * - deviceId 存 localStorage：设备级设置不跨机器同步，也不需要进 DB；
 * - 输出枚举/切换/音量是壳侧（cpal + rodio），这里只做调用与持久化；
 * - 麦克风电平试听：临时开流 + AnalyserNode 算 RMS，关掉即释放。
 */
import { onUnmounted, ref } from "vue";

import * as ipc from "../lib/ipc";
import type { OutputDevice } from "../lib/ipc";

const INPUT_KEY = "echoes.audio.inputDevice";
const OUTPUT_KEY = "echoes.audio.outputDevice";
const VOLUME_KEY = "echoes.audio.volume";

function readStored(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function writeStored(key: string, value: string): void {
  try {
    if (value === "") localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // 隐私模式/存储被禁用：只在本次会话生效
  }
}

function readVolume(): number {
  const raw = Number.parseFloat(readStored(VOLUME_KEY));
  return Number.isFinite(raw) ? Math.min(1, Math.max(0, raw)) : 1;
}

export function useAudioDevices() {
  const inputDevices = ref<MediaDeviceInfo[]>([]);
  const outputDevices = ref<OutputDevice[]>([]);
  const inputDeviceId = ref(readStored(INPUT_KEY));
  const outputDeviceName = ref(readStored(OUTPUT_KEY));
  const volume = ref(readVolume());
  const micLevel = ref(0);
  const previewing = ref(false);
  const status = ref("");

  let previewStream: MediaStream | null = null;
  let previewCtx: AudioContext | null = null;
  let previewRaf: number | null = null;

  function stopPreview(): void {
    previewing.value = false;
    micLevel.value = 0;
    if (previewRaf !== null) {
      window.cancelAnimationFrame(previewRaf);
      previewRaf = null;
    }
    previewStream?.getTracks().forEach((track) => track.stop());
    previewStream = null;
    if (previewCtx) {
      void previewCtx.close().catch(() => undefined);
      previewCtx = null;
    }
  }

  /** 采集约束：只在选中的设备仍在列表里时用 exact，避免拔设备后直接 Overconstrained。 */
  function audioConstraints(): MediaTrackConstraints {
    const base: MediaTrackConstraints = {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    };
    const selected = inputDeviceId.value;
    if (selected && inputDevices.value.some((item) => item.deviceId === selected)) {
      base.deviceId = { exact: selected };
    }
    return base;
  }

  /** 打开麦克风（PTT / 试听共用）；选定设备失效时清掉持久化并回退系统默认。 */
  async function openMicStream(): Promise<MediaStream> {
    try {
      return await navigator.mediaDevices.getUserMedia({ audio: audioConstraints() });
    } catch (err) {
      if (!inputDeviceId.value) throw err;
      inputDeviceId.value = "";
      writeStored(INPUT_KEY, "");
      status.value = "选定的麦克风不可用，已回退系统默认（可重新选择）";
      void refreshDevices();
      return navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
    }
  }

  async function refreshDevices(): Promise<void> {
    status.value = "";
    if (!navigator.mediaDevices?.enumerateDevices) {
      status.value = "当前环境不支持设备枚举（浏览器预览下正常）";
      return;
    }
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      inputDevices.value = all.filter((item) => item.kind === "audioinput");
      if (
        inputDeviceId.value &&
        !inputDevices.value.some((item) => item.deviceId === inputDeviceId.value)
      ) {
        inputDeviceId.value = "";
        writeStored(INPUT_KEY, "");
      }
    } catch (err) {
      status.value = `枚举输入设备失败：${String(err)}`;
    }
    try {
      outputDevices.value = await ipc.listOutputDevices();
      if (
        outputDeviceName.value &&
        !outputDevices.value.some((item) => item.id === outputDeviceName.value)
      ) {
        outputDeviceName.value = "";
        writeStored(OUTPUT_KEY, "");
      }
    } catch (err) {
      status.value = `枚举输出设备失败：${String(err)}`;
    }
  }

  function selectInput(deviceId: string): void {
    inputDeviceId.value = deviceId;
    writeStored(INPUT_KEY, deviceId);
    status.value = "";
    if (previewing.value) {
      // 换设备要重新协商流，旧流不会自动切过去
      stopPreview();
      void togglePreview();
    }
  }

  async function applyOutputDevice(): Promise<void> {
    try {
      await ipc.setOutputDevice(outputDeviceName.value || null);
    } catch (err) {
      status.value = `切换输出设备失败：${String(err)}`;
    }
  }

  function selectOutput(deviceId: string): void {
    outputDeviceName.value = deviceId;
    writeStored(OUTPUT_KEY, deviceId);
    void applyOutputDevice();
  }

  async function applyVolume(): Promise<void> {
    writeStored(VOLUME_KEY, String(volume.value));
    try {
      await ipc.setVolume(volume.value);
    } catch (err) {
      status.value = `设置音量失败：${String(err)}`;
    }
  }

  async function testOutput(): Promise<void> {
    try {
      await ipc.playTestTone();
    } catch (err) {
      status.value = `试听失败：${String(err)}`;
    }
  }

  async function togglePreview(): Promise<void> {
    if (previewing.value) {
      stopPreview();
      return;
    }
    status.value = "";
    try {
      const stream = await openMicStream();
      const ctx = new AudioContext();
      await ctx.resume();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const samples = new Float32Array(analyser.fftSize);
      previewStream = stream;
      previewCtx = ctx;
      previewing.value = true;
      const tick = () => {
        analyser.getFloatTimeDomainData(samples);
        let sum = 0;
        for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
        // ×4 让正常说话音量落在条子中段；开方前先钳制，避免爆表
        micLevel.value = Math.min(1, Math.sqrt(sum / samples.length) * 4);
        previewRaf = window.requestAnimationFrame(tick);
      };
      tick();
      // 拿到权限后 label 才可读，刷新一次列表
      void refreshDevices();
    } catch (err) {
      stopPreview();
      status.value = `无法试听麦克风：${String(err)}`;
    }
  }

  /** 设备热插拔：插上耳机后设置页要能立刻选到（判据 2）。 */
  const onDeviceChange = () => void refreshDevices();
  navigator.mediaDevices?.addEventListener?.("devicechange", onDeviceChange);

  onUnmounted(() => {
    navigator.mediaDevices?.removeEventListener?.("devicechange", onDeviceChange);
    stopPreview();
  });

  return {
    inputDevices,
    outputDevices,
    inputDeviceId,
    outputDeviceName,
    volume,
    micLevel,
    previewing,
    status,
    refreshDevices,
    selectInput,
    selectOutput,
    applyOutputDevice,
    applyVolume,
    testOutput,
    togglePreview,
    openMicStream,
  };
}
