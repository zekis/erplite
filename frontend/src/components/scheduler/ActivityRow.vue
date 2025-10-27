<template>
  <div class="activity-row-container w-full">
    <!-- Main Row -->
    <div :class="[
      'activity-row flex items-center w-full border-b bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700',
      {
        'row-disabled': !isRowActive
      }
    ]"
    :style="getDivisionColorStyle()">
      <!-- Tools Column -->
      <div class="tools-column flex items-center justify-center" style="width: 40px; min-width: 40px;">
        <!-- Delete Row Button -->
        <button
          v-if="canDeleteRow"
          @click="handleDeleteRow"
          :class="[
            'delete-row-btn p-1 rounded text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20',
            'transition-all duration-200'
          ]"
          title="Archive Row"
        >
          <Icon icon="lucide:trash-2" class="w-3 h-3" />
        </button>
        <!-- Future tool icons can be added here -->
      </div>

      <!-- Project/Activity Column -->
      <div class="activity-column" :style="{ width: projectColumnWidth + 'px', minWidth: projectColumnWidth + 'px' }">
        <FilterableDropdown
          v-if="!row.project"
          v-model="row.project"
          :options="projectOptions"
          type="project"
          placeholder="Select Project"
          @change="handleProjectChange"
        />
        <FilterableDropdown
          v-else
          v-model="row.activity"
          :options="getActivityOptions(row.project)"
          type="activity"
          placeholder="Select Activity"
          @change="handleActivityChange"
        />
      </div>

      <!-- Role Column -->
      <div class="role-column" :style="{ width: roleColumnWidth + 'px', minWidth: roleColumnWidth + 'px' }">
        <FilterableDropdown
          v-if="row.project"
          v-model="row.role"
          :options="roleOptions"
          type="role"
          placeholder="Role"
          :disabled="!row.activity"
          @change="handleRoleChange"
        />
      </div>

      <!-- Resource Column -->
      <div class="resource-column" :style="{ width: resourceColumnWidth + 'px', minWidth: resourceColumnWidth + 'px' }">
        <FilterableDropdown
          v-if="row.project"
          v-model="row.resource"
          :options="resourceOptionsWithTypes"
          type="resource"
          placeholder="Resource"
          :disabled="!row.activity"
          @change="handleResourceChange"
        />
      </div>

      <!-- Date Columns Grid with Shift Bars -->
    <div class="calendar-row relative flex overflow-x-hidden">
      <!-- Grid Cells (Base Layer) -->
      <div 
        v-for="dateColumn in dateColumns"
        :key="dateColumn.dateString"
        class="date-cell relative z-10"
        style="width: 80px; min-width: 80px; max-width: 80px;"
      >
        <DayCell
          :date="dateColumn.dateString"
          :date-info="dateColumn"
          :row="row"
          :row-index="row.id"
          :project-color="getProjectColor(row.project)"
          :entries="getDayEntries(row, dateColumn.dateString)"
          :is-interactive="row.project && row.activity"
          @create-entry="$emit('create-entry', $event)"
          @update-entry="$emit('update-entry', $event)"
          @delete-entry="$emit('delete-entry', $event)"
          @show-context-menu="showContextMenu"
          @show-notes="handleShowNotes"
          @move-shift="handleMoveShift"
        />
      </div>
      
      <!-- Shift Bars (Overlay Layer) -->
      <div class="shift-bars-overlay absolute inset-0 pointer-events-none z-20">
        <MultiDayShiftGroup
          :row="row"
          :date-columns="dateColumns"
          :project-color="getProjectColor(row.project)"
          :column-width="80"
          @edit-shift="handleEditShift"
          @delete-shift="handleDeleteShift"
          @show-notes="handleShowNotes"
          @click-shift="handleClickShift"
          @navigate-to-start="$emit('navigate-to-start', $event)"
        />
      </div>
    </div>
    </div>

    <!-- Context Menu -->
    <ContextMenu
      :is-visible="contextMenu.isVisible"
      :position="contextMenu.position"
      :selected-dates="contextMenu.selectedDates"
      :row-data="row"
      @create-shift="handleCreateShift"
      @quick-template="handleQuickTemplate"
      @close="closeContextMenu"
    />

    <!-- Shift Creation Popup -->
    <ShiftCreationPopup
      :is-visible="shiftPopup.isVisible"
      :selected-dates="shiftPopup.selectedDates"
      :row-data="row"
      @create="handleShiftCreate"
      @cancel="closeShiftPopup"
    />

    <!-- Drag Tooltip -->
    <DragTooltip
      :is-visible="dragTooltip.isVisible"
      :position="dragTooltip.position"
      :selected-dates="dragTooltip.selectedDates"
    />

    <!-- Notes Edit Dialog -->
    <NotesEditDialog
      :visible="notesDialog.isVisible"
      :shift="notesDialog.shift"
      :dates="notesDialog.dates"
      @save="handleNotesSave"
      @close="closeNotesDialog"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import FilterableDropdown from './FilterableDropdown.vue'
import DayCell from './DayCell.vue'
import ContextMenu from './ContextMenu.vue'
import ShiftCreationPopup from './ShiftCreationPopup.vue'
import DragTooltip from './DragTooltip.vue'
import NotesEditDialog from './NotesEditDialog.vue'
import MultiDayShiftGroup from './MultiDayShiftGroup.vue'
import { useDragDrop } from './composables/useDragDrop'

// Composables
const { dragTooltip } = useDragDrop()

// Props
const props = defineProps({
  row: {
    type: Object,
    required: true
  },
  projects: {
    type: Array,
    default: () => []
  },
  resources: {
    type: Array,
    default: () => []
  },
  roles: {
    type: Array,
    default: () => []
  },
  projectColors: {
    type: Object,
    default: () => ({})
  },
  dateColumns: {
    type: Array,
    default: () => []
  },
  fixedColumnsWidth: {
    type: Number,
    default: 400
  },
  projectColumnWidth: {
    type: Number,
    default: 180
  },
  roleColumnWidth: {
    type: Number,
    default: 100
  },
  resourceColumnWidth: {
    type: Number,
    default: 120
  }
})

// Emits
const emit = defineEmits([
  'update-row',
  'create-entry',
  'update-entry',
  'delete-entry',
  'delete-row',
  'navigate-to-start'
])

// State for context menu and shift popup
const contextMenu = ref({
  isVisible: false,
  position: { x: 0, y: 0 },
  selectedDates: []
})

const shiftPopup = ref({
  isVisible: false,
  selectedDates: []
})

const notesDialog = ref({
  isVisible: false,
  shift: null,
  dates: []
})


// Computed
const projectOptions = computed(() => {
  return props.projects.map(project => ({
    label: project.project_name || project.name,
    value: project.name,
    project: project
  }))
})

const roleOptions = computed(() => {
  const options = props.roles.map(role => ({
    label: role.role_name || role.name,
    value: role.name,
    description: role.description,
    role: role
  }))
  
  // Add "No role" option at the beginning
  options.unshift({
    label: 'No role',
    value: null,
    description: 'No role assigned',
    role: null
  })
  
  return options
})

const resourceOptionsWithTypes = computed(() => {
  return props.resources.map(resource => ({
    label: resource.resource_name || resource.name,
    value: resource.name,
    resource_type: resource.resource_type,
    available_capacity: resource.available_capacity || 0,
    description: resource.resource_type,
    resource: resource
  }))
})

const isRowActive = computed(() => {
  return props.row.project && props.row.activity
})

const canDeleteRow = computed(() => {
  // Show delete button for rows that have some data (project or activity selected)
  // but don't show for completely empty rows
  return props.row.project || props.row.activity || props.row.resource || props.row.role
})

// Methods
const getActivityOptions = (projectName) => {
  if (!projectName) return []
  
  const project = props.projects.find(p => p.name === projectName)
  if (!project || !project.activities) return []
  
  return project.activities.map(activity => ({
    label: activity.activity_name || activity.name,
    value: activity.name,
    description: activity.priority ? `Priority: ${activity.priority}` : 'No priority set',
    activity: activity
  }))
}

const getProjectColor = (projectName) => {
  return props.projectColors[projectName] || '#6b7280'
}

const getDayEntries = (row, dateString) => {
  if (!row.dailyEntries) return []
  
  const entry = row.dailyEntries[dateString]
  if (!entry) return []
  
  return [entry]
}

const handleProjectChange = (event) => {
  const projectValue = event.value
  const project = props.projects.find(p => p.name === projectValue)
  
  const updates = {
    project: projectValue,
    projectName: project?.project_name || project?.name,
    activity: null,
    activityName: null
  }
  
  Object.assign(props.row, updates)
  emit('update-row', props.row.id, updates)
}

const handleRowScroll = (event) => {
  // Sync scroll with header and other rows
  const scrollLeft = event.target.scrollLeft
  
  // Find header scroll container
  const headerScrollContainer = document.querySelector('.date-headers-section')
  if (headerScrollContainer && headerScrollContainer.scrollLeft !== scrollLeft) {
    headerScrollContainer.scrollLeft = scrollLeft
  }
  
  // Sync with other row date sections
  const dateColumnSections = document.querySelectorAll('.date-columns-section')
  dateColumnSections.forEach(section => {
    if (section !== event.target && section.scrollLeft !== scrollLeft) {
      section.scrollLeft = scrollLeft
    }
  })
}

const handleActivityChange = (event) => {
  const activityValue = event.value
  const project = props.projects.find(p => p.name === props.row.project)
  const activity = project?.activities?.find(a => a.name === activityValue)
  
  const updates = {
    activity: activityValue,
    activityName: activity?.activity_name || activity?.name
  }
  
  Object.assign(props.row, updates)
  emit('update-row', props.row.id, updates)
}

const handleRoleChange = (event) => {
  const roleValue = event.value
  const role = roleOptions.value.find(r => r.value === roleValue)
  
  const updates = {
    role: roleValue,
    roleName: role?.label
  }
  
  Object.assign(props.row, updates)
  emit('update-row', props.row.id, updates)
}

const handleResourceChange = (event) => {
  const resourceValue = event.value
  const resource = props.resources.find(r => r.name === resourceValue)
  
  const updates = {
    resource: resourceValue,
    resourceName: resource?.resource_name || resource?.name
  }
  
  Object.assign(props.row, updates)
  emit('update-row', props.row.id, updates)
}

// Context menu and shift creation handlers
const showContextMenu = (selectedDates, position) => {
  console.log('🎯 Step 3 - ActivityRow received:', { selectedDates, position })
  
  // Convert Proxy Array to regular array to ensure Vue reactivity works
  const regularArray = Array.isArray(selectedDates) ? [...selectedDates] : selectedDates
  
  console.log('🎯 Step 4 - ActivityRow converted array:', { regularArray })
  
  // Ensure position is within viewport bounds
  const adjustedPosition = {
    x: Math.min(position.x, window.innerWidth - 200), // Leave space for menu width
    y: Math.min(position.y, window.innerHeight - 300) // Leave space for menu height
  }
  
  contextMenu.value = {
    isVisible: true,
    position: adjustedPosition,
    selectedDates: regularArray
  }
  
  console.log('🎯 Step 5 - ActivityRow set contextMenu:', contextMenu.value)
}

const closeContextMenu = () => {
  contextMenu.value.isVisible = false
}

const handleCreateShift = () => {
  shiftPopup.value = {
    isVisible: true,
    selectedDates: contextMenu.value.selectedDates
  }
}

const handleShiftCreate = (shiftData) => {
  // Create entries for all selected dates using the shift data
  shiftData.dates.forEach(date => {
    const entryData = {
      id: `temp-${Date.now()}-${Math.random()}`, // Temporary ID for frontend
      date: date,
      hours: shiftData.hours,
      start_time: shiftData.startTime,
      end_time: shiftData.endTime,
      description: shiftData.notes,
      status: 'planned',
      is_night_shift: shiftData.isNightShift
    }
    
    // For now, just add to local row data instead of emitting to backend
    handleLocalEntryCreation(entryData)
  })
  
  closeShiftPopup()
}

const handleQuickTemplate = (templateData) => {
  // Create entries for all selected dates using the template
  templateData.dates.forEach(date => {
    const entryData = {
      id: `temp-${Date.now()}-${Math.random()}`, // Temporary ID for frontend
      date: date,
      hours: templateData.template.hours,
      start_time: templateData.template.startTime,
      end_time: templateData.template.endTime,
      description: templateData.template.notes,
      status: templateData.template.isLeave ? 'leave' : 'planned',
      is_night_shift: templateData.template.isNightShift
    }
    
    // For now, just add to local row data instead of emitting to backend
    handleLocalEntryCreation(entryData)
  })
}


const handleLocalEntryCreation = (entryData) => {
  // Add entry to local row data for immediate UI feedback
  if (!props.row.dailyEntries) {
    props.row.dailyEntries = {}
  }
  
  // Add the entry to the specific date
  if (!props.row.dailyEntries[entryData.date]) {
    props.row.dailyEntries[entryData.date] = []
  }
  
  // If dailyEntries[date] is not an array, make it one
  if (!Array.isArray(props.row.dailyEntries[entryData.date])) {
    props.row.dailyEntries[entryData.date] = [props.row.dailyEntries[entryData.date]]
  }
  
  props.row.dailyEntries[entryData.date].push(entryData)
  
  // Show success toast
  console.log('✅ Entry created locally:', entryData)
  
  // TODO: Later we can emit to backend here
  // emit('create-entry', entryData)
}

const closeShiftPopup = () => {
  shiftPopup.value.isVisible = false
}

const handleNotesSave = (data) => {
  // Update the shift with new notes and tags
  const { shift, dates } = data
  
  // Find and update the entry in the row data
  dates.forEach(date => {
    if (props.row.dailyEntries && props.row.dailyEntries[date]) {
      const entries = Array.isArray(props.row.dailyEntries[date]) 
        ? props.row.dailyEntries[date] 
        : [props.row.dailyEntries[date]]
      
      const entryIndex = entries.findIndex(entry => entry.id === shift.id)
      if (entryIndex !== -1) {
        entries[entryIndex] = { ...entries[entryIndex], ...shift }
      }
    }
  })
  
  console.log('✅ Notes saved for shift:', shift)
  // TODO: Later we can emit to backend here
  // emit('update-entry', { shift, dates })
}

const handleShowNotes = (shift) => {
  // Open notes dialog for the selected shift
  // Handle both old format (with data object) and new format (direct shift)
  let shiftData, dates
  
  if (shift && shift.shift && shift.date) {
    // Old format: { shift, date }
    shiftData = shift.shift
    dates = [shift.date]
  } else {
    // New format: direct shift object
    shiftData = shift
    dates = [shift.date] // Use the date from the shift itself
  }
  
  notesDialog.value = {
    isVisible: true,
    shift: shiftData,
    dates: dates
  }
}

const handleEditShift = (shift) => {
  // Handle editing a shift from the multi-day bar
  console.log('Edit shift:', shift)
  // TODO: Open edit dialog or emit to parent
  emit('update-entry', { shift })
}

const handleDeleteShift = (shift) => {
  // Handle deleting a shift from the multi-day bar
  console.log('Delete shift:', shift)
  
  // Remove from local row data
  if (props.row.dailyEntries && shift.date) {
    const entries = props.row.dailyEntries[shift.date]
    if (Array.isArray(entries)) {
      const index = entries.findIndex(entry => entry.id === shift.id)
      if (index !== -1) {
        entries.splice(index, 1)
        if (entries.length === 0) {
          delete props.row.dailyEntries[shift.date]
        }
      }
    } else if (entries && entries.id === shift.id) {
      delete props.row.dailyEntries[shift.date]
    }
  }
  
  // TODO: Later emit to backend
  // emit('delete-entry', { shift })
}

const handleClickShift = (shift) => {
  // Handle clicking on a shift bar
  console.log('Shift clicked:', shift)
  // Could be used for selection or quick actions
}

const closeNotesDialog = () => {
  notesDialog.value.isVisible = false
  notesDialog.value.shift = null
  notesDialog.value.dates = []
}

const handleMoveShift = (moveData) => {
  console.log('🔄 Handling shift move with replacement:', moveData)
  
  const { shift, originalDates, newStartDate, targetDates, replaceExisting } = moveData
  
  if (replaceExisting) {
    // First, remove any existing shifts on the target dates
    targetDates.forEach(date => {
      if (props.row.dailyEntries && props.row.dailyEntries[date]) {
        console.log(`🗑️ Replacing existing shift on ${date}`)
        delete props.row.dailyEntries[date]
      }
    })
  }
  
  // Remove the original shift from its original dates (if moving within same row)
  if (originalDates && moveData.sourceRowId === props.row.id) {
    originalDates.forEach(date => {
      if (props.row.dailyEntries && props.row.dailyEntries[date]) {
        const entries = props.row.dailyEntries[date]
        if (Array.isArray(entries)) {
          const index = entries.findIndex(entry => entry.id === shift.id)
          if (index !== -1) {
            entries.splice(index, 1)
            if (entries.length === 0) {
              delete props.row.dailyEntries[date]
            }
          }
        } else if (entries && entries.id === shift.id) {
          delete props.row.dailyEntries[date]
        }
      }
    })
  }
  
  // Generate a single ID for the entire multi-day shift to keep it grouped
  const multiDayShiftId = shift.id || `temp-${Date.now()}-${Math.random()}`
  
  // Add the shift to the new target dates - ALL with the SAME ID to maintain grouping
  targetDates.forEach((date, index) => {
    const newShift = {
      ...shift,
      id: multiDayShiftId, // Use the SAME ID for all dates to maintain multi-day grouping
      date: date
    }
    
    // Initialize dailyEntries if needed
    if (!props.row.dailyEntries) {
      props.row.dailyEntries = {}
    }
    
    // Add the entry directly (not as array) since we want single entries per date
    props.row.dailyEntries[date] = newShift
    console.log(`✅ Added moved shift to ${date} with ID ${multiDayShiftId}:`, newShift)
  })
  
  console.log('✅ Multi-day shift move with replacement completed - all dates have same ID:', multiDayShiftId)
}

const handleDeleteRow = () => {
  // Emit delete-row event to parent component
  // The parent will handle the actual archiving/deletion logic
  emit('delete-row', props.row.id)
}

const getDivisionColorStyle = () => {
  if (!props.row.project) return {}
  
  const divisionColor = getProjectColor(props.row.project)
  if (!divisionColor || divisionColor === '#6b7280') return {}
  
  return {
    borderLeft: `4px solid ${divisionColor}`,
    background: `linear-gradient(90deg, ${divisionColor}08 0%, transparent 100%)`
  }
}

// Mouse down handler - only dismiss on new interactions, not drag completion
const handleMouseDown = (event) => {
  if (contextMenu.value.isVisible) {
    // Only close if mouse down is outside context menu
    const contextMenuElement = event.target.closest('.context-menu')
    if (!contextMenuElement) {
      closeContextMenu()
    }
  }
}

// Lifecycle hooks
onMounted(() => {
  document.addEventListener('mousedown', handleMouseDown)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', handleMouseDown)
})
</script>

<style scoped>
.activity-row {
  min-height: 50px;
  max-height: 50px;
  overflow: visible;
}

.activity-row.row-disabled {
  @apply bg-gray-50/30 dark:bg-gray-700/40;
}

.activity-row.row-disabled .calendar-row {
  @apply opacity-10 pointer-events-none;
}

.activity-column,
.role-column,
.resource-column {
  @apply border-r border-gray-200 dark:border-gray-600 flex items-center;
}

.date-cell {
  @apply border-l border-gray-200 dark:border-gray-600;
}

.delete-row-btn {
  @apply opacity-0 group-hover:opacity-100 transition-opacity duration-200;
}

.activity-row:hover .delete-row-btn {
  @apply opacity-100;
}
</style>
