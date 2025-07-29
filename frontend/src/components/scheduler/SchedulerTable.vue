<template>
  <div class="scheduler-table-container">
    <!-- Header -->
    <div class="scheduler-header flex w-full border-b-2 border-gray-200 dark:border-gray-700">
      <!-- Fixed Columns Header -->
      <div 
        class="fixed-columns-header flex" 
        :style="{ width: fixedColumnsWidth + 'px', minWidth: fixedColumnsWidth + 'px' }"
      >
        <div class="header-cell border-r flex flex-col bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700" 
             :style="{ width: projectColumnWidth + 'px', minWidth: projectColumnWidth + 'px' }">
          <div class="font-semibold p-2 pb-1">Project / Activity</div>
          <div class="px-2 pb-2">
            <FilterableDropdown
              v-model="filters.project"
              :options="projectFilterOptions"
              type="project"
              placeholder="Filter proj/activities..."
              :allow-clear="true"
              @change="handleProjectFilter"
            />
          </div>
        </div>
        <div class="header-cell border-r flex flex-col bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700" 
             :style="{ width: roleColumnWidth + 'px', minWidth: roleColumnWidth + 'px' }">
          <div class="font-semibold p-2 pb-1">Role</div>
          <div class="px-2 pb-2">
            <FilterableDropdown
              v-model="filters.role"
              :options="roleFilterOptions"
              type="role"
              placeholder="Filter roles..."
              :allow-clear="true"
              @change="handleRoleFilter"
            />
          </div>
        </div>
        <div class="header-cell flex flex-col bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700" 
             :style="{ width: resourceColumnWidth + 'px', minWidth: resourceColumnWidth + 'px' }">
          <div class="font-semibold p-2 pb-1">Resource</div>
          <div class="px-2 pb-2">
            <FilterableDropdown
              v-model="filters.resource"
              :options="resourceFilterOptions"
              type="resource"
              placeholder="Filter resources..."
              :allow-clear="true"
              @change="handleResourceFilter"
            />
          </div>
        </div>
      </div>

      <!-- Resize Handle -->
      <div 
        class="resize-handle"
        :class="{ 'resizing': isResizing }"
        @mousedown="startResize"
        :title="'Drag to resize columns'"
      >
        <div class="resize-line"></div>
      </div>

      <!-- Scrollable Date Headers -->
      <div 
        ref="headerScrollContainer"
        class="date-headers-section flex overflow-x-auto flex-1"
        @scroll="handleHeaderScroll"
      >
        <div 
          v-for="dateColumn in dateColumns"
          :key="dateColumn.dateString"
          class="date-header-cell font-semibold p-2 border-l text-center"
          style="width: 80px; min-width: 80px; max-width: 80px;"
          :class="[
            'bg-gray-100 dark:bg-gray-800', 
            'border-gray-200 dark:border-gray-700',
            dateColumn.isToday ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' : '',
            dateColumn.isWeekend ? 'bg-blue-50 dark:bg-blue-900/30' : ''
          ]"
        >
          <div class="text-xs font-medium">{{ dateColumn.dayName }}</div>
          <div class="text-xs">{{ dateColumn.dayNumber }}</div>
        </div>
      </div>
    </div>

    <!-- Scrollable Body -->
    <div class="scheduler-body">
      <div class="scheduler-rows">
        <!-- Project Groups -->
        <ProjectGroup
          v-for="project in projectGroups"
          :key="project.id"
          :project-id="project.id"
          :project-name="project.name"
          :schedule-rows="filteredScheduleRows"
          :projects="projects"
          :all-resources="resources"
          :roles="roles"
          :project-colors="projectColors"
          :date-columns="dateColumns"
          :initial-collapsed="project.collapsed || false"
          :fixed-columns-width="fixedColumnsWidth"
          :project-column-width="projectColumnWidth"
          :role-column-width="roleColumnWidth"
          :resource-column-width="resourceColumnWidth"
          @toggle-collapse="handleToggleCollapse"
          @edit-project="handleEditProject"
          @view-project="handleViewProject"
          @add-row="handleAddProjectRow"
          @export-project="handleExportProject"
          @update-row="handleUpdateRow"
          @create-entry="handleCreateEntry"
          @update-entry="handleUpdateEntry"
          @delete-entry="handleDeleteEntry"
        />
        
        <!-- Standalone Activity Rows (rows without projects) -->
        <ActivityRow
          v-for="row in standaloneRows"
          :key="row.id"
          :row="row"
          :projects="projects"
          :resources="resources"
          :roles="roles"
          :date-columns="dateColumns"
          :project-colors="projectColors"
          @update-row="handleUpdateRow"
          @create-entry="handleCreateEntry"
          @update-entry="handleUpdateEntry"
          @delete-entry="handleDeleteEntry"
        />
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, onUnmounted } from 'vue'
import { format, addDays } from 'date-fns'
import ProjectGroup from './ProjectGroup.vue'
import ActivityRow from './ActivityRow.vue'
import FilterableDropdown from './FilterableDropdown.vue'
// Composables removed - using direct Tailwind classes

// Refs
const headerScrollContainer = ref(null)
const fixedColumnsWidth = ref(600)
const isResizing = ref(false)

// Filter state
const filters = ref({
  project: null,
  role: null,
  resource: null
})

// Constants
const MIN_FIXED_WIDTH = 400
const MAX_FIXED_WIDTH = 1200

// Props
const props = defineProps({
  scheduleRows: {
    type: Array,
    default: () => []
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
  currentStartDate: {
    type: String,
    required: true
  },
  dateRange: {
    type: Number,
    default: 30
  }
})

// Emits
const emit = defineEmits([
  'update-row', 
  'create-entry', 
  'update-entry', 
  'delete-entry', 
  'add-row'
])

// Computed
const dateColumns = computed(() => {
  const columns = []
  const startDate = new Date(props.currentStartDate)
  
  for (let i = 0; i < props.dateRange; i++) {
    const date = addDays(startDate, i)
    const dateString = format(date, 'yyyy-MM-dd')
    const dayName = format(date, 'EEE')
    const dayNumber = format(date, 'd')
    const isToday = format(new Date(), 'yyyy-MM-dd') === dateString
    const isWeekend = date.getDay() === 0 || date.getDay() === 6
    
    columns.push({
      dateString,
      dayName,
      dayNumber,
      isToday,
      isWeekend,
      date
    })
  }
  
  return columns
})

const filteredScheduleRows = computed(() => {
  let filtered = [...props.scheduleRows]
  
  // Apply project/activity filter
  if (filters.value.project) {
    // Check if the filter value is a project or activity
    const filterOption = projectFilterOptions.value.find(opt => opt.value === filters.value.project)
    
    if (filterOption?.type === 'project') {
      // Filter by project - show all rows for this project
      filtered = filtered.filter(row => 
        row.project === filters.value.project || row.type === 'project-header'
      )
    } else if (filterOption?.type === 'activity') {
      // Filter by activity - show only rows with this activity AND only the project that contains it
      const activityProject = filterOption.project?.name
      filtered = filtered.filter(row => {
        if (row.type === 'project-header') {
          // Only show project header for the project that contains this activity
          return row.project === activityProject
        }
        // Show only rows with the specific activity
        return row.activity === filters.value.project
      })
    }
  }
  
  // Apply role filter
  if (filters.value.role) {
    if (filters.value.role === '__no_role__') {
      // Show only rows with no role set
      filtered = filtered.filter(row => 
        !row.role || row.type === 'project-header'
      )
    } else {
      // Show only rows with specific role
      filtered = filtered.filter(row => 
        row.role === filters.value.role || row.type === 'project-header'
      )
    }
  }
  
  // Apply resource filter
  if (filters.value.resource) {
    if (filters.value.resource === '__no_resource__') {
      // Show only rows with no resource set
      filtered = filtered.filter(row => 
        !row.resource || row.type === 'project-header'
      )
    } else {
      // Show only rows with specific resource
      filtered = filtered.filter(row => 
        row.resource === filters.value.resource || row.type === 'project-header'
      )
    }
  }
  
  return filtered
})

const projectGroups = computed(() => {
  const projectsWithRows = new Set()
  filteredScheduleRows.value.forEach(row => {
    if (row.project && row.type !== 'project-header') {
      projectsWithRows.add(row.project)
    }
  })
  
  const groups = []
  projectsWithRows.forEach(projectId => {
    const project = props.projects.find(p => p.name === projectId)
    const projectHeaderRow = filteredScheduleRows.value.find(row => 
      row.type === 'project-header' && row.project === projectId
    )
    
    groups.push({
      id: projectId,
      name: project?.project_name || project?.name || projectId,
      collapsed: projectHeaderRow?.collapsed || false
    })
  })
  
  return groups
})

const standaloneRows = computed(() => {
  return filteredScheduleRows.value.filter(row => 
    !row.project && row.type !== 'project-header'
  )
})

// Column width calculations (proportional to total width)
const projectColumnWidth = computed(() => {
  return Math.floor(fixedColumnsWidth.value * 0.30) // 35% of total (reduced from 45%)
})

const roleColumnWidth = computed(() => {
  return Math.floor(fixedColumnsWidth.value * 0.30) // 32% of total (increased from 25%)
})

const resourceColumnWidth = computed(() => {
  return fixedColumnsWidth.value - projectColumnWidth.value - roleColumnWidth.value // Remaining space (~33%)
})

// Filter options
const projectFilterOptions = computed(() => {
  const projectOptions = []
  const activityOptions = []
  const uniqueProjects = new Set()
  const uniqueActivities = new Set()
  
  // Collect unique projects and activities
  props.scheduleRows.forEach(row => {
    if (row.project) {
      uniqueProjects.add(row.project)
    }
    if (row.activity) {
      uniqueActivities.add(row.activity)
    }
  })
  
  // Add project options
  Array.from(uniqueProjects).forEach(projectId => {
    const project = props.projects.find(p => p.name === projectId)
    projectOptions.push({
      label: project?.project_name || project?.name || projectId,
      value: projectId,
      type: 'project',
      project: project
    })
  })
  
  // Add activity options
  Array.from(uniqueActivities).forEach(activityId => {
    // Find the activity in the projects data
    let activityData = null
    let parentProject = null
    
    for (const project of props.projects) {
      if (project.activities) {
        const activity = project.activities.find(a => a.name === activityId)
        if (activity) {
          activityData = activity
          parentProject = project
          break
        }
      }
    }
    
    const activityLabel = activityData?.subject || activityData?.name || activityId
    const projectLabel = parentProject?.project_name || parentProject?.name || 'Unknown Project'
    
    activityOptions.push({
      label: `${activityLabel} (${projectLabel})`,
      value: activityId,
      type: 'activity',
      activity: activityData,
      project: parentProject
    })
  })
  
  // Sort each group separately
  projectOptions.sort((a, b) => a.label.localeCompare(b.label))
  activityOptions.sort((a, b) => a.label.localeCompare(b.label))
  
  // Combine with divider
  const options = []
  
  // Add projects
  if (projectOptions.length > 0) {
    options.push(...projectOptions)
  }
  
  // Add divider if both groups exist
  if (projectOptions.length > 0 && activityOptions.length > 0) {
    options.push({
      type: 'divider',
      label: 'divider',
      value: null
    })
  }
  
  // Add activities
  if (activityOptions.length > 0) {
    options.push(...activityOptions)
  }
  
  return options
})

const roleFilterOptions = computed(() => {
  const uniqueRoles = new Set()
  props.scheduleRows.forEach(row => {
    if (row.role) {
      uniqueRoles.add(row.role)
    }
  })
  
  const options = Array.from(uniqueRoles).map(roleId => {
    const role = props.roles.find(r => r.name === roleId)
    return {
      label: role?.role_name || role?.name || roleId,
      value: roleId,
      role: role
    }
  }).sort((a, b) => a.label.localeCompare(b.label))
  
  // Add "No role set" option at the beginning
  options.unshift({
    label: 'No role set',
    value: '__no_role__',
    description: 'Rows with no role assigned'
  })
  
  return options
})

const resourceFilterOptions = computed(() => {
  const uniqueResources = new Set()
  props.scheduleRows.forEach(row => {
    if (row.resource) {
      uniqueResources.add(row.resource)
    }
  })
  
  const options = Array.from(uniqueResources).map(resourceId => {
    const resource = props.resources.find(r => r.name === resourceId)
    return {
      label: resource?.resource_name || resource?.name || resourceId,
      value: resourceId,
      resource_type: resource?.resource_type,
      resource: resource
    }
  }).sort((a, b) => a.label.localeCompare(b.label))
  
  // Add "No resource set" option at the beginning
  options.unshift({
    label: 'No resource set',
    value: '__no_resource__',
    resource_type: 'None',
    description: 'Rows with no resource assigned'
  })
  
  return options
})

// Methods
const handleHeaderScroll = (event) => {
  const scrollLeft = event.target.scrollLeft
  
  // Sync all calendar row containers
  const calendarRows = document.querySelectorAll('.calendar-row')
  calendarRows.forEach(row => {
    if (row.scrollLeft !== scrollLeft) {
      row.scrollLeft = scrollLeft
    }
  })
}

const handleToggleCollapse = (projectId) => {
  const projectRow = props.scheduleRows.find(row => 
    row.type === 'project-header' && row.project === projectId
  )
  if (projectRow) {
    const updates = { collapsed: !projectRow.collapsed }
    emit('update-row', projectRow.id, updates)
  }
}

const handleEditProject = (projectId) => {
  window.open(`/app/project/${projectId}`, '_blank')
}

const handleViewProject = (projectId) => {
  window.open(`/app/project/${projectId}`, '_blank')
}

const handleAddProjectRow = (projectId) => {
  // Use the project-specific add function instead of generic add-row
  emit('add-project-row', projectId)
}

const handleExportProject = (projectId) => {
  console.log('Export project:', projectId)
}

const handleUpdateRow = (rowId, updates) => {
  emit('update-row', rowId, updates)
}

const handleCreateEntry = (entryData) => {
  emit('create-entry', entryData)
}

const handleUpdateEntry = (entryId, updates) => {
  emit('update-entry', entryId, updates)
}

const handleDeleteEntry = (entryId) => {
  emit('delete-entry', entryId)
}

// Filter handlers
const handleProjectFilter = (event) => {
  console.log('Project filter changed:', event)
  // TODO: Implement filtering logic
  // This could emit an event to parent or filter the displayed rows
}

const handleRoleFilter = (event) => {
  console.log('Role filter changed:', event)
  // TODO: Implement filtering logic
}

const handleResourceFilter = (event) => {
  console.log('Resource filter changed:', event)
  // TODO: Implement filtering logic
}

// Resize functionality
const startResize = (event) => {
  event.preventDefault()
  isResizing.value = true
  
  const startX = event.clientX
  const startWidth = fixedColumnsWidth.value
  
  const handleMouseMove = (moveEvent) => {
    const deltaX = moveEvent.clientX - startX
    const newWidth = Math.max(MIN_FIXED_WIDTH, Math.min(MAX_FIXED_WIDTH, startWidth + deltaX))
    fixedColumnsWidth.value = newWidth
  }
  
  const handleMouseUp = () => {
    isResizing.value = false
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
  
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}


// Setup scroll synchronization
onMounted(() => {
  nextTick(() => {
    // Listen for scroll events on calendar rows and sync with header
    const observer = new MutationObserver(() => {
      const calendarRows = document.querySelectorAll('.calendar-row')
      calendarRows.forEach(row => {
        row.addEventListener('scroll', (event) => {
          const scrollLeft = event.target.scrollLeft
          
          // Sync header
          if (headerScrollContainer.value && headerScrollContainer.value.scrollLeft !== scrollLeft) {
            headerScrollContainer.value.scrollLeft = scrollLeft
          }
          
          // Sync other calendar rows
          calendarRows.forEach(otherRow => {
            if (otherRow !== event.target && otherRow.scrollLeft !== scrollLeft) {
              otherRow.scrollLeft = scrollLeft
            }
          })
        })
      })
    })
    
    observer.observe(document.body, { childList: true, subtree: true })
  })
})
</script>

<style scoped>
.scheduler-table-container {
  @apply flex-1 flex flex-col overflow-hidden;
}

.scheduler-header {
  @apply flex-shrink-0;
}

.scheduler-body {
  @apply flex-1 overflow-y-auto;
}

.date-headers-section::-webkit-scrollbar {
  height: 8px;
}

.date-headers-section::-webkit-scrollbar-track {
  @apply bg-gray-100 dark:bg-gray-800;
}

.date-headers-section::-webkit-scrollbar-thumb {
  @apply bg-gray-400 dark:bg-gray-600 rounded;
}

.date-headers-section::-webkit-scrollbar-thumb:hover {
  @apply bg-gray-500;
}

/* Resize Handle Styles */
.resize-handle {
  @apply relative flex items-center justify-center cursor-col-resize;
  width: 8px;
  height: 60px; /* Fixed height instead of 100% */
  background: transparent;
  transition: background-color 0.2s ease;
}

.resize-handle:hover {
  @apply bg-blue-100 dark:bg-blue-900;
}

.resize-handle.resizing {
  @apply bg-blue-200 dark:bg-blue-800;
}

.resize-line {
  @apply bg-gray-400 dark:bg-gray-600;
  width: 2px;
  height: 60%;
  border-radius: 1px;
  transition: all 0.2s ease;
}

.resize-handle:hover .resize-line {
  @apply bg-blue-500 dark:bg-blue-400;
  width: 3px;
}

.resize-handle.resizing .resize-line {
  @apply bg-blue-600 dark:bg-blue-300;
  width: 3px;
  height: 80%;
}
</style>
