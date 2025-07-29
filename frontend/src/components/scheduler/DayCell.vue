<template>
  <div class="day-cell-container" style="width: 80px; min-width: 80px; max-width: 80px;">
    <!-- Project Header Cell (special case) -->
    <div 
      v-if="row.type === 'project-header'"
      class="project-header-cell relative flex-shrink-0 border-r min-h-[64px] flex flex-col justify-center items-center border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800"
      style="width: 80px; min-width: 80px; max-width: 80px;"
    >
      <div class="project-total text-xs font-medium text-gray-600 dark:text-gray-300">
        {{ getProjectTotal() }}
      </div>
    </div>

    <!-- Empty Day Cell (for creating new entries) -->
    <EmptyDayCell
      v-else-if="!hasEntries && isInteractive"
      :date="date"
      :date-info="dateInfo"
      :row="row"
      :row-index="rowIndex"
      :project-color="projectColor"
      @create-entry="$emit('create-entry', $event)"
      @show-context-menu="handleShowContextMenu"
    />

    <!-- Empty cell when entries exist (shift bars handle all display) -->
    <EmptyDayCell
      v-else-if="hasEntries"
      :date="date"
      :date-info="dateInfo"
      :row="row"
      :row-index="rowIndex"
      :project-color="projectColor"
      @create-entry="$emit('create-entry', $event)"
      @show-context-menu="handleShowContextMenu"
    />

    <!-- Inactive Cell (when row is not interactive) -->
    <div 
      v-else
      class="inactive-cell relative flex-shrink-0 border-r min-h-[64px] flex flex-col justify-center items-center border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-700 opacity-60"
      style="width: 80px; min-width: 80px; max-width: 80px;"
    >
      <!-- Empty inactive cell -->
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EmptyDayCell from './EmptyDayCell.vue'

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
  },
  entries: {
    type: Array,
    default: () => []
  },
  isInteractive: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['create-entry', 'update-entry', 'delete-entry', 'show-context-menu', 'show-notes'])

// Computed properties
const hasEntries = computed(() => {
  return props.entries && props.entries.length > 0
})

// Methods
const handleMoveEntry = (moveData) => {
  // Handle moving entries between cells
  emit('update-entry', {
    entryId: moveData.entryId,
    fromDate: moveData.fromDate,
    toDate: moveData.toDate,
    updates: {
      schedule_date: moveData.toDate
    }
  })
}

const handleShowContextMenu = (selectedDates, position) => {
  // Handle context menu from EmptyDayCell (both single click and drag selection)
  console.log('🎯 Step 2 - DayCell forwarding to ActivityRow:', { selectedDates, position })
  emit('show-context-menu', selectedDates, position)
}

const handleEntryContextMenu = (contextData) => {
  // Handle right-click context menu for entries
  // This could show different options like edit, delete, copy, etc.
  console.log('Entry context menu:', contextData)
  
  // For now, just emit the show-context-menu event
  // In the future, we could have a separate entry context menu
  emit('show-context-menu', [contextData.date], contextData.position)
}

const getProjectTotal = () => {
  // Calculate total hours for project on this date
  // This would need to be calculated from all activity rows for this project
  return '0h'
}

const formatEntryDisplay = (entry) => {
  // Format entry for display in the cell
  if (entry.hours) {
    return `${entry.hours}h`
  }
  if (entry.start_time && entry.end_time) {
    return `${entry.start_time}-${entry.end_time}`
  }
  return 'h'
}

const handleEntryClick = () => {
  // Handle clicking on an entry
  if (props.entries[0]) {
    emit('show-notes', {
      shift: props.entries[0],
      date: props.date
    })
  }
}

const handleEntryRightClick = (event) => {
  event.preventDefault()
  handleEntryContextMenu({
    date: props.date,
    position: { x: event.clientX, y: event.clientY }
  })
}
</script>

<style scoped>
.day-cell-container {
  @apply relative;
}

.project-header-cell {
  @apply relative flex-shrink-0 border-r border-gray-200 min-h-[50px] flex flex-col justify-center items-center;
  width: 80px;
}

.inactive-cell {
  @apply relative flex-shrink-0 border-r border-gray-200 min-h-[50px] flex flex-col justify-center items-center;
  width: 80px;
  background-color: #f9fafb;
  opacity: 0.6;
}

.project-total {
  @apply text-xs text-gray-600 font-medium;
}
</style>
