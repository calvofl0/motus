<template>
  <div id="easy-mode">
    <div class="panes-container">
      <!-- Left Pane -->
      <FilePane pane="left" />

      <!-- Arrow Buttons -->
      <div class="arrow-buttons">
        <div class="arrow-button" :class="{ disabled: !canCopyRight }" @click="copyToRight">▶</div>
        <div class="arrow-button" :class="{ disabled: !canCopyLeft }" @click="copyToLeft">◀</div>
      </div>

      <!-- Right Pane -->
      <FilePane pane="right" />
    </div>

    <!-- Job Panel -->
    <JobPanel />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores/app'
import FilePane from '../components/FilePane.vue'
import JobPanel from '../components/JobPanel.vue'

const appStore = useAppStore()

const canCopyRight = computed(() =>
  appStore.leftPane.selectedIndexes.length > 0
)

const canCopyLeft = computed(() =>
  appStore.rightPane.selectedIndexes.length > 0
)

function copyToRight() {
  if (!canCopyRight.value) return
  // TODO: Implement copy logic
  console.log('Copy to right')
}

function copyToLeft() {
  if (!canCopyLeft.value) return
  // TODO: Implement copy logic
  console.log('Copy to left')
}
</script>

<style scoped>
#easy-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panes-container {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 0;
  padding: 15px;
  overflow: hidden;
}

.arrow-buttons {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 20px;
  padding: 0 15px;
}

.arrow-button {
  color: #28a745;
  font-size: 28px;
  cursor: pointer;
  transition: all 0.3s;
  opacity: 1;
  user-select: none;
}

.arrow-button.disabled {
  cursor: not-allowed;
  opacity: 0.3;
}

.arrow-button:not(.disabled):hover {
  transform: scale(1.2);
}
</style>
