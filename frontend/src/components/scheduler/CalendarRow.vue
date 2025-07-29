<template>
  <div 
    ref="scrollContainer"
    class="calendar-row flex overflow-x-auto"
    :class="scrollClass"
    @scroll="handleScroll"
  >
    <div 
      v-for="dateColumn in dateColumns"
      :key="dateColumn.dateString"
      class="date-cell"
      style="width: 80px; min-width: 80px; max-width: 80px;"
      :class="[
        dateColumn.isToday ? 'bg-blue-50 dark:bg-blue-900/20' : '',
        dateColumn.isWeekend ? 'bg-blue-50 dark:bg-blue-900/30' : ''
      ]"
    >
      <slot 
        :date-column="dateColumn" 
        :date="dateColumn.dateString"
        :date-info="dateColumn"
      >
        <!-- Default slot content if no slot provided -->
        <div class="p-2 text-center text-xs">
          {{ dateColumn.dayNumber }}
        </div>
      </slot>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useScrollSync } from './composables/useScrollSync'

// Props
const props = defineProps({
  dateColumns: {
    type: Array,
    default: () => []
  },
  scrollClass: {
    type: String,
    default: 'calendar-row-scroll'
  }
})

// Refs
const scrollContainer = ref(null)

// Composables
const { registerScrollContainer, unregisterScrollContainer } = useScrollSync()

// Methods
const handleScroll = (event) => {
  // This will be handled by the useScrollSync composable
}

// Lifecycle
onMounted(() => {
  if (scrollContainer.value) {
    registerScrollContainer(scrollContainer.value, props.scrollClass)
  }
})

onUnmounted(() => {
  if (scrollContainer.value) {
    unregisterScrollContainer(scrollContainer.value)
  }
})
</script>

<style scoped>
.calendar-row {
  @apply flex-shrink-0;
}

.date-cell {
  @apply border-l border-gray-200 dark:border-gray-700;
}

.date-cell:first-child {
  @apply border-l-0;
}

/* Hide scrollbars on individual calendar rows */
.calendar-row::-webkit-scrollbar {
  display: none;
}

.calendar-row {
  -ms-overflow-style: none;  /* IE and Edge */
  scrollbar-width: none;  /* Firefox */
}
</style>
