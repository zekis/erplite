<template>
  <div 
    :class="[
      'empty-day-cell relative flex-shrink-0 border-r min-h-[64px] flex flex-col justify-center items-center transition-all duration-200 cursor-pointer',
      'border-gray-200 dark:border-gray-700',
      cellClasses
    ]"
    :data-date="date"
    :data-row-index="rowIndex"
    @click="handleClick"
    @mousedown="handleMouseDown"
    @drop="handleDrop"
    @dragover.prevent="handleDragOver"
    @dragenter.prevent="handleDragEnter"
    @dragleave="handleDragLeave"
    style="width: 80px; min-width: 80px; max-width: 80px;"
  >
    <!-- Drop Zone Indicator -->
    <div v-if="isDragOver" :class="[
      'drop-zone-indicator absolute inset-0 flex items-center justify-center border-2 border-dashed rounded transition-all duration-200',
      'bg-blue-100 bg-opacity-75 border-blue-300'
    ]">
      <Icon icon="lucide:plus" class="w-4 h-4 text-blue-500" />
    </div>

    <!-- Empty Cell Placeholder -->
    <div v-if="!isDragOver" class="empty-placeholder absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity duration-200 bg-gray-50 dark:bg-gray-700">
      <Icon icon="lucide:plus" class="w-3 h-3 text-gray-400" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useDragDrop } from './composables/useDragDrop'

// Props
const props = defineProps({
  date: {
    type: String,
    required: true
  },
  dateInfo: {
    type: Object,
    required: true
  },
  row: {
    type: Object,
    required: true
  },
  rowIndex: {
    type: Number,
    required: true
  },
  projectColor: {
    type: String,
    default: '#6b7280'
  }
})

// Emits
const emit = defineEmits(['create-entry', 'show-context-menu', 'move-shift'])

// Local state
const isDragOver = ref(false)

// Composables
const { 
  isDragSelecting, 
  startDragSelection
} = useDragDrop()

// Computed properties
const cellClasses = computed(() => {
  return {
    'today': props.dateInfo.isToday,
    'weekend': props.dateInfo.isWeekend,
    'interactive': true,
    'drag-over': isDragOver.value
    // Removed 'drag-selecting': isDragSelecting.value - this was causing all cells to glow
    // The drag-selected class is applied dynamically via JavaScript in useDragDrop.js
  }
})

// Methods
const handleClick = (event) => {
  event.preventDefault()
  event.stopPropagation()
  
  // Only handle single clicks if we're not in the middle of a drag operation
  if (!isDragSelecting.value) {
    // Show context menu for single day selection
    const position = { x: event.clientX, y: event.clientY }
    emit('show-context-menu', [props.date], position)
  }
}

const handleMouseDown = (event) => {
  if (event.button !== 0) return // Only left mouse button
  
  event.preventDefault()
  
  // Start drag selection with context menu callback
  const showContextMenuCallback = (selectedDates, position) => {
    emit('show-context-menu', selectedDates, position)
  }
  
  startDragSelection(event, props.rowIndex, props.date, showContextMenuCallback)
}

const handleDrop = (event) => {
  event.preventDefault()
  event.stopPropagation()
  
  isDragOver.value = false
  
  try {
    // Try to get data from both possible formats
    let data
    try {
      data = JSON.parse(event.dataTransfer.getData('application/json'))
    } catch {
      data = JSON.parse(event.dataTransfer.getData('text/plain'))
    }
    
    if (data.type === 'shift-bar') {
      handleShiftBarDrop(data, event)
    } else if (data.type === 'template') {
      handleTemplateDrop(data.template)
    } else if (data.type === 'time-block') {
      handleTimeBlockMove(data)
    }
  } catch (error) {
    console.error('Error handling drop:', error)
  }
}

const handleDragOver = (event) => {
  event.preventDefault()
  isDragOver.value = true
  
  // Show multi-day drop zone if dragging a shift bar
  try {
    const data = JSON.parse(event.dataTransfer.getData('application/json'))
    if (data.type === 'shift-bar') {
      showMultiDayDropZone(data.dates.length)
    }
  } catch (error) {
    // Ignore parsing errors
  }
}

const handleDragEnter = (event) => {
  event.preventDefault()
  isDragOver.value = true
}

const handleDragLeave = (event) => {
  // Only remove drag over if we're actually leaving the cell
  if (!event.currentTarget.contains(event.relatedTarget)) {
    isDragOver.value = false
    hideMultiDayDropZone()
  }
}

const handleTemplateDrop = (template) => {
  const templateConfig = getTemplateConfig(template)
  
  const entryData = {
    date: props.date,
    hours: templateConfig.hours,
    start_time: templateConfig.start_time,
    end_time: templateConfig.end_time,
    description: templateConfig.description,
    status: templateConfig.status
  }
  
  emit('create-entry', entryData)
}

const handleShiftBarDrop = (data, event) => {
  // Calculate the new start date based on drop position
  const rect = event.currentTarget.getBoundingClientRect()
  const dropX = event.clientX - rect.left
  
  // Calculate which column this corresponds to (for multi-day shifts)
  const columnIndex = Math.floor(dropX / 80) // 80px per column
  const newStartDate = props.date
  
  // Emit shift move event
  emit('move-shift', {
    shift: data.shift,
    originalDates: data.originalDates,
    newStartDate: newStartDate,
    targetRowId: props.row.id,
    sourceRowId: data.sourceRowId
  })
}

const handleTimeBlockMove = (data) => {
  // Handle moving existing time blocks
  emit('create-entry', {
    date: props.date,
    hours: data.entry.hours,
    start_time: data.entry.start_time,
    end_time: data.entry.end_time,
    description: data.entry.description,
    status: data.entry.status,
    moveFromDate: data.entry.date,
    moveEntryId: data.entryId
  })
}

const showMultiDayDropZone = (dayCount) => {
  // Find all cells in this row starting from current date
  const currentCell = document.querySelector(`[data-date="${props.date}"][data-row-index="${props.rowIndex}"]`)
  if (!currentCell) return
  
  const row = currentCell.closest('.activity-row')
  if (!row) return
  
  // Find all day cells in this row
  const dayCells = row.querySelectorAll('.empty-day-cell')
  const currentIndex = Array.from(dayCells).indexOf(currentCell)
  
  // Highlight the cells that would be covered by the multi-day shift
  for (let i = 0; i < dayCount && (currentIndex + i) < dayCells.length; i++) {
    const cell = dayCells[currentIndex + i]
    if (cell) {
      cell.classList.add('multi-day-drop-zone')
    }
  }
}

const hideMultiDayDropZone = () => {
  // Remove multi-day drop zone indicators from all cells
  const allCells = document.querySelectorAll('.multi-day-drop-zone')
  allCells.forEach(cell => {
    cell.classList.remove('multi-day-drop-zone')
  })
}

const getTemplateConfig = (template) => {
  const templates = {
    '8h': {
      hours: 8,
      start_time: '09:00',
      end_time: '17:00',
      description: '8 hour work day',
      status: 'planned'
    },
    '12h': {
      hours: 12,
      start_time: '07:00',
      end_time: '19:00',
      description: '12 hour shift',
      status: 'planned'
    },
    'leave': {
      hours: 8,
      start_time: '00:00',
      end_time: '23:59',
      description: 'Leave day',
      status: 'leave'
    }
  }
  
  return templates[template] || templates['8h']
}
</script>

<style scoped>
.empty-day-cell {
  @apply relative flex-shrink-0 border-r border-gray-200 min-h-[50px] flex flex-col justify-center items-center;
  width: 80px;
}

.empty-day-cell.today {
  @apply bg-blue-50 dark:bg-blue-900;
}

.empty-day-cell.weekend {
  @apply bg-blue-50 dark:bg-blue-900/30;
}

.empty-day-cell.interactive {
  @apply cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600;
}

.empty-day-cell.drag-over {
  @apply bg-blue-100 dark:bg-blue-800 border-blue-300 dark:border-blue-500;
}


/* Global drag selection styling */
:global(.empty-day-cell.drag-selected) {
  @apply bg-blue-200 dark:bg-blue-700 border-blue-400 dark:border-blue-400 border-2;
  animation: dragPulse 0.5s ease-in-out infinite alternate;
}

@keyframes dragPulse {
  from { 
    background-color: rgb(191 219 254); /* blue-200 */
  }
  to { 
    background-color: rgb(147 197 253); /* blue-300 */
  }
}

@media (prefers-color-scheme: dark) {
  @keyframes dragPulse {
    from { 
      background-color: rgb(29 78 216); /* blue-700 */
    }
    to { 
      background-color: rgb(37 99 235); /* blue-600 */
    }
  }
}

.drop-zone-indicator {
  @apply absolute inset-0 flex items-center justify-center bg-blue-100 bg-opacity-75 border-2 border-dashed border-blue-300 rounded;
}

/* Multi-day drop zone styling */
:global(.multi-day-drop-zone) {
  @apply bg-green-100 dark:bg-green-800 border-green-300 dark:border-green-500 border-2 border-dashed;
  animation: multiDayPulse 1s ease-in-out infinite alternate;
}

@keyframes multiDayPulse {
  from { 
    background-color: rgb(220 252 231); /* green-100 */
    border-color: rgb(134 239 172); /* green-300 */
  }
  to { 
    background-color: rgb(187 247 208); /* green-200 */
    border-color: rgb(74 222 128); /* green-400 */
  }
}

@media (prefers-color-scheme: dark) {
  @keyframes multiDayPulse {
    from { 
      background-color: rgb(22 101 52); /* green-800 */
      border-color: rgb(34 197 94); /* green-500 */
    }
    to { 
      background-color: rgb(21 128 61); /* green-700 */
      border-color: rgb(74 222 128); /* green-400 */
    }
  }
}
</style>
