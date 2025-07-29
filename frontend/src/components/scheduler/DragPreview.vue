<template>
  <div
    v-if="isVisible"
    :class="[
      'drag-preview fixed pointer-events-none z-[9999] transition-all duration-100',
      'rounded-lg shadow-lg border-2 opacity-80',
      previewClasses
    ]"
    :style="previewStyle"
  >
    <!-- Preview content matching ShiftBar -->
    <div class="flex-1 flex items-center justify-between px-3 py-1 min-w-0">
      <!-- Left: Total hours and indicators -->
      <div class="flex items-center space-x-2 min-w-0">
        <!-- Night shift indicator -->
        <div 
          v-if="dragData?.shift?.is_night_shift"
          class="w-2 h-2 rounded-full bg-purple-400"
        />
        
        <!-- Total hours -->
        <div :class="[
          'text-sm font-semibold',
          dragData?.shift?.is_night_shift ? 'text-purple-100' : 'text-gray-800'
        ]">
          {{ totalHours }}h
        </div>
        
        <!-- Multi-day indicator -->
        <div 
          v-if="dragData?.dates?.length > 1"
          :class="[
            'text-xs px-1.5 py-0.5 rounded-full font-medium',
            dragData?.shift?.is_night_shift 
              ? 'bg-purple-700/50 text-purple-100' 
              : 'bg-gray-200 text-gray-700'
          ]"
        >
          {{ dragData?.dates?.length }}d
        </div>
      </div>

      <!-- Right: Resource avatar -->
      <div class="flex items-center space-x-1 ml-2">
        <div 
          v-if="dragData?.shift?.resource_name"
          class="w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium text-white"
          :style="{ backgroundColor: resourceColor }"
        >
          {{ getResourceInitials(dragData?.shift?.resource_name) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

// Props
const props = defineProps({
  dragData: {
    type: Object,
    default: null
  },
  columnWidth: {
    type: Number,
    default: 80
  },
  snapToGrid: {
    type: Boolean,
    default: true
  }
})

// State
const isVisible = ref(false)
const position = ref({ x: 0, y: 0 })
const snappedPosition = ref({ column: 0, row: 0 })

// Computed
const totalHours = computed(() => {
  if (!props.dragData?.shift?.hours || !props.dragData?.dates?.length) return 0
  return props.dragData.shift.hours * props.dragData.dates.length
})

const resourceColor = computed(() => {
  const resourceName = props.dragData?.shift?.resource_name
  if (!resourceName) return '#3b82f6'
  
  // Same color algorithm as ShiftBar
  const colors = [
    '#3B82F6', '#8B5CF6', '#06B6D4', '#10B981', '#F59E0B',
    '#EF4444', '#EC4899', '#84CC16', '#6366F1', '#14B8A6'
  ]
  
  let hash = 0
  for (let i = 0; i < resourceName.length; i++) {
    hash = resourceName.charCodeAt(i) + ((hash << 5) - hash)
  }
  
  return colors[Math.abs(hash) % colors.length]
})

const previewClasses = computed(() => {
  const isNight = props.dragData?.shift?.is_night_shift
  return isNight
    ? 'border-purple-500 text-white'
    : 'border-blue-300 text-gray-800'
})

const previewStyle = computed(() => {
  const width = (props.dragData?.dates?.length || 1) * props.columnWidth - 4
  const height = 42
  
  let left = position.value.x
  let top = position.value.y
  
  // Snap to grid if enabled
  if (props.snapToGrid) {
    const schedulerTable = document.querySelector('.scheduler-table')
    if (schedulerTable) {
      const rect = schedulerTable.getBoundingClientRect()
      const relativeX = left - rect.left
      const relativeY = top - rect.top
      
      // Snap to column grid (80px columns)
      const column = Math.round(relativeX / props.columnWidth)
      const row = Math.round(relativeY / 64) // 64px row height
      
      left = rect.left + (column * props.columnWidth) + 2
      top = rect.top + (row * 64) + 4
      
      snappedPosition.value = { column, row }
    }
  }
  
  const baseStyle = {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`,
    transform: 'translate(-50%, -50%)'
  }
  
  // Apply resource color background
  if (resourceColor.value) {
    const color = resourceColor.value
    const isNight = props.dragData?.shift?.is_night_shift
    
    if (isNight) {
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
      // Day shift: resource color tinting
      baseStyle.background = `linear-gradient(135deg, ${color}80 0%, ${color}60 50%, ${color}80 100%)`
    }
  }
  
  return baseStyle
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

const updatePosition = (event) => {
  position.value = {
    x: event.clientX,
    y: event.clientY
  }
}

const show = (event) => {
  isVisible.value = true
  updatePosition(event)
}

const hide = () => {
  isVisible.value = false
}

const handleDragOver = (event) => {
  if (isVisible.value) {
    updatePosition(event)
  }
}

// Lifecycle
onMounted(() => {
  document.addEventListener('dragover', handleDragOver)
})

onUnmounted(() => {
  document.removeEventListener('dragover', handleDragOver)
})

// Expose methods
defineExpose({
  show,
  hide,
  updatePosition
})
</script>

<style scoped>
.drag-preview {
  pointer-events: none;
  z-index: 9999;
}
</style>
