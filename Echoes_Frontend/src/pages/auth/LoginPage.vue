<template>
  <main class="auth-container auth-login" @mousemove="handleMouseMove">
    <div class="ambient-glow"></div>
    
    <canvas ref="particleCanvas" class="particle-canvas"></canvas>

    <div class="letter-stage" :class="{ 'is-expanded': isExpanded }">
      <div class="letter-flap top">
        <div class="seal-wax">
          <span class="seal-emoji">✨</span>
        </div>
      </div>

      <div class="letter-content">
        <div class="split-layout">
          <section class="brand-side">
            <div class="brand-header">
              <span class="dot"></span>
              <span class="brand-name">{{ t("auth.brand") }}</span>
            </div>
            
            <div class="main-text">
              <h1 class="serif-title">{{ t("auth.loginHeroTitle") }}</h1>
              <p class="subtitle">{{ t("auth.loginHeroSubtitle") }}</p>
            </div>

            <div class="quote-footer">
              <p class="quote">{{ t("auth.quote") }}</p>
            </div>
          </section>

          <section class="form-side">
            <LanguageSwitcher class="lang-switcher-instance" />

            <header class="form-header">
              <h2 class="form-title">{{ t("auth.loginTitle") }}</h2>
              <p class="form-desc">{{ t("auth.loginSubtitle") }}</p>
            </header>

            <form @submit.prevent="onSubmit" class="modern-form">
              <div class="input-group">
                <input v-model="phone" type="text" required placeholder=" " />
                <label>{{ t("auth.phone") }}</label>
                <div class="focus-bar"></div>
              </div>

              <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

              <button type="submit" class="submit-btn" :disabled="userStore.loading">
                <span>{{ userStore.loading ? t("auth.loading") : t("auth.loginAction") }}</span>
                <svg class="arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                  <polyline points="12 5 19 12 12 19"></polyline>
                </svg>
              </button>
            </form>

            <div class="form-footer">
              <router-link to="/auth/register" class="link-btn">
                {{ t("auth.registerAction") }}
              </router-link>
            </div>
          </section>
        </div>
      </div>

      <div class="letter-flap bottom"></div>
    </div>
  </main>
</template>
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import LanguageSwitcher from "../../components/LanguageSwitcher.vue";
import { useRouter } from "vue-router";
import { useUserStore } from "../../store/user";

const { t } = useI18n();
const router = useRouter();
const userStore = useUserStore();
const isExpanded = ref(false);
const phone = ref("");
const errorMessage = ref("");

// --- 高性能粒子系统 ---
const particleCanvas = ref<HTMLCanvasElement | null>(null);
let ctx: CanvasRenderingContext2D | null = null;
let particles: any[] = [];
let animationId: number;

const handleMouseMove = (e: MouseEvent) => {
  if (!ctx || particles.length > 35) return;
  particles.push({
    x: e.clientX,
    y: e.clientY,
    vx: (Math.random() - 0.5) * 1.2,
    vy: (Math.random() - 0.5) * 1.2,
    size: Math.random() * 25 + 15,
    alpha: 0.5
  });
};

const animate = () => {
  if (!ctx || !particleCanvas.value) return;
  ctx.clearRect(0, 0, particleCanvas.value.width, particleCanvas.value.height);
  
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i];
    p.x += p.vx;
    p.y += p.vy;
    p.alpha -= 0.006;

    if (p.alpha <= 0) {
      particles.splice(i, 1);
      continue;
    }

    const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size);
    gradient.addColorStop(0, `rgba(241, 180, 123, ${p.alpha * 0.3})`);
    gradient.addColorStop(1, "rgba(241, 180, 123, 0)");
    
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
    ctx.fill();
  }
  animationId = requestAnimationFrame(animate);
};

const handleResize = () => {
  if (particleCanvas.value) {
    particleCanvas.value.width = window.innerWidth;
    particleCanvas.value.height = window.innerHeight;
  }
};

onMounted(() => {
  setTimeout(() => (isExpanded.value = true), 300);
  
  if (particleCanvas.value) {
    handleResize();
    ctx = particleCanvas.value.getContext("2d");
    window.addEventListener("resize", handleResize);
    animate();
  }
});

onUnmounted(() => {
  cancelAnimationFrame(animationId);
  window.removeEventListener("resize", handleResize);
});

const onSubmit = async () => {
  errorMessage.value = "";
  if (!phone.value) {
    errorMessage.value = t("auth.required");
    return;
  }
  const result = await userStore.login({ phoneNumber: phone.value });
  if (!result.data?.token) {
    errorMessage.value = result.message || result.msg || t("auth.loginFailed");
    return;
  }
  router.push("/home");
};
</script>

<style scoped>
.lang-switcher-instance {
  position: absolute;
  top: 28px;
  right: 28px;
}

@media (max-width: 900px) {
  .lang-switcher-instance {
    top: 20px;
    right: 20px;
  }
}
</style>
