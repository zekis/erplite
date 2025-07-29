<template>
  <div class="multi-day-shift-group w-full h-full">
    <!-- Unified shift bars for all shifts (single or multi-day) -->
    <ShiftBar
      v-for="group in shiftGroups"
      :key="group.id"
      :shift="group.shift"
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
    
    // Find consecutive shifts with same time range
    const consecutiveShifts = [shift]
    processed.add(index)
    
    // Look ahead for consecutive days with same time range
    for (let i = index + 1; i < allShifts.value.length; i++) {
      const nextShift = allShifts.value[i]
      const lastShift = consecutiveShifts[consecutiveShifts.length - 1]
      
      // Check if next day and same time range
      if (isNextDay(lastShift.date, nextShift.date) && 
          hasSameTimeRange(lastShift, nextShift)) {
        consecutiveShifts.push(nextShift)
        processed.add(i)
      } else {
        break
      }
    }
    
    // Create shift bar for any shift (1+ days)
    if (consecutiveShifts.length >= 1) {
      const dates = consecutiveShifts.map(s => s.date)
      const startColumn = getColumnIndex(dates[0])
      
      if (startColumn !== -1) {
        groups.push({
          id: `group-${shift.date}-${dates.length}`,
          shift: shift,
          dates: dates,
          startColumn: startColumn
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

const getColumnIndex = (date) => {
  return props.dateColumns.findIndex(col => col.dateString === date)
}

// Event handlers
const handleResize = (resizeData) => {
  const { shift, originalDates, direction, columnsDelta } = resizeData
  
  if (direction === 'left') {
    // Shrinking from the left (removing days from start)
    const daysToRemove = Math.max(0, Math.min(columnsDelta, originalDates.length - 1))
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

const handleDragMove = (dragData) => {
  // Handle moving the entire shift bar to a new position
  console.log('Drag move:', dragData)
  // TODO: Implement shift moving logic
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
  dates.forEach(date => {
    if (!props.row.dailyEntries[date]) {
      // Create new shift entry for this date
      const newShift = {
        id: `temp-${Date.now()}-${Math.random()}`,
        date: date,
        hours: templateShift.hours,
        start_time: templateShift.start_time,
        end_time: templateShift.end_time,
        description: templateShift.description,
        status: templateShift.status || 'planned',
        is_night_shift: templateShift.is_night_shift
      }
      
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
