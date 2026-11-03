<script setup lang="ts">
import DsSkin from "../components/ui/DsSkin.vue";
import Chat from "./Chat.vue";
</script>

<template>
  <DsSkin class="chat-skin">
    <Chat embedded />
  </DsSkin>
</template>

<style scoped>
.chat-skin {
  flex: 1;
  min-height: 0;
}
</style>
