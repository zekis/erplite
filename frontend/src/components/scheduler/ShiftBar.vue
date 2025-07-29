<template>
  <div 
    :class="[
      'shift-bar absolute flex items-center cursor-move transition-all duration-200',
      'rounded-lg shadow-sm border-2',
      shiftTypeClasses,
      isDragging ? 'opacity-50 scale-95 z-50' : 'z-20',
      isSelected ? 'ring-2 ring-blue-400 ring-offset-1' : '',
      'hover:shadow-md hover:scale-[1.02] hover:z-20'
    ]"
    :style="barStyle"
    :draggable="true"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
    @click="handleClick"
    :title="tooltipText"
  >
    <!-- Left resize handle -->
    <div 
      v-if="dates.length > 1 || canExtend"
      class="absolute left-0 top-0 bottom-0 w-2 bg-blue-500 bg-opacity-0 hover:bg-opacity-80 cursor-w-resize transition-all duration-200 rounded-l-md group-hover:bg-opacity-40"
      @mousedown="handleResizeStart($event, 'left')"
      @click.stop
      title="Drag to shrink from start"
    >
      <div class="absolute left-0.5 top-1/2 transform -translate-y-1/2 w-1 h-4 bg-white bg-opacity-60 rounded-sm opacity-0 hover:opacity-100 transition-opacity"></div>
    </div>

    <!-- Right resize handle -->
    <div 
      v-if="dates.length > 1 || canExtend"
      class="absolute right-0 top-0 bottom-0 w-2 bg-blue-500 bg-opacity-0 hover:bg-opacity-80 cursor-e-resize transition-all duration-200 rounded-r-md group-hover:bg-opacity-40"
      @mousedown="handleResizeStart($event, 'right')"
      @click.stop
      title="Drag to extend or shrink from end"
    >
      <div class="absolute right-0.5 top-1/2 transform -translate-y-1/2 w-1 h-4 bg-white bg-opacity-60 rounded-sm opacity-0 hover:opacity-100 transition-opacity"></div>
    </div>

    <!-- Shift content -->
    <div class="flex-1 flex items-center justify-between px-3 py-1 min-w-0">
      <!-- Left: Total hours and night shift indicator -->
      <div class="flex items-center space-x-2 min-w-0">
        <!-- Night shift indicator -->
        <div 
          v-if="isNightShift"
          :class="[
            'w-2 h-2 rounded-full',
            isNightShift ? 'bg-purple-400' : 'bg-blue-400'
          ]"
          title="Night shift"
        />
        
        <!-- Total hours -->
        <div :class="[
          'text-sm font-semibold',
          isNightShift ? 'text-purple-100' : 'text-gray-800'
        ]">
          {{ totalHours }}h
        </div>
        
        <!-- Multi-day indicator -->
        <div 
          v-if="dates.length > 1"
          :class="[
            'text-xs px-1.5 py-0.5 rounded-full font-medium',
            isNightShift 
              ? 'bg-purple-700/50 text-purple-100' 
              : 'bg-gray-200 text-gray-700'
          ]"
        >
          {{ dates.length }}d
        </div>
      </div>

      <!-- Right: Notes icon and resource -->
      <div class="flex items-center space-x-1 ml-2">
        <!-- Notes icon -->
        <button
          v-if="hasNotes"
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
        
        <!-- Resource avatar -->
        <div 
          v-if="shift.resource_name"
          :class="[
            'w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium',
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

    <!-- Shift type indicator (left edge) -->
    <div 
      :class="[
        'absolute left-0 top-0 bottom-0 w-1 rounded-l-lg',
        shiftIndicatorColor
      ]"
    />

    <!-- Project color indicator (right edge) -->
    <div 
      v-if="projectColor && projectColor !== '#6b7280'"
      :class="[
        'absolute right-0 top-0 bottom-0 w-1 rounded-r-lg'
      ]"
      :style="{ backgroundColor: projectColor }"
    />

    <!-- Hover actions overlay -->
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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
// Composables removed - using direct Tailwind classes

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
  canExtend: {
    type: Boolean,
    default: true
  }
})

// Emits
const emit = defineEmits(['edit', 'delete', 'show-notes', 'click', 'resize', 'drag-move'])

// State
const isDragging = ref(false)

// Computed properties
const isNightShift = computed(() => {
  return props.shift.is_night_shift || 
         props.shift.start_time >= '22:00' || 
         props.shift.start_time <= '06:00'
})

const totalHours = computed(() => {
  if (props.shift.hours) {
    return props.shift.hours * props.dates.length
  }
  return props.dates.length * 8 // Default 8 hours per day
})

const hasNotes = computed(() => {
  return !!(props.shift.notes || props.shift.description)
})

const shiftTypeClasses = computed(() => {
  if (isNightShift.value) {
    return 'bg-gradient-to-r from-purple-600 to-indigo-700 border-purple-500 text-white'
  } else {
    return 'bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-gray-700 dark:to-gray-600 border-blue-300 dark:border-gray-500 text-gray-800 dark:text-gray-100'
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
  const top = 12 // More padding from top
  const height = 32 // Fixed smaller height to prevent scrollbars
  
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`
  }
})

const tooltipText = computed(() => {
  const parts = [
    `${totalHours.value} hours total`,
    isNightShift.value ? 'Night Shift' : 'Day Shift',
    `${props.dates.length} day${props.dates.length > 1 ? 's' : ''}`
  ]
  
  if (hasNotes.value) {
    parts.push(`Notes: ${props.shift.notes || props.shift.description}`)
  }
  
  if (props.shift.resource_name) {
    parts.push(`Resource: ${props.shift.resource_name}`)
  }
  
  return parts.join(' • ')
})

// Methods
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
  // Set drag data for moving the entire shift
  event.dataTransfer.setData('text/plain', JSON.stringify({
    type: 'shift-bar',
    shift: props.shift,
    dates: props.dates
  }))
}

const handleDragEnd = (event) => {
  isDragging.value = false
  emit('drag-move', {
    shift: props.shift,
    dates: props.dates,
    event
  })
}

const handleResizeStart = (event, direction) => {
  event.preventDefault()
  event.stopPropagation()
  
  const startX = event.clientX
  const originalDates = [...props.dates]
  
  const handleMouseMove = (moveEvent) => {
    const deltaX = moveEvent.clientX - startX
    const columnsDelta = Math.round(deltaX / props.columnWidth)
    
    emit('resize', {
      shift: props.shift,
      originalDates,
      direction,
      columnsDelta
    })
  }
  
  const handleMouseUp = () => {
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
  }
  
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
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
.shift-bar {
  position: absolute;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  pointer-events: auto; /* Enable pointer events for shift bars */
  /* Ensure shift bars don't block empty cell interactions */
  width: fit-content;
  max-width: 100%;
}

.shift-bar:hover {
  transform: translateY(-1px);
}

.shift-bar:active {
  transform: translateY(0) scale(0.98);
}

.shift-bar.dragging {
  transform: rotate(1deg) scale(0.95);
  z-index: 1000;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .shift-bar {
    min-height: 40px;
  }
}
</style>
