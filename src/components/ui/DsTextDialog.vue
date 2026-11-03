<script setup lang="ts">
import DsButton from "./DsButton.vue";
import DsDialog from "./DsDialog.vue";
import DsField from "./DsField.vue";
import DsTextarea from "./DsTextarea.vue";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    description?: string;
    label?: string;
    placeholder?: string;
    rows?: number;
    confirmLabel?: string;
    busy?: boolean;
    error?: string;
    maxlength?: number;
  }>(),
  {
    description: "",
    label: "内容",
    placeholder: "",
    rows: 4,
    confirmLabel: "保存",
    busy: false,
    error: "",
    maxlength: 4000,
  },
);

const emit = defineEmits<{ confirm: []; cancel: [] }>();
const text = defineModel<string>({ default: "" });

function onKeydown(event: KeyboardEvent): void {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    if (!props.busy) emit("confirm");
  }
}
</script>

<template>
  <DsDialog
    :open="open"
    :title="title"
    :description="description"
    size="md"
    @close="emit('cancel')"
  >
    <DsField :label="label">
      <DsTextarea
        v-model="text"
        :rows="rows"
        :placeholder="placeholder"
        :maxlength="maxlength"
        data-autofocus
        @keydown="onKeydown"
      />
    </DsField>
    <p v-if="error" class="ds-text-dialog__error" role="alert">{{ error }}</p>

    <template #footer>
      <DsButton variant="ghost" @click="emit('cancel')">取消</DsButton>
      <DsButton variant="primary" :loading="busy" @click="emit('confirm')">
        {{ confirmLabel }}
      </DsButton>
    </template>
  </DsDialog>
</template>

<style scoped>
.ds-text-dialog__error {
  margin-top: var(--space-2);
  color: var(--danger);
  font-size: 12px;
  line-height: 18px;
}
</style>
