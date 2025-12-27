<template>
  <BaseKeyboardShortcutsModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    title="Manage Remotes - Keyboard Shortcuts"
    :sectionIds="sectionSets.manageRemotes"
  />
</template>

<script setup>
import BaseKeyboardShortcutsModal from './BaseKeyboardShortcutsModal.vue'
import { sectionSets } from '../../data/shortcutSections'

defineProps({
  modelValue: {
    type: Boolean,
    required: true
  }
})

defineEmits(['update:modelValue'])
</script>
