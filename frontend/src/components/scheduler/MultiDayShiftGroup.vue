<template>
  <div class="multi-day-shift-group w-full h-full">
    <!-- Unified shift bars for all shifts (single or multi-day) -->
    <ShiftBar
      v-for="group in shiftGroups"
      :key="group.id"
      :shift="enrichShiftWithRowData(group.shift)"
      :dates="group.dates"
      :start-column="group.startColumn"
      :column-width="columnWidth"
      :row-height="64"
      :project-color="projectColor"
      @edit="$emit('edit-shift', $event)"
      @delete="$emit('delete-shift', $event)"
      @show-notes="$emit('show-notes', $event)"
      @click="$emit('click-shift', $event)"
      @resize="handleResize"
      @drag-move="handleDragMove"
      @drag-start="handleDragStart"
      @drag-end="handleDragEnd"
      @move-shift="handleMoveShift"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ShiftBar from './ShiftBar.vue'

// Props
const props = defineProps({
  row: {
    type: Object,
    required: true
  },
  dateColumns: {
    type: Array,
    required: true
  },
  projectColor: {
    type: String,
    default: '#6b7280'
  },
  columnWidth: {
    type: Number,
    default: 80
  }
})

// Emits
const emit = defineEmits([
  'edit-shift', 
  'delete-shift',
  'show-notes',
  'click-shift'
])

// Get all shifts sorted by date
const allShifts = computed(() => {
  if (!props.row.dailyEntries) return []
  
  const shifts = []
  Object.entries(props.row.dailyEntries).forEach(([date, entries]) => {
    const entryArray = Array.isArray(entries) ? entries : [entries]
    entryArray.forEach(entry => {
      // Ensure every shift has an ID - generate one if missing
      if (!entry.id) {
        entry.id = `shift-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
        console.log('Generated ID for API shift:', entry.id, 'on date:', date)
      }
      
      shifts.push({
        ...entry,
        date: date
      })
    })
  })
  
  // Sort by date
  return shifts.sort((a, b) => new Date(a.date) - new Date(b.date))
})

// Group consecutive shifts with same time range
const shiftGroups = computed(() => {
  if (allShifts.value.length === 0) return []
  
  const groups = []
  const processed = new Set()
  
  allShifts.value.forEach((shift, index) => {
    if (processed.has(index)) return
    
    // Find consecutive shifts with same time range and same shift ID/properties
    const consecutiveShifts = [shift]
    processed.add(index)
    
    // Look ahead for consecutive days with same time range and matching properties
    for (let i = index + 1; i < allShifts.value.length; i++) {
      const nextShift = allShifts.value[i]
      const lastShift = consecutiveShifts[consecutiveShifts.length - 1]
      
      // Check if next day, same time range, and same shift properties
      if (isNextDay(lastShift.date, nextShift.date) && 
          hasSameTimeRange(lastShift, nextShift) &&
          hasSameShiftProperties(lastShift, nextShift)) {
        consecutiveShifts.push(nextShift)
        processed.add(i)
      } else {
        break
      }
    }
    
    // Create shift bar for any shift (1+ days)
    if (consecutiveShifts.length >= 1) {
      const allDates = consecutiveShifts.map(s => s.date)
      const startColumn = getColumnIndex(allDates[0])
      
      // Handle shifts that start before the visible calendar range
      if (startColumn === -1) {
        // Find the first visible date in this shift group
        const visibleDates = allDates.filter(date => getColumnIndex(date) !== -1)
        
        if (visibleDates.length > 0) {
          // This shift extends into the visible range - show the tail end
          const firstVisibleColumn = getColumnIndex(visibleDates[0])
          
          groups.push({
            id: `group-${shift.id || shift.date}-${allDates.length}-${shift.start_time}`,
            shift: {
              ...shift,
              startsOffScreen: true, // Flag to indicate this starts before visible range
              totalDays: allDates.length, // Total days including off-screen portion
              visibleDays: visibleDates.length // Only the visible portion
            },
            dates: visibleDates, // Only show visible dates
            startColumn: firstVisibleColumn,
            startsOffScreen: true
          })
        }
      } else {
        // Normal shift that starts within visible range
        groups.push({
          id: `group-${shift.id || shift.date}-${allDates.length}-${shift.start_time}`,
          shift: shift,
          dates: allDates,
          startColumn: startColumn,
          startsOffScreen: false
        })
      }
    }
  })
  
  return groups
})

// Helper functions
const isNextDay = (date1, date2) => {
  const d1 = new Date(date1)
  const d2 = new Date(date2)
  const diffTime = d2 - d1
  const diffDays = diffTime / (1000 * 60 * 60 * 24)
  return diffDays === 1
}

const hasSameTimeRange = (shift1, shift2) => {
  // Group shifts with same start_time and end_time
  return shift1.start_time === shift2.start_time && 
         shift1.end_time === shift2.end_time
}

const hasSameShiftProperties = (shift1, shift2) => {
  // Simplified grouping logic - only check essential time-based properties
  // Since we're on the same row, resource/description/status don't matter for grouping
  return shift1.start_time === shift2.start_time &&
         shift1.end_time === shift2.end_time &&
         shift1.is_night_shift === shift2.is_night_shift
}

const getColumnIndex = (date) => {
  return props.dateColumns.findIndex(col => col.dateString === date)
}

// Enrich shift with row data (resource, project info, etc.)
const enrichShiftWithRowData = (shift) => {
  return {
    ...shift,
    resource_name: props.row.resourceName || props.row.resource,
    project_name: props.row.projectName || props.row.project,
    activity_name: props.row.activityName || props.row.activity,
    role_name: props.row.roleName || props.row.role
  }
}

// Event handlers
const handleResize = (resizeData) => {
  const { shift, originalDates, direction, columnsDelta, isComplete } = resizeData
  
  // Only apply changes when the resize is complete to avoid breaking mouse tracking
  if (!isComplete) {
    return // Don't modify data during drag - just let the visual feedback happen
  }
  
  if (direction === 'left') {
    // Shrinking from the left (removing days from start)
    const daysToRemove = Math.max(0, Math.min(Math.abs(columnsDelta), originalDates.length - 1))
    if (daysToRemove > 0) {
      const datesToRemove = originalDates.slice(0, daysToRemove)
      removeShiftsFromDates(datesToRemove, shift)
    }
  } else {
    // Extending/shrinking from the right
    if (columnsDelta > 0) {
      // Extending - add new shifts to the right
      const lastDate = originalDates[originalDates.length - 1]
      const newDates = generateConsecutiveDates(lastDate, columnsDelta)
      addShiftsToNewDates(newDates, shift)
    } else if (columnsDelta < 0) {
      // Shrinking from the right - remove days from end
      const daysToRemove = Math.min(Math.abs(columnsDelta), originalDates.length - 1)
      if (daysToRemove > 0) {
        const datesToRemove = originalDates.slice(-daysToRemove)
        removeShiftsFromDates(datesToRemove, shift)
      }
    }
  }
}

const handleDragStart = (dragData) => {
  // Simple drag start handler - no custom preview needed
  console.log('Drag started:', dragData)
}

const handleDragEnd = (dragData) => {
  // Simple drag end handler
  console.log('Drag ended:', dragData)
}

const handleDragMove = (dragData) => {
  // Handle moving the entire shift bar to a new position
  console.log('Drag move:', dragData)
  // TODO: Implement shift moving logic
}

const handleMoveShift = (moveData) => {
  const { shift, dates, newStartColumn, columnDelta } = moveData
  
  console.log('Moving shift:', { shift, dates, newStartColumn, columnDelta })
  
  // Calculate new dates based on the column delta
  const newDates = dates.map(date => {
    const originalDate = new Date(date)
    originalDate.setDate(originalDate.getDate() + columnDelta)
    return originalDate.toISOString().split('T')[0]
  })
  
  // Remove shift from original dates - match by shift properties, not just ID
  dates.forEach(date => {
    if (props.row.dailyEntries[date]) {
      const entries = Array.isArray(props.row.dailyEntries[date]) 
        ? props.row.dailyEntries[date] 
        : [props.row.dailyEntries[date]]
      
      // Filter out entries that match the shift being moved
      const filteredEntries = entries.filter(entry => {
        // Use the same simplified matching logic as grouping - focus on essential properties
        // This ensures API shifts are properly identified for removal
        return !(
          entry.start_time === shift.start_time &&
          entry.end_time === shift.end_time &&
          entry.is_night_shift === shift.is_night_shift
        )
      })
      
      if (filteredEntries.length === 0) {
        delete props.row.dailyEntries[date]
      } else if (filteredEntries.length === 1) {
        props.row.dailyEntries[date] = filteredEntries[0]
      } else {
        props.row.dailyEntries[date] = filteredEntries
      }
    }
  })
  
  // Add shift to new dates
  newDates.forEach(date => {
    const newShift = {
      ...shift,
      date: date,
      id: shift.id // Keep the same ID
    }
    
    if (!props.row.dailyEntries[date]) {
      props.row.dailyEntries[date] = newShift
    } else {
      // Handle multiple entries per day
      const existing = props.row.dailyEntries[date]
      if (Array.isArray(existing)) {
        existing.push(newShift)
      } else {
        props.row.dailyEntries[date] = [existing, newShift]
      }
    }
  })
  
  console.log('✅ Shift moved successfully from', dates, 'to', newDates)
}

const generateConsecutiveDates = (startDate, count) => {
  const dates = []
  const date = new Date(startDate)
  
  for (let i = 1; i <= count; i++) {
    date.setDate(date.getDate() + 1)
    dates.push(date.toISOString().split('T')[0])
  }
  
  return dates
}

const addShiftsToNewDates = (dates, templateShift) => {
  // Ensure the template shift has an ID - if not, generate one
  if (!templateShift.id) {
    templateShift.id = `shift-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    console.log('Generated ID for template shift:', templateShift.id)
  }
  
  console.log('Adding shifts to dates:', dates, 'with template ID:', templateShift.id)
  
  dates.forEach(date => {
    if (!props.row.dailyEntries[date]) {
      // Create new shift entry for this date - use the SAME ID as the template shift
      const newShift = {
        id: templateShift.id, // Use the same ID as the original shift
        date: date,
        hours: templateShift.hours,
        start_time: templateShift.start_time,
        end_time: templateShift.end_time,
        description: templateShift.description,
        status: templateShift.status || 'planned',
        is_night_shift: templateShift.is_night_shift,
        resource_name: templateShift.resource_name // Also copy resource_name
      }
      
      console.log('Created new shift for date', date, 'with ID:', newShift.id)
      props.row.dailyEntries[date] = newShift
    }
  })
}

const removeShiftsFromDates = (dates, templateShift) => {
  dates.forEach(date => {
    if (props.row.dailyEntries[date]) {
      // Remove shift entries that match the template
      const entries = Array.isArray(props.row.dailyEntries[date]) 
        ? props.row.dailyEntries[date] 
        : [props.row.dailyEntries[date]]
      
      const filteredEntries = entries.filter(entry => 
        !(entry.start_time === templateShift.start_time && 
          entry.end_time === templateShift.end_time)
      )
      
      if (filteredEntries.length === 0) {
        delete props.row.dailyEntries[date]
      } else if (filteredEntries.length === 1) {
        props.row.dailyEntries[date] = filteredEntries[0]
      } else {
        props.row.dailyEntries[date] = filteredEntries
      }
    }
  })
}
</script>

<style scoped>
.multi-day-shift-group {
  position: relative;
  width: 100%;
  height: 100%;
  pointer-events: none; /* Allow events to pass through to underlying cells */
}

/* Individual shift bars should still capture events */
.multi-day-shift-group :deep(.shift-bar) {
  pointer-events: auto;
}
</style>
