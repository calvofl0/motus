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
      <button class="modal-button modal-button-secondary" @click="handleClose">
        Cancel
      </button>
      <button class="modal-button modal-button-primary" @click="handleConfirm">
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
    if (inputRef.value) {
      inputRef.value.focus()
    }
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
  margin: 0 0 10px 0;
  color: #555;
  font-size: 14px;
}

.folder-input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.folder-input:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}

.modal-button {
  padding: 8px 20px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.modal-button-primary {
  background: #007bff;
  color: white;
}

.modal-button-primary:hover {
  background: #0056b3;
}

.modal-button-secondary {
  background: #6c757d;
  color: white;
}

.modal-button-secondary:hover {
  background: #5a6268;
}
</style>
