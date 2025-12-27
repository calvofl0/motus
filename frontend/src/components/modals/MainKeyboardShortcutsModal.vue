<template>
  <BaseKeyboardShortcutsModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    title="Keyboard Shortcuts"
    :sectionIds="sectionSets.main"
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
