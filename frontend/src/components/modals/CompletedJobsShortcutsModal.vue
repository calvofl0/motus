<template>
  <BaseKeyboardShortcutsModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    title="Completed Jobs - Keyboard Shortcuts"
    :sectionIds="sectionSets.completedJobs"
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
