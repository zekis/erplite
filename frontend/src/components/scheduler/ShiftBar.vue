<template>
  <div 
    :class="[
      'shift-bar absolute flex items-center cursor-move transition-all duration-200',
      'rounded-lg shadow-sm border-2',
      shiftTypeClasses,
      isDragging ? 'opacity-50 scale-95 z-50' : 'z-20',
      isSelected ? 'ring-2 ring-blue-400 ring-offset-1' : '',
      'hover:shadow-md hover:scale-[1.02] hover:z-20',
      props.shift.isPartial ? 'partial-shift' : ''
    ]"
    :style="barStyle"
    :draggable="true"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
    @click="handleClick"
    @contextmenu="handleRightClick"
    :title="tooltipText"
  >
    <!-- Left continuation indicator -->
    <div 
      v-if="props.shift.startsOffScreen"
      class="absolute left-0 top-0 bottom-0 w-3 bg-gradient-to-r from-orange-400 to-transparent rounded-l-lg flex items-center justify-start pl-0.5 cursor-pointer hover:from-orange-500 transition-colors duration-200"
      title="Click to navigate to start of shift"
      @click.stop="handleNavigateToStart"
    >
      <Icon icon="lucide:chevron-left" class="w-3 h-3 text-white opacity-90" />
    </div>
    
    <!-- Right continuation indicator -->
    <div 
      v-if="props.shift.endsOffScreen"
      class="absolute right-0 top-0 bottom-0 w-3 bg-gradient-to-l from-orange-400 to-transparent rounded-r-lg flex items-center justify-end pr-0.5"
      title="Continues to later dates"
    >
      <Icon icon="lucide:chevron-right" class="w-3 h-3 text-white opacity-90" />
    </div>
    <!-- Left resize handle - only show if shift doesn't start off-screen -->
    <div 
      v-if="(dates.length > 1 || canExtend) && !props.shift.startsOffScreen"
      class="absolute left-0 top-0 bottom-0 w-4 bg-black bg-opacity-0 hover:bg-opacity-20 cursor-w-resize transition-all duration-200 rounded-l-lg flex items-center justify-center"
      @mousedown="handleResizeStart($event, 'left')"
      @click.stop
      title="Drag to shrink from start"
    >
      <div class="w-1 h-6 bg-white bg-opacity-60 rounded-sm opacity-0 hover:opacity-100 transition-opacity"></div>
    </div>

    <!-- Right resize handle - only show if shift doesn't end off-screen -->
    <div 
      v-if="(dates.length > 1 || canExtend) && !props.shift.endsOffScreen"
      class="absolute right-0 top-0 bottom-0 w-4 bg-black bg-opacity-0 hover:bg-opacity-20 cursor-e-resize transition-all duration-200 rounded-r-lg flex items-center justify-center"
      @mousedown="handleResizeStart($event, 'right')"
      @click.stop
      title="Drag to extend or shrink from end"
    >
      <div class="w-1 h-6 bg-white bg-opacity-60 rounded-sm opacity-0 hover:opacity-100 transition-opacity"></div>
    </div>

    <!-- Individual column durations and day/night indicators -->
    <div 
      v-for="(date, index) in props.dates" 
      :key="date"
      class="absolute flex items-center justify-between px-2 pointer-events-none"
      :style="{
        left: `${index * props.columnWidth}px`,
        width: `${props.columnWidth}px`,
        height: '100%',
        top: '0'
      }"
    >
      <!-- Duration text for this specific column -->
      <div 
        :class="[
          'text-xs font-semibold',
          isNightShift ? 'text-purple-100' : 'text-gray-700 dark:text-gray-300'
        ]"
        :title="`${date}: ${getDailyHours(date)}h`"
      >
        {{ getDailyHours(date) }}h
      </div>
      
      <!-- Day/Night indicator icon -->
      <div 
        :class="[
          'flex items-center justify-center',
          isNightShift ? 'text-purple-200' : 'text-yellow-500'
        ]"
        :title="isNightShift ? 'Night shift' : 'Day shift'"
      >
        <Icon 
          :icon="isNightShift ? 'lucide:moon' : 'lucide:sun'" 
          class="w-3 h-3" 
        />
      </div>
    </div>

    <!-- Notes corner triangle indicator -->
    <div 
      v-if="hasNotes"
      class="absolute top-0 right-0 w-0 h-0 pointer-events-none"
      style="border-left: 8px solid transparent; border-top: 8px solid #f59e0b;"
      title="This shift has notes"
    />


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
const emit = defineEmits(['edit', 'delete', 'show-notes', 'click', 'resize', 'drag-move', 'drag-end', 'drag-start', 'move-shift', 'navigate-to-start'])

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
      // Night shift: darker, more subdued resource color
      baseStyle.background = `linear-gradient(135deg, ${color}50 0%, ${color}40 50%, ${color}50 100%)`
      // Add a darker overlay to tone down the brightness
      baseStyle.boxShadow = 'inset 0 0 0 1000px rgba(0,0,0,0.2)'
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
    isNightShift.value ? 'Night Shift' : 'Day Shift'
  ]
  
  // Add partial shift information
  if (props.shift.isPartial) {
    if (props.shift.totalDays > props.shift.visibleDays) {
      parts.push(`Showing ${props.shift.visibleDays} of ${props.shift.totalDays} days`)
    }
    
    if (props.shift.startsOffScreen) {
      const startDate = props.shift.allDates[0]
      parts.push(`⬅ Starts ${startDate}`)
    }
    
    if (props.shift.endsOffScreen) {
      const endDate = props.shift.allDates[props.shift.allDates.length - 1]
      parts.push(`Ends ${endDate} ➡`)
    }
  } else {
    parts.push(`${props.dates.length} day${props.dates.length > 1 ? 's' : ''}`)
  }
  
  if (hasNotes.value) {
    parts.push(`Notes: ${props.shift.notes || props.shift.description}`)
  }
  
  if (props.shift.resource_name) {
    parts.push(`Resource: ${props.shift.resource_name}`)
  }
  
  // Add visible dates for debugging
  parts.push(`Visible: ${props.dates.join(', ')}`)
  
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

const getDailyHours = (date) => {
  // Return the hours for this specific date
  // If the shift has a specific hours property, use that
  // Otherwise, calculate from start_time and end_time or default to 8
  if (props.shift.hours) {
    return props.shift.hours
  }
  
  // Try to calculate from start_time and end_time
  if (props.shift.start_time && props.shift.end_time) {
    const startTime = new Date(`2000-01-01T${props.shift.start_time}:00`)
    const endTime = new Date(`2000-01-01T${props.shift.end_time}:00`)
    
    // Handle overnight shifts
    if (endTime < startTime) {
      endTime.setDate(endTime.getDate() + 1)
    }
    
    const diffMs = endTime - startTime
    const diffHours = diffMs / (1000 * 60 * 60)
    return Math.round(diffHours * 10) / 10 // Round to 1 decimal place
  }
  
  // Default to 8 hours
  return 8
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

const handleNavigateToStart = () => {
  // Emit navigation event with the start date of the shift
  if (props.shift.allDates && props.shift.allDates.length > 0) {
    const startDate = props.shift.allDates[0]
    emit('navigate-to-start', {
      shift: props.shift,
      startDate: startDate
    })
  }
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
