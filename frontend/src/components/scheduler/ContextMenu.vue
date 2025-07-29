<template>
  <div 
    v-show="isVisible" 
    class="context-menu fixed"
    :style="{ left: position.x + 'px', top: position.y + 'px', zIndex: 9999 }"
    @click.stop
  >
    <div class="context-menu-content bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 min-w-48">
      <!-- Create Shift Option -->
      <button
        @click="handleCreateShift"
        class="menu-item w-full flex items-center px-4 py-3 text-left transition-colors text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700 first:rounded-t-lg last:rounded-b-lg"
      >
        <Icon icon="lucide:clock" class="w-4 h-4 mr-3 flex-shrink-0 text-blue-500" />
        <div class="flex-1">
          <div class="text-sm font-medium">Create Shift</div>
          <div class="text-xs text-gray-600 dark:text-gray-300">
            {{ selectedDates.length }} day{{ selectedDates.length > 1 ? 's' : '' }} selected
          </div>
        </div>
      </button>

      <!-- Divider -->
      <div class="border-t border-gray-300 dark:border-gray-600"></div>

      <!-- Quick Templates -->
      <button
        @click="handleQuickTemplate('8h')"
        class="menu-item w-full flex items-center px-4 py-2 text-left transition-colors text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700"
      >
        <Icon icon="lucide:sun" class="w-4 h-4 mr-3 flex-shrink-0 text-orange-500" />
        <span class="text-sm">8h Day Shift (9:00-17:00)</span>
      </button>

      <button
        @click="handleQuickTemplate('12h')"
        class="menu-item w-full flex items-center px-4 py-2 text-left transition-colors text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700"
      >
        <Icon icon="lucide:moon" class="w-4 h-4 mr-3 flex-shrink-0 text-indigo-500" />
        <span class="text-sm">12h Shift (7:00-19:00)</span>
      </button>

      <button
        @click="handleQuickTemplate('night')"
        class="menu-item w-full flex items-center px-4 py-2 text-left transition-colors text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700"
      >
        <Icon icon="lucide:moon-star" class="w-4 h-4 mr-3 flex-shrink-0 text-purple-500" />
        <span class="text-sm">Night Shift (22:00-06:00)</span>
      </button>

      <!-- Divider -->
      <div class="border-t border-gray-300 dark:border-gray-600"></div>

      <!-- Leave Option -->
      <button
        @click="handleQuickTemplate('leave')"
        class="menu-item w-full flex items-center px-4 py-2 text-left transition-colors text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700 last:rounded-b-lg"
      >
        <Icon icon="lucide:calendar-x" class="w-4 h-4 mr-3 flex-shrink-0 text-red-500" />
        <span class="text-sm">Mark as Leave</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { watch, computed } from 'vue'
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
  },
  rowData: {
    type: Object,
    default: () => ({})
  }
})

// Computed property to ensure we have a real array
const shouldShow = computed(() => {
  const hasValidDates = props.selectedDates && Array.isArray(props.selectedDates) && props.selectedDates.length > 0
  console.log('🎯 ContextMenu shouldShow computed:', {
    isVisible: props.isVisible,
    hasValidDates,
    selectedDatesLength: props.selectedDates?.length,
    selectedDatesType: typeof props.selectedDates,
    isArray: Array.isArray(props.selectedDates)
  })
  return props.isVisible && hasValidDates
})

// Debug watcher - clean version
watch(() => props.isVisible, (newVal) => {
  if (newVal) {
    console.log('🎯 Step 6 - ContextMenu became visible with props:', {
      isVisible: props.isVisible,
      selectedDates: props.selectedDates,
      selectedDatesLength: props.selectedDates?.length,
      position: props.position,
      positionX: props.position?.x,
      positionY: props.position?.y,
      windowWidth: window.innerWidth,
      windowHeight: window.innerHeight
    })
  }
})

// Emits
const emit = defineEmits(['create-shift', 'quick-template', 'close'])

// Methods
const handleCreateShift = () => {
  emit('create-shift')
  emit('close')
}

const handleQuickTemplate = (template) => {
  const templateData = getTemplateData(template)
  emit('quick-template', {
    dates: props.selectedDates,
    template: templateData,
    rowData: props.rowData
  })
  emit('close')
}

const getTemplateData = (template) => {
  const templates = {
    '8h': {
      startTime: '09:00',
      endTime: '17:00',
      hours: 8,
      notes: '8 hour day shift',
      isNightShift: false
    },
    '12h': {
      startTime: '07:00',
      endTime: '19:00',
      hours: 12,
      notes: '12 hour shift',
      isNightShift: false
    },
    'night': {
      startTime: '22:00',
      endTime: '06:00',
      hours: 8,
      notes: 'Night shift',
      isNightShift: true
    },
    'leave': {
      startTime: '00:00',
      endTime: '23:59',
      hours: 8,
      notes: 'Leave day',
      isNightShift: false,
      isLeave: true
    }
  }
  
  return templates[template] || templates['8h']
}
</script>

<style scoped>
.context-menu {
  animation: contextMenuIn 0.15s ease-out;
}

.context-menu-content {
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
}

.menu-item {
  @apply transition-all duration-150;
}

.menu-item:hover {
  @apply scale-[1.02];
}

.menu-item:active {
  @apply scale-[0.98];
}

@keyframes contextMenuIn {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(-5px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
