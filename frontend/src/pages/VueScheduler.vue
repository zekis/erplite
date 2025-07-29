<template>
  <!-- Full-screen scheduler with proper background -->
  <div :class="['scheduler-page min-h-screen w-full', colors.bg.primary]">
    <SchedulerApp />
  </div>
</template>

<script setup>
import SchedulerApp from '../components/scheduler/SchedulerApp.vue'
import { useTheme } from '../components/scheduler/composables/useTheme'

// Composables
const { colors } = useTheme()
</script>
