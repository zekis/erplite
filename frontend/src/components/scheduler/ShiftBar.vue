<template>
  <div 
    :class="[
      'shift-bar absolute flex items-center cursor-move transition-all duration-200',
      'rounded-lg shadow-sm border-2',
      shiftTypeClasses,
      isDragging ? 'opacity-50 scale-95 z-50' : 'z-20',
      isSelected ? 'ring-2 ring-blue-400 ring-offset-1' : '',
      'hover:shadow-md hover:scale-[1.02] hover:z-20',
      props.shift.startsOffScreen ? 'off-screen-indicator' : ''
    ]"
    :style="barStyle"
    :draggable="true"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
    @click="handleClick"
    @contextmenu="handleRightClick"
    :title="tooltipText"
  >
    <!-- Off-screen continuation indicator -->
    <div 
      v-if="props.shift.startsOffScreen"
      class="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-yellow-400 to-orange-500 rounded-l-lg"
      title="This shift continues from before the visible date range"
    />
    <!-- Left resize handle -->
    <div 
      v-if="dates.length > 1 || canExtend"
      class="absolute left-0 top-0 bottom-0 w-4 bg-black bg-opacity-0 hover:bg-opacity-20 cursor-w-resize transition-all duration-200 rounded-l-lg flex items-center justify-center"
      @mousedown="handleResizeStart($event, 'left')"
      @click.stop
      title="Drag to shrink from start"
    >
      <div class="w-1 h-6 bg-white bg-opacity-60 rounded-sm opacity-0 hover:opacity-100 transition-opacity"></div>
    </div>

    <!-- Right resize handle -->
    <div 
      v-if="dates.length > 1 || canExtend"
      class="absolute right-0 top-0 bottom-0 w-4 bg-black bg-opacity-0 hover:bg-opacity-20 cursor-e-resize transition-all duration-200 rounded-r-lg flex items-center justify-center"
      @mousedown="handleResizeStart($event, 'right')"
      @click.stop
      title="Drag to extend or shrink from end"
    >
      <div class="w-1 h-6 bg-white bg-opacity-60 rounded-sm opacity-0 hover:opacity-100 transition-opacity"></div>
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
          class="w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium text-white"
          :style="resourceColor ? { backgroundColor: resourceColor } : { backgroundColor: isNightShift ? '#8b5cf6' : '#3b82f6' }"
          :title="shift.resource_name"
        >
          {{ getResourceInitials(shift.resource_name) }}
        </div>
      </div>
    </div>


    <!-- Right-click context menu (teleported to body) -->
    <Teleport to="body">
      <div
        v-if="showContextMenu"
        :class="[
          'fixed bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700',
          'rounded-lg shadow-xl py-2 min-w-[160px]'
        ]"
        :style="contextMenuStyle"
        style="z-index: 99999;"
        @click.stop
      >
        <button
          @click="handleEdit"
          class="w-full flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          <Icon icon="lucide:edit-3" class="w-4 h-4 mr-3" />
          Edit Shift
        </button>
        
        <button
          @click="handleShowNotes"
          class="w-full flex items-center px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          <Icon icon="lucide:sticky-note" class="w-4 h-4 mr-3" />
          Edit Notes
        </button>
        
        <div class="border-t border-gray-200 dark:border-gray-600 my-1"></div>
        
        <button
          @click="handleDelete"
          class="w-full flex items-center px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
        >
          <Icon icon="lucide:trash-2" class="w-4 h-4 mr-3" />
          Delete Shift
        </button>
      </div>
    </Teleport>
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
const emit = defineEmits(['edit', 'delete', 'show-notes', 'click', 'resize', 'drag-move', 'drag-end', 'drag-start', 'move-shift'])

// State
const isDragging = ref(false)
const showContextMenu = ref(false)
const contextMenuPosition = ref({ x: 0, y: 0 })
const isResizing = ref(false)
const resizePreview = ref({ direction: null, columnsDelta: 0 })

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

const resourceColor = computed(() => {
  // Try different possible resource property names
  const resourceName = props.shift.resource_name || props.shift.resource || props.shift.resourceName
  
  if (!resourceName) {
    console.log('No resource found. Shift properties:', Object.keys(props.shift))
    return null
  }
  
  // Use the EXACT same color array and algorithm as Avatar component
  const colors = [
    '#3B82F6', // blue
    '#8B5CF6', // violet  
    '#06B6D4', // cyan
    '#10B981', // emerald
    '#F59E0B', // amber
    '#EF4444', // red
    '#EC4899', // pink
    '#84CC16', // lime
    '#6366F1', // indigo
    '#14B8A6'  // teal
  ]
  
  let hash = 0
  for (let i = 0; i < resourceName.length; i++) {
    hash = resourceName.charCodeAt(i) + ((hash << 5) - hash)
  }
  
  return colors[Math.abs(hash) % colors.length]
})

const shiftTypeClasses = computed(() => {
  const baseClasses = isNightShift.value
    ? 'border-purple-500 text-white'
    : 'border-blue-300 dark:border-gray-500 text-gray-800 dark:text-gray-100'
  
  
  // If we have a resource color, use it for both day and night shifts
  if (resourceColor.value) {
    return baseClasses // We'll handle the background with inline styles
  }
  
  // Default backgrounds for when no resource color
  if (isNightShift.value) {
    return `bg-gradient-to-r from-purple-600 to-indigo-700 ${baseClasses}`
  } else {
    return `bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-gray-700 dark:to-gray-600 ${baseClasses}`
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
  let width = props.dates.length * props.columnWidth - 4 // Account for borders
  let left = props.startColumn * props.columnWidth + 2
  const top = 4 // Small top padding
  const height = 42 // Fits perfectly in 50px row (50 - 4 top - 4 bottom = 42px)
  
  // Apply resize preview if currently resizing
  if (isResizing.value && resizePreview.value.columnsDelta !== 0) {
    const delta = resizePreview.value.columnsDelta
    
    if (resizePreview.value.direction === 'left') {
      // Left resize: adjust left position and width
      const leftAdjustment = delta * props.columnWidth
      left += leftAdjustment
      width -= leftAdjustment
    } else {
      // Right resize: adjust width only
      width += delta * props.columnWidth
    }
    
    // Ensure minimum width
    width = Math.max(width, props.columnWidth - 4)
  }
  
  const baseStyle = {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`
  }
  
  // Add visual indication when resizing
  if (isResizing.value) {
    baseStyle.opacity = '0.8'
    baseStyle.transform = 'scale(1.02)'
    baseStyle.zIndex = '100'
  }
  
  if (resourceColor.value) {
    const color = resourceColor.value
    
    if (isNightShift.value) {
      // Night shift: resource color with cross-hatch pattern
      const crossHatchSvg = `data:image/svg+xml,${encodeURIComponent(`
        <svg width="8" height="8" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="crosshatch" patternUnits="userSpaceOnUse" width="8" height="8">
              <path d="M0,8 L8,0" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>
              <path d="M0,0 L8,8" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>
            </pattern>
          </defs>
          <rect width="8" height="8" fill="${color}"/>
          <rect width="8" height="8" fill="url(#crosshatch)"/>
        </svg>
      `)}`
      
      baseStyle.background = `url("${crossHatchSvg}")`
      baseStyle.backgroundSize = '8px 8px'
    } else {
      // Day shift: full resource color tinting
      baseStyle.background = `linear-gradient(135deg, ${color}80 0%, ${color}60 50%, ${color}80 100%)`
    }
  }
  
  return baseStyle
})

const tooltipText = computed(() => {
  const parts = [
    `ID: ${props.shift.id || 'No ID'}`, // Add shift ID for debugging
    `${totalHours.value} hours total`,
    isNightShift.value ? 'Night Shift' : 'Day Shift',
    `${props.dates.length} day${props.dates.length > 1 ? 's' : ''}`
  ]
  
  // Add off-screen indicator
  if (props.shift.startsOffScreen) {
    parts.push(`⬅ Continues from ${props.shift.totalDays} total days`)
  }
  
  if (hasNotes.value) {
    parts.push(`Notes: ${props.shift.notes || props.shift.description}`)
  }
  
  if (props.shift.resource_name) {
    parts.push(`Resource: ${props.shift.resource_name}`)
  }
  
  // Add dates for debugging
  parts.push(`Dates: ${props.dates.join(', ')}`)
  
  return parts.join(' • ')
})

const contextMenuStyle = computed(() => {
  return {
    left: `${contextMenuPosition.value.x}px`,
    top: `${contextMenuPosition.value.y}px`
  }
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
  // Prevent default drag behavior - we'll handle movement manually
  event.preventDefault()
  
  isDragging.value = true
  
  const startX = event.clientX
  const startY = event.clientY
  const originalLeft = props.startColumn * props.columnWidth + 2
  
  // Store original data
  const dragData = {
    type: 'shift-bar',
    shift: props.shift,
    dates: props.dates,
    originalStartColumn: props.startColumn,
    originalDates: [...props.dates],
    sourceRowId: props.shift.rowId || 'unknown'
  }
  
  // Real-time drag movement
  const handleMouseMove = (moveEvent) => {
    const deltaX = moveEvent.clientX - startX
    const newLeft = originalLeft + deltaX
    
    // Calculate which column this corresponds to
    const newColumn = Math.round((newLeft - 2) / props.columnWidth)
    const clampedColumn = Math.max(0, newColumn) // Don't allow negative columns
    
    // Update the shift bar position in real-time
    const shiftElement = event.target
    shiftElement.style.left = `${clampedColumn * props.columnWidth + 2}px`
    shiftElement.style.zIndex = '1000'
    shiftElement.style.opacity = '0.8'
  }
  
  const handleMouseUp = (upEvent) => {
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
    
    // Calculate final position
    const deltaX = upEvent.clientX - startX
    const newLeft = originalLeft + deltaX
    const newColumn = Math.round((newLeft - 2) / props.columnWidth)
    const clampedColumn = Math.max(0, newColumn)
    
    // Reset visual state
    const shiftElement = event.target
    shiftElement.style.zIndex = ''
    shiftElement.style.opacity = ''
    
    isDragging.value = false
    
    // Only emit move if position actually changed
    if (clampedColumn !== props.startColumn) {
      emit('move-shift', {
        ...dragData,
        newStartColumn: clampedColumn,
        columnDelta: clampedColumn - props.startColumn
      })
    } else {
      // Reset position if no change
      shiftElement.style.left = `${originalLeft}px`
    }
  }
  
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
  
  // Emit drag start event
  emit('drag-start', dragData)
}

const handleDragEnd = (event) => {
  isDragging.value = false
  
  // Emit drag end event for cleanup
  emit('drag-end', {
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
  let lastColumnsDelta = 0
  
  // Start resize mode
  isResizing.value = true
  resizePreview.value = { direction, columnsDelta: 0 }
  
  const handleMouseMove = (moveEvent) => {
    const deltaX = moveEvent.clientX - startX
    const columnsDelta = Math.round(deltaX / props.columnWidth)
    
    // Update visual preview
    resizePreview.value.columnsDelta = columnsDelta
    
    // Only emit if the delta has changed (to avoid excessive updates)
    if (columnsDelta !== lastColumnsDelta) {
      lastColumnsDelta = columnsDelta
      emit('resize', {
        shift: props.shift,
        originalDates,
        direction,
        columnsDelta
      })
    }
  }
  
  const handleMouseUp = () => {
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
    
    // End resize mode
    isResizing.value = false
    resizePreview.value = { direction: null, columnsDelta: 0 }
    
    // Final resize event to ensure the change is committed
    if (lastColumnsDelta !== 0) {
      emit('resize', {
        shift: props.shift,
        originalDates,
        direction,
        columnsDelta: lastColumnsDelta,
        isComplete: true
      })
    }
  }
  
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

const handleClick = (event) => {
  event.stopPropagation()
  closeContextMenu()
  emit('click', props.shift)
}

const handleRightClick = (event) => {
  event.preventDefault()
  event.stopPropagation()
  
  // Close any existing context menus first
  document.dispatchEvent(new CustomEvent('close-all-context-menus'))
  
  // Position the context menu at the mouse position
  contextMenuPosition.value = {
    x: event.clientX,
    y: event.clientY
  }
  
  showContextMenu.value = true
  
  // Add click listener to close menu when clicking outside
  setTimeout(() => {
    document.addEventListener('click', closeContextMenu, { once: true })
    document.addEventListener('close-all-context-menus', closeContextMenu, { once: true })
  }, 0)
}

const closeContextMenu = () => {
  showContextMenu.value = false
}

const handleEdit = () => {
  closeContextMenu()
  emit('edit', props.shift)
}

const handleDelete = () => {
  closeContextMenu()
  emit('delete', props.shift)
}

const handleShowNotes = () => {
  closeContextMenu()
  emit('show-notes', props.shift)
}
</script>

<style scoped>
.shift-bar {
  position: absolute;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  pointer-events: auto; /* Enable pointer events for shift bars */
  /* Use the calculated width from barStyle instead of fit-content */
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
