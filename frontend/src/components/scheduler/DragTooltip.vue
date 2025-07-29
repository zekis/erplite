<template>
  <div 
    v-if="isVisible" 
    class="drag-tooltip fixed z-50 pointer-events-none"
    :style="{ left: position.x + 'px', top: position.y + 'px' }"
  >
    <div :class="[
      'tooltip-content bg-gray-900 text-white px-3 py-2 rounded-lg shadow-xl text-sm font-medium',
      'border border-gray-700'
    ]">
      <!-- Date Range -->
      <div class="tooltip-dates flex items-center space-x-2">
        <Icon icon="lucide:calendar" class="w-4 h-4 text-blue-400" />
        <span>{{ formatDateRange() }}</span>
      </div>
      
      <!-- Duration -->
      <div class="tooltip-duration flex items-center space-x-2 mt-1">
        <Icon icon="lucide:clock" class="w-4 h-4 text-green-400" />
        <span>{{ formatDuration() }}</span>
      </div>
      
      <!-- Arrow pointing to selection -->
      <div class="tooltip-arrow absolute -bottom-1 left-1/2 transform -translate-x-1/2">
        <div class="w-2 h-2 bg-gray-900 border-r border-b border-gray-700 transform rotate-45"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { format, parseISO } from 'date-fns'
import { Icon } from '@iconify/vue'

// Props
const props = defineProps({
  isVisible: {
    type: Boolean,
    default: false
  },
  position: {
    type: Object,
    default: () => ({ x: 0, y: 0 })
  },
  selectedDates: {
    type: Array,
    default: () => []
  }
})

// Computed
const formatDateRange = () => {
  if (!props.selectedDates.length) return 'No dates selected'
  
  if (props.selectedDates.length === 1) {
    return format(parseISO(props.selectedDates[0]), 'MMM d, yyyy')
  }
  
  const sortedDates = [...props.selectedDates].sort()
  const startDate = format(parseISO(sortedDates[0]), 'MMM d')
  const endDate = format(parseISO(sortedDates[sortedDates.length - 1]), 'MMM d, yyyy')
  
  return `${startDate} - ${endDate}`
}

const formatDuration = () => {
  const count = props.selectedDates.length
  if (count === 0) return '0 days'
  if (count === 1) return '1 day'
  return `${count} days`
}
</script>

<style scoped>
.drag-tooltip {
  animation: tooltipFadeIn 0.2s ease-out;
  transform: translateY(-10px);
}

.tooltip-content {
  backdrop-filter: blur(8px);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
}

.tooltip-arrow {
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
}

@keyframes tooltipFadeIn {
  from {
    opacity: 0;
    transform: translateY(-5px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(-10px) scale(1);
  }
}
</style>
