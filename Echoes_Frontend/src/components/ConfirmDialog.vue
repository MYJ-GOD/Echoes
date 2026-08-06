<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="visible" class="modal-overlay" @click.self="handleCancel">
        <div class="modal-content">
          <div class="modal-header">
            <h3>{{ title }}</h3>
          </div>
          <div class="modal-body">
            <p>{{ message }}</p>
          </div>
          <div class="modal-footer">
            <button class="btn-cancel" @click="handleCancel">
              {{ cancelText }}
            </button>
            <button 
              class="btn-confirm" 
              :class="{ 'btn-danger': danger }"
              @click="handleConfirm"
            >
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}>();

const emit = defineEmits<{
  confirm: [];
  cancel: [];
}>();

function handleConfirm() {
  emit('confirm');
}

function handleCancel() {
  emit('cancel');
  emit('update:visible', false);
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(45, 36, 32, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-4);
}

.modal-content {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: 0 20px 50px rgba(77, 48, 20, 0.2);
  width: 100%;
  max-width: 400px;
  overflow: hidden;
}

.modal-header {
  padding: var(--space-5) var(--space-6) var(--space-3);
}

.modal-header h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.25rem;
  color: var(--color-text);
}

.modal-body {
  padding: 0 var(--space-6) var(--space-5);
}

.modal-body p {
  margin: 0;
  color: var(--color-muted);
  line-height: 1.6;
}

.modal-footer {
  padding: var(--space-4) var(--space-6);
  background: rgba(243, 229, 216, 0.3);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

.btn-cancel,
.btn-confirm {
  padding: 10px 20px;
  border-radius: var(--radius-sm);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.btn-cancel {
  background: transparent;
  color: var(--color-muted);
  border: 1px solid var(--color-border);
}

.btn-cancel:hover {
  background: rgba(243, 229, 216, 0.5);
  color: var(--color-text);
}

.btn-confirm {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-strong));
  color: #2a1a0f;
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.2);
}

.btn-confirm:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(249, 115, 22, 0.3);
}

.btn-confirm.btn-danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: white;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
}

.btn-confirm.btn-danger:hover {
  box-shadow: 0 6px 16px rgba(239, 68, 68, 0.3);
}

/* Transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .modal-content,
.modal-leave-active .modal-content {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-content,
.modal-leave-to .modal-content {
  transform: scale(0.95);
  opacity: 0;
}
</style>

