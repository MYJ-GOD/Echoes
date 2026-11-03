<script setup lang="ts">
import DsButton from "./DsButton.vue";
import DsDialog from "./DsDialog.vue";

withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    description?: string;
    confirmLabel?: string;
    busy?: boolean;
    danger?: boolean;
  }>(),
  {
    description: "",
    confirmLabel: "确认",
    busy: false,
    danger: false,
  },
);

const emit = defineEmits<{ confirm: []; cancel: [] }>();
</script>

<template>
  <DsDialog
    :open="open"
    :title="title"
    :description="description"
    @close="emit('cancel')"
  >
    <slot />
    <template #footer>
      <DsButton variant="ghost" data-autofocus @click="emit('cancel')">取消</DsButton>
      <DsButton
        :variant="danger ? 'danger' : 'primary'"
        :loading="busy"
        @click="emit('confirm')"
      >
        {{ confirmLabel }}
      </DsButton>
    </template>
  </DsDialog>
</template>
