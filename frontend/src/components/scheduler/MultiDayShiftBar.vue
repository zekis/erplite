<template>
  <div 
    :class="[
      'multi-day-shift-bar absolute flex items-center cursor-pointer transition-all duration-200',
      'rounded-lg shadow-sm border-2',
      shiftTypeClasses,
      isDragging ? 'opacity-50 scale-95 z-50' : 'z-0',
      isSelected ? 'ring-2 ring-blue-400 ring-offset-1' : '',
      'hover:shadow-md hover:scale-[1.02] hover:z-20',
      'opacity-60 hover:opacity-80'
    ]"
    :style="barStyle"
    :draggable="true"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
    @click="handleClick"
    :title="tooltipText"
  >
    <!-- Bar Content -->
    <div class="flex-1 flex items-center justify-between px-3 py-1 min-w-0">
      <!-- Left: Time and Duration -->
      <div class="flex items-center space-x-2 min-w-0">
        <div :class="[
          'text-sm font-semibold truncate',
          isNightShift ? 'text-purple-100' : 'text-gray-800'
        ]">
          {{ formatTimeRange(shift.start_time, shift.end_time) }}
        </div>
        <div :class="[
          'text-xs opacity-80',
          isNightShift ? 'text-purple-200' : 'text-gray-600'
        ]">
          {{ formatDuration(shift.hours) }}
        </div>
      </div>

      <!-- Right: Icons and Indicators -->
      <div class="flex items-center space-x-1 ml-2">
        <!-- Note Icon -->
        <button
          v-if="shift.notes || shift.description"
          @click.stop="handleShowNotes"
          :class="[
            'p-1 rounded-full transition-all duration-200 hover:scale-110',
            isNightShift 
              ? 'text-purple-200 hover:bg-purple-700/30' 
              : 'text-gray-600 hover:bg-gray-200'
          ]"
          title="View notes"
        >
          <Icon icon="lucide:sticky-note" class="w-3 h-3" />
        </button>
        
        <!-- Multi-day indicator -->
        <div 
          :class="[
            'text-xs px-1.5 py-0.5 rounded-full font-medium',
            isNightShift 
              ? 'bg-purple-700/50 text-purple-100' 
              : 'bg-gray-200 text-gray-700'
          ]"
        >
          {{ dayCount }}d
        </div>

        <!-- Avatar/Resource indicator -->
        <div 
          v-if="shift.resource_name"
          :class="[
            'w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium',
            isNightShift 
              ? 'bg-purple-600 text-purple-100' 
              : 'bg-blue-500 text-white'
          ]"
          :title="shift.resource_name"
        >
          {{ getResourceInitials(shift.resource_name) }}
        </div>
      </div>
    </div>

    <!-- Shift Type Indicator (left edge) -->
    <div 
      :class="[
        'absolute left-0 top-0 bottom-0 w-1 rounded-l-lg',
        shiftIndicatorColor
      ]"
    />

    <!-- Project Color Indicator (right edge) -->
    <div 
      v-if="projectColor && projectColor !== '#6b7280'"
      :class="[
        'absolute right-0 top-0 bottom-0 w-1 rounded-r-lg'
      ]"
      :style="{ backgroundColor: projectColor }"
    />

    <!-- Hover Actions Overlay -->
    <div :class="[
      'absolute inset-0 flex items-center justify-center space-x-2',
      'opacity-0 hover:opacity-100 transition-all duration-200',
      'bg-black bg-opacity-60 rounded-lg backdrop-blur-sm'
    ]">
      <button
        :class="[
          'p-2 rounded-full transition-all duration-200',
          'bg-white bg-opacity-20 hover:bg-opacity-40',
          'text-white hover:scale-110'
        ]"
        @click.stop="handleEdit"
        title="Edit shift"
      >
        <Icon icon="lucide:edit-3" class="w-4 h-4" />
      </button>
      
      <button
        :class="[
          'p-2 rounded-full transition-all duration-200',
          'bg-white bg-opacity-20 hover:bg-opacity-40',
          'text-white hover:scale-110'
        ]"
        @click.stop="handleShowNotes"
        title="Edit notes"
      >
        <Icon icon="lucide:sticky-note" class="w-4 h-4" />
      </button>
      
      <button
        :class="[
          'p-2 rounded-full transition-all duration-200',
          'bg-red-500 bg-opacity-80 hover:bg-opacity-100',
          'text-white hover:scale-110'
        ]"
        @click.stop="handleDelete"
        title="Delete shift"
      >
        <Icon icon="lucide:trash-2" class="w-4 h-4" />
      </button>
    </div>

    <!-- Loading Overlay -->
    <div 
      v-if="isLoading"
      :class="[
        'absolute inset-0 flex items-center justify-center',
        'bg-white bg-opacity-80 rounded-lg backdrop-blur-sm'
      ]"
    >
      <div class="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useTheme } from './composables/useTheme'
import { useDragDrop } from './composables/useDragDrop'

// Props
const props = defineProps({
  shift: {
    type: Object,
    required: true
  },
  dates: {
    type: Array,
    required: true
  },
  startColumn: {
    type: Number,
    required: true
  },
  columnWidth: {
    type: Number,
    default: 80
  },
  rowHeight: {
    type: Number,
    default: 64
  },
  projectColor: {
    type: String,
    default: '#6b7280'
  },
  isSelected: {
    type: Boolean,
    default: false
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['edit', 'delete', 'show-notes', 'click'])

// Composables
const { colors } = useTheme()
const { handleTimeBlockDragStart, handleTimeBlockDragEnd } = useDragDrop()

// State
const isDragging = ref(false)

// Computed properties
const isNightShift = computed(() => {
  return props.shift.is_night_shift || 
         props.shift.start_time >= '22:00' || 
         props.shift.start_time <= '06:00'
})

const dayCount = computed(() => {
  return props.dates.length
})

const shiftTypeClasses = computed(() => {
  if (isNightShift.value) {
    return 'bg-gradient-to-r from-purple-600 to-indigo-700 border-purple-500 text-white'
  } else {
    return 'bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-300 text-gray-800'
  }
})

const shiftIndicatorColor = computed(() => {
  if (isNightShift.value) {
    return 'bg-gradient-to-b from-purple-400 to-purple-600'
  } else {
    return 'bg-gradient-to-b from-blue-400 to-blue-600'
  }
})

const barStyle = computed(() => {
  const width = props.dates.length * props.columnWidth - 4 // Account for borders
  const left = props.startColumn * props.columnWidth + 2
  const top = 8 // Padding from top of row
  const height = props.rowHeight - 16 // Leave padding top and bottom
  
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`
  }
})

const tooltipText = computed(() => {
  const parts = [
    `${formatTimeRange(props.shift.start_time, props.shift.end_time)}`,
    `${formatDuration(props.shift.hours)}`,
    isNightShift.value ? 'Night Shift' : 'Day Shift',
    `${dayCount.value} days`
  ]
  
  if (props.shift.notes || props.shift.description) {
    parts.push(`Notes: ${props.shift.notes || props.shift.description}`)
  }
  
  if (props.shift.resource_name) {
    parts.push(`Resource: ${props.shift.resource_name}`)
  }
  
  return parts.join(' • ')
})

// Methods
const formatTimeRange = (startTime, endTime) => {
  if (!startTime || !endTime) return 'No time'
  
  const formatTime = (time) => {
    const [hours, minutes] = time.split(':')
    const hour = parseInt(hours)
    const ampm = hour >= 12 ? 'PM' : 'AM'
    const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour
    return `${displayHour}:${minutes}${ampm}`
  }
  
  return `${formatTime(startTime)} - ${formatTime(endTime)}`
}

const formatDuration = (hours) => {
  if (!hours) return '0h'
  
  if (hours < 1) {
    return `${Math.round(hours * 60)}m`
  }
  
  const wholeHours = Math.floor(hours)
  const minutes = Math.round((hours - wholeHours) * 60)
  
  if (minutes === 0) {
    return `${wholeHours}h`
  }
  
  return `${wholeHours}h ${minutes}m`
}

const getResourceInitials = (resourceName) => {
  if (!resourceName) return '?'
  
  return resourceName
    .split(' ')
    .map(word => word.charAt(0).toUpperCase())
    .slice(0, 2)
    .join('')
}

const handleDragStart = (event) => {
  isDragging.value = true
  handleTimeBlockDragStart(event, {
    id: props.shift.id || `multi-shift-${Date.now()}`,
    dates: props.dates,
    type: 'multi-day-shift',
    ...props.shift
  })
}

const handleDragEnd = (event) => {
  isDragging.value = false
  handleTimeBlockDragEnd(event)
}

const handleClick = (event) => {
  event.stopPropagation()
  emit('click', props.shift)
}

const handleEdit = () => {
  emit('edit', props.shift)
}

const handleDelete = () => {
  emit('delete', props.shift)
}

const handleShowNotes = () => {
  emit('show-notes', props.shift)
}
</script>

<style scoped>
.multi-day-shift-bar {
  position: absolute;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.multi-day-shift-bar:hover {
  transform: translateY(-1px);
}

.multi-day-shift-bar:active {
  transform: translateY(0) scale(0.98);
}

.multi-day-shift-bar.dragging {
  transform: rotate(1deg) scale(0.95);
  z-index: 1000;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .multi-day-shift-bar {
    min-height: 40px;
  }
}
</style>
