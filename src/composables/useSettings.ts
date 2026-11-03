import { computed, onScopeDispose, ref } from "vue";

import * as ipc from "../lib/ipc";
import { formatBytes } from "./useData";

/** R1b：设置/人设/音色列表的状态与读写都收在这里，页面只渲染。 */
export function useSettings() {
  const personaDraft = ref<ipc.PersonaView>({ name: "", systemPrompt: "" });
  const settingsDraft = ref<ipc.SettingsView>({
    provider: "ollama",
    model: "qwen3:8b",
    privacyMode: true,
    baseUrl: "",
    hasKey: false,
    firstRunDone: false,
    ttsProvider: "cosyvoice2",
    ttsModel: "tts-1",
    ttsBaseUrl: "",
    hasTtsKey: false,
    asrProvider: "whisper",
    asrModel: "small",
    asrBaseUrl: "",
    hasAsrKey: false,
    llmCloudConsent: false,
    asrCloudConsent: false,
    ttsCloudConsent: false,
  });
  const firstRun = ref(false);
  const llmKeyDraft = ref("");
  const keyStatus = ref("");
  const ttsKeyDraft = ref("");
  const ttsKeyStatus = ref("");
  const asrKeyDraft = ref("");
  const asrKeyStatus = ref("");
  /// hello.engines 的 active_*（R2a 2.5）：设置页据此显示「实际生效」。
  const activeEngines = ref<
    Record<string, { provider: string | null; model: string | null }>
  >({});
  const voices = ref<ipc.VoiceView[]>([]);
  const voicesStatus = ref("");
  const voiceBusy = ref("");
  /** R5：克隆音色配额（样本/推理成本上限，不是许可证限制） */
  const VOICE_LIMIT = 20;
  const clonedVoiceCount = computed(
    () =>
      voices.value.filter(
        (voice) =>
          voice.id !== "builtin:default" && !voice.id.startsWith("openai:")
      ).length,
  );
  const voiceQuotaReached = computed(() => clonedVoiceCount.value >= VOICE_LIMIT);
  const profileStatus = ref("");
  const hasClonedVoice = ref(false);

  let profileRetry: number | null = null;
  let profileAttempts = 0;

  const companionName = computed(() => personaDraft.value.name.trim() || "Echoes");
  const selectedVoiceName = computed(
    () => voices.value.find((voice) => voice.selected)?.displayName ?? "内置音色",
  );
  const privacyConflict = computed(
    () =>
      settingsDraft.value.provider === "openai" &&
      settingsDraft.value.privacyMode &&
      !ipc.isLoopbackBaseUrl(settingsDraft.value.baseUrl),
  );
  const ttsPrivacyConflict = computed(
    () =>
      settingsDraft.value.ttsProvider === "openai" &&
      settingsDraft.value.privacyMode &&
      !ipc.isLoopbackBaseUrl(settingsDraft.value.ttsBaseUrl),
  );
  const asrPrivacyConflict = computed(
    () =>
      settingsDraft.value.asrProvider === "openai" &&
      settingsDraft.value.privacyMode &&
      !ipc.isLoopbackBaseUrl(settingsDraft.value.asrBaseUrl),
  );
  /** 2.11：公网端点才需要逐链同意（环回端点不出网）。 */
  const llmNeedsConsent = computed(
    () =>
      settingsDraft.value.provider === "openai" &&
      !ipc.isLoopbackBaseUrl(settingsDraft.value.baseUrl),
  );
  const asrNeedsConsent = computed(
    () =>
      settingsDraft.value.asrProvider === "openai" &&
      !ipc.isLoopbackBaseUrl(settingsDraft.value.asrBaseUrl),
  );
  const ttsNeedsConsent = computed(
    () =>
      settingsDraft.value.ttsProvider === "openai" &&
      !ipc.isLoopbackBaseUrl(settingsDraft.value.ttsBaseUrl),
  );
  const activeLlm = computed(() => activeEngines.value.llm ?? null);
  const activeTts = computed(() => activeEngines.value.tts ?? null);
  const activeAsr = computed(() => activeEngines.value.asr ?? null);
  /** 目标 vs 实际生效（2.12）：与 hello 的 active_* 不一致时标「待下一轮生效」。 */
  const ttsPending = computed(() => {
    const active = activeTts.value;
    return active !== null && active.provider !== settingsDraft.value.ttsProvider;
  });
  const asrPending = computed(() => {
    const active = activeAsr.value;
    return active !== null && active.provider !== settingsDraft.value.asrProvider;
  });
  const llmPending = computed(() => {
    const active = activeLlm.value;
    return active !== null && active.provider !== settingsDraft.value.provider;
  });

  /**
   * 三档预设（2.7）：只看 provider 组合，任一链被单独改过就是 custom。
   * - cloud：三链全云（最省本地运行时）
   * - offline：全本地
   * - hybrid：云脑 + 本地耳朵/嗓子（识别与音色不出本机）
   */
  const preset = computed<"cloud" | "offline" | "hybrid" | "custom">(() => {
    const { provider, asrProvider, ttsProvider } = settingsDraft.value;
    if (provider === "openai" && asrProvider === "openai" && ttsProvider === "openai") {
      return "cloud";
    }
    if (provider === "ollama" && asrProvider === "whisper" && ttsProvider === "cosyvoice2") {
      return "offline";
    }
    if (provider === "openai" && asrProvider === "whisper" && ttsProvider === "cosyvoice2") {
      return "hybrid";
    }
    return "custom";
  });
  const presetLabel = computed(() => {
    switch (preset.value) {
      case "cloud":
        return "云端";
      case "offline":
        return "本地";
      case "hybrid":
        return "混合";
      default:
        return "自定义";
    }
  });

  async function loadProfile(): Promise<void> {
    try {
      const [persona, settings] = await Promise.all([
        ipc.getPersona(),
        ipc.getSettings(),
      ]);
      personaDraft.value = persona;
      settingsDraft.value = settings;
      firstRun.value = !settings.firstRunDone;
      profileStatus.value = "";
      profileAttempts = 0;
    } catch (err) {
      profileAttempts += 1;
      profileStatus.value =
        profileAttempts >= 5 ? `⚠ ${String(err)}` : "等待 sidecar 初始化…";
      if (profileAttempts < 5) {
        if (profileRetry !== null) window.clearTimeout(profileRetry);
        profileRetry = window.setTimeout(() => {
          profileRetry = null;
          void loadProfile();
        }, 1500);
      }
    }
  }

  async function savePersona(): Promise<void> {
    try {
      await ipc.savePersona(personaDraft.value);
      profileStatus.value = "人设已保存（下一轮对话生效）";
    } catch (err) {
      profileStatus.value = `⚠ ${String(err)}`;
    }
  }

  async function saveSettings(): Promise<void> {
    try {
      await ipc.saveSettings(settingsDraft.value);
      profileStatus.value = "设置已保存（下一轮对话生效）";
      // 语音链换了会改变音色目录（云端预置 ↔ 本地/克隆）
      await loadVoices();
      settingsDraft.value.hasTtsKey = await ipc.hasEngineKey("tts", "openai");
      settingsDraft.value.hasAsrKey = await ipc.hasEngineKey("asr", "openai");
    } catch (err) {
      profileStatus.value = `⚠ ${String(err)}`;
    }
  }

  function onProviderChange(): void {
    const draft = settingsDraft.value;
    if (draft.provider === "openai" && !ipc.isLoopbackBaseUrl(draft.baseUrl)) {
      draft.privacyMode = false;
    }
  }

  function onTtsProviderChange(): void {
    const draft = settingsDraft.value;
    if (draft.ttsProvider === "openai" && !ipc.isLoopbackBaseUrl(draft.ttsBaseUrl)) {
      draft.privacyMode = false;
    }
  }

  function onAsrProviderChange(): void {
    const draft = settingsDraft.value;
    if (draft.asrProvider === "openai" && !ipc.isLoopbackBaseUrl(draft.asrBaseUrl)) {
      draft.privacyMode = false;
    }
    // 切回本地时把云端模型名换成 whisper 档位（否则会把 whisper-1 当档位）
    if (draft.asrProvider === "whisper" && !["tiny", "base", "small"].includes(draft.asrModel)) {
      draft.asrModel = "small";
    }
    if (draft.asrProvider === "openai" && !draft.asrModel.includes("-")) {
      draft.asrModel = "whisper-1";
    }
  }

  /** 2.7 三档预设：只切 provider（模型/端点/Key 保留用户已有配置）。 */
  function applyPreset(name: "cloud" | "offline" | "hybrid"): void {
    const draft = settingsDraft.value;
    if (name === "offline") {
      draft.provider = "ollama";
      if (!draft.model) draft.model = "qwen3:8b";
      draft.asrProvider = "whisper";
      draft.asrModel = ["tiny", "base", "small"].includes(draft.asrModel)
        ? draft.asrModel
        : "small";
      draft.ttsProvider = "cosyvoice2";
      // 全本地没有出网理由，隐私模式跟着打开
      draft.privacyMode = true;
      return;
    }
    draft.provider = "openai";
    if (name === "cloud") {
      draft.asrProvider = "openai";
      draft.asrModel = "whisper-1";
      draft.ttsProvider = "openai";
      if (!draft.ttsModel) draft.ttsModel = "tts-1";
    } else {
      draft.asrProvider = "whisper";
      draft.asrModel = ["tiny", "base", "small"].includes(draft.asrModel)
        ? draft.asrModel
        : "small";
      draft.ttsProvider = "cosyvoice2";
    }
    // 云端端点会出网：与单选切换同口径，需要关隐私模式
    draft.privacyMode = false;
  }

  /** hello 帧 → active_*（切链后 sidecar 会重发 hello，2.5）。 */
  function noteEngines(
    states: Array<{ name: string; provider?: string | null; model?: string | null }>,
  ): void {
    const next: Record<string, { provider: string | null; model: string | null }> = {};
    for (const state of states) {
      next[state.name] = {
        provider: state.provider ?? null,
        model: state.model ?? null,
      };
    }
    activeEngines.value = next;
  }

  async function saveKey(): Promise<void> {
    const key = llmKeyDraft.value.trim();
    if (!key) return;
    try {
      await ipc.saveLlmKey(key);
      llmKeyDraft.value = "";
      settingsDraft.value.hasKey = true;
      keyStatus.value = "已保存到 Windows 凭据管理器";
    } catch (err) {
      keyStatus.value = `⚠ ${String(err)}`;
    }
  }

  async function clearKey(): Promise<void> {
    try {
      await ipc.clearLlmKey();
      settingsDraft.value.hasKey = false;
      keyStatus.value = "已清除";
    } catch (err) {
      keyStatus.value = `⚠ ${String(err)}`;
    }
  }

  async function saveTtsKey(): Promise<void> {
    const key = ttsKeyDraft.value.trim();
    if (!key) return;
    try {
      await ipc.saveEngineKey("tts", "openai", key);
      ttsKeyDraft.value = "";
      settingsDraft.value.hasTtsKey = true;
      ttsKeyStatus.value = "已保存到 Windows 凭据管理器";
    } catch (err) {
      ttsKeyStatus.value = `⚠ ${String(err)}`;
    }
  }

  async function clearTtsKey(): Promise<void> {
    try {
      await ipc.clearEngineKey("tts", "openai");
      settingsDraft.value.hasTtsKey = false;
      ttsKeyStatus.value = "已清除";
    } catch (err) {
      ttsKeyStatus.value = `⚠ ${String(err)}`;
    }
  }

  async function saveAsrKey(): Promise<void> {
    const key = asrKeyDraft.value.trim();
    if (!key) return;
    try {
      await ipc.saveEngineKey("asr", "openai", key);
      asrKeyDraft.value = "";
      settingsDraft.value.hasAsrKey = true;
      asrKeyStatus.value = "已保存到 Windows 凭据管理器";
    } catch (err) {
      asrKeyStatus.value = `⚠ ${String(err)}`;
    }
  }

  async function clearAsrKey(): Promise<void> {
    try {
      await ipc.clearEngineKey("asr", "openai");
      settingsDraft.value.hasAsrKey = false;
      asrKeyStatus.value = "已清除";
    } catch (err) {
      asrKeyStatus.value = `⚠ ${String(err)}`;
    }
  }

  async function loadVoices(): Promise<void> {
    try {
      voices.value = await ipc.listVoices();
      hasClonedVoice.value = voices.value.some(
        (voice) => voice.id !== "builtin:default" && voice.status === "ready",
      );
      voicesStatus.value = "";
    } catch (err) {
      voicesStatus.value = `⚠ ${String(err)}`;
    }
  }

  // ---- R2a 2.6 / 2.10：模型目录与本地模型安装 ----
  const modelOptions = ref<ipc.LlmModelOption[]>([]);
  const modelsStatus = ref("");
  const localModels = ref<Record<string, boolean>>({});
  const localModelsStatus = ref("");
  const installingModels = ref(false);
  const installPct = ref(0);
  /** R5 模型管理：占用与删除（清单驱动；Ollama 模型只显示状态）。 */
  const modelInventory = ref<ipc.LocalModelInfo[]>([]);
  const modelInventoryStatus = ref("");
  const removingModel = ref("");

  /** 拉取 LLM 目录（Ollama 需在跑；云端需已存 key）。 */
  async function loadModels(): Promise<void> {
    const provider = settingsDraft.value.provider;
    if (provider === "mock") {
      modelOptions.value = [];
      modelsStatus.value = "mock 模式没有模型目录";
      return;
    }
    modelsStatus.value = "读取中…";
    try {
      modelOptions.value = await ipc.listLlmModels(
        provider,
        provider === "openai" ? settingsDraft.value.baseUrl : undefined,
      );
      modelsStatus.value = modelOptions.value.length
        ? `发现 ${modelOptions.value.length} 个模型`
        : "没有发现模型（Ollama 未启动或端点无目录）";
    } catch (err) {
      modelOptions.value = [];
      modelsStatus.value = `⚠ ${String(err)}`;
    }
  }

  /** 本地权重状态（whisper / bge / cosyvoice）。 */
  async function loadLocalModels(): Promise<void> {
    localModelsStatus.value = "检测中…";
    try {
      const event = await ipc.setupDetect();
      if (event.type === "detect") {
        localModels.value = event.report.models;
        const missing = event.report.missingModels;
        localModelsStatus.value =
          missing.length === 0 ? "" : `缺少 ${missing.length} 个模型`;
      }
    } catch (err) {
      localModelsStatus.value = `⚠ ${String(err)}`;
    }
  }

  /** 安装缺失的本地权重（与首启向导同一套 setup CLI，进度事件共用）。 */
  async function installLocalModels(): Promise<void> {
    if (installingModels.value) return;
    installingModels.value = true;
    installPct.value = 0;
    localModelsStatus.value = "";
    let unlisten: (() => void) | null = null;
    try {
      unlisten = await ipc.onSetupEvent((event) => {
        if (event.type === "progress") installPct.value = event.pct;
        if (event.type === "error") {
          localModelsStatus.value = `⚠ ${event.code}：${event.message}`;
        }
      });
      const result = await ipc.setupInstall("install-models");
      if (result.type === "error") {
        localModelsStatus.value = `⚠ ${result.code}：${result.message}`;
      } else {
        localModelsStatus.value = "本地模型已就绪（重启 sidecar 后加载新权重）";
      }
      await loadLocalModels();
    } catch (err) {
      localModelsStatus.value = `⚠ ${String(err)}`;
    } finally {
      unlisten?.();
      installingModels.value = false;
    }
  }

  /** R5：按清单列出本地权重 + 实际占用；迁移目录走 ECHOES_MODELS_DIR（需重启）。 */
  async function loadModelInventory(): Promise<void> {
    modelInventoryStatus.value = "读取中…";
    try {
      modelInventory.value = await ipc.modelsInfo();
      modelInventoryStatus.value = "";
    } catch (err) {
      modelInventory.value = [];
      modelInventoryStatus.value = `读取模型占用失败：${String(err)}`;
    }
  }

  /** R5：删除一个本地权重目录（Ollama 模型由 Ollama 管理，会返回错误）。 */
  async function removeModel(modelId: string): Promise<void> {
    if (removingModel.value) return;
    removingModel.value = modelId;
    modelInventoryStatus.value = "";
    try {
      const result = await ipc.modelsRemove([modelId]);
      modelInventoryStatus.value = result.removed.length
        ? `已删除 ${modelId}，释放 ${formatBytes(result.freedBytes)}`
        : `${modelId} 没有占用（可能本来就没装）`;
    } catch (err) {
      modelInventoryStatus.value = `删除失败：${String(err)}`;
    } finally {
      removingModel.value = "";
      await loadModelInventory();
      await loadLocalModels();
    }
  }

  async function chooseVoice(voiceId: string): Promise<void> {
    try {
      await ipc.selectVoice(voiceId);
      await loadVoices();
      profileStatus.value = "音色已切换（下一轮对话生效）";
    } catch (err) {
      profileStatus.value = `⚠ ${String(err)}`;
    }
  }

  /** R5：音色改名（只改显示名）。 */
  async function renameVoiceItem(voice: ipc.VoiceView): Promise<void> {
    if (voiceBusy.value) return;
    const next = window.prompt("音色新名字（只改显示名）", voice.displayName);
    if (next === null) return;
    const name = next.trim();
    if (!name || name === voice.displayName) return;
    voiceBusy.value = voice.id;
    try {
      await ipc.renameVoice(voice.id, name);
      await loadVoices();
      voicesStatus.value = "音色已改名";
    } catch (err) {
      voicesStatus.value = `改名失败：${String(err)}`;
    } finally {
      voiceBusy.value = "";
    }
  }

  /** R5：删音色——被会话绑定时后端拒绝，UI 直接显示错误。 */
  async function deleteVoiceItem(voice: ipc.VoiceView): Promise<void> {
    if (voiceBusy.value) return;
    if (
      !window.confirm(
        `删除音色「${voice.displayName}」？\n\n样本与克隆文件会一并删除；被会话使用时会拒绝。`,
      )
    ) {
      return;
    }
    voiceBusy.value = voice.id;
    try {
      await ipc.deleteVoice(voice.id);
      await loadVoices();
      voicesStatus.value = "音色已删除";
    } catch (err) {
      voicesStatus.value = `删除失败：${String(err)}`;
    } finally {
      voiceBusy.value = "";
    }
  }

  function voiceLabel(voice: ipc.VoiceView): string {
    const score =
      voice.qualityScore === null
        ? ""
        : ` · 相似度 ${Math.round(voice.qualityScore * 100)}%`;
    if (voice.id.startsWith("openai:")) {
      return "云端预置音色";
    }
    if (voice.status === "ready") {
      return (voice.id === "builtin:default" ? "内置" : "已就绪") + score;
    }
    if (voice.status === "training") {
      return "克隆中";
    }
    return voice.qualityScore === null ? "失败" : `失败${score}`;
  }

  onScopeDispose(() => {
    if (profileRetry !== null) {
      window.clearTimeout(profileRetry);
      profileRetry = null;
    }
  });

  return {
    personaDraft,
    settingsDraft,
    firstRun,
    llmKeyDraft,
    keyStatus,
    ttsKeyDraft,
    ttsKeyStatus,
    asrKeyDraft,
    asrKeyStatus,
    activeEngines,
    activeLlm,
    activeTts,
    activeAsr,
    llmPending,
    ttsPending,
    asrPending,
    preset,
    presetLabel,
    voices,
    voicesStatus,
    voiceBusy,
    VOICE_LIMIT,
    clonedVoiceCount,
    voiceQuotaReached,
    renameVoiceItem,
    deleteVoiceItem,
    profileStatus,
    hasClonedVoice,
    companionName,
    selectedVoiceName,
    privacyConflict,
    ttsPrivacyConflict,
    asrPrivacyConflict,
    llmNeedsConsent,
    asrNeedsConsent,
    ttsNeedsConsent,
    loadProfile,
    savePersona,
    saveSettings,
    onProviderChange,
    onTtsProviderChange,
    onAsrProviderChange,
    applyPreset,
    noteEngines,
    saveKey,
    clearKey,
    saveTtsKey,
    clearTtsKey,
    saveAsrKey,
    clearAsrKey,
    loadVoices,
    modelOptions,
    modelsStatus,
    localModels,
    localModelsStatus,
    installingModels,
    installPct,
    modelInventory,
    modelInventoryStatus,
    removingModel,
    loadModelInventory,
    removeModel,
    loadModels,
    loadLocalModels,
    installLocalModels,
    chooseVoice,
    voiceLabel,
  };
}

