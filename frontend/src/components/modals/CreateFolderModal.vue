<template>
  <BaseModal
    v-model="isOpen"
    title="Create Folder"
    size="small"
    @close="handleClose"
    @confirm="handleConfirm"
  >
    <p class="label-text">Enter folder name:</p>
    <input
      ref="inputRef"
      type="text"
      v-model="folderName"
      class="folder-input"
      placeholder="Folder name..."
    />

    <template #footer>
      <button class="btn btn-secondary" @click="handleClose">
        Cancel
      </button>
      <button class="btn btn-primary" @click="handleConfirm">
        Create
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import BaseModal from './BaseModal.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const folderName = ref('')
const inputRef = ref(null)

// Watch for modal opening to focus input
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    folderName.value = ''
    await nextTick()
    // Use setTimeout to ensure modal is fully rendered
    setTimeout(() => {
      if (inputRef.value) {
        inputRef.value.focus()
      }
    }, 100)
  }
})

function handleConfirm() {
  if (folderName.value.trim()) {
    emit('confirm', folderName.value)
    isOpen.value = false
  }
}

function handleClose() {
  emit('cancel')
  isOpen.value = false
}
</script>

<script>
import { computed } from 'vue'
export default {
  name: 'CreateFolderModal'
}
</script>

<style scoped>
.label-text {
  margin: 0 0 var(--spacing-sm) 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-base);
}

.folder-input {
  width: 100%;
  padding: var(--spacing-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-base);
}

.folder-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}
</style>
