<template>
  <div class="project-header-row flex items-center w-full border-b bg-gradient-to-r from-gray-100 to-gray-200 dark:from-gray-700 dark:to-gray-800 text-gray-900 dark:text-white border-gray-200 dark:border-gray-700"
  :style="getDivisionColorStyle()">
    <!-- Project Info Section (spans where Project/Activity, Role, Resource columns would be) -->
    <div class="project-info-section flex items-center justify-between p-3 font-semibold" 
         :style="{ width: fixedColumnsWidth + 'px', minWidth: fixedColumnsWidth + 'px' }">
      <!-- Left side: Project info -->
      <div class="project-info flex items-center">
        <button 
          @click="toggleCollapse"
          class="collapse-btn mr-2 p-1 rounded transition-colors hover:bg-black hover:bg-opacity-10 dark:hover:bg-white dark:hover:bg-opacity-10"
          :title="collapsed ? 'Expand project' : 'Collapse project'"
        >
          <Icon 
            :icon="collapsed ? 'lucide:chevron-right' : 'lucide:chevron-down'" 
            class="w-4 h-4" 
          />
        </button>
        <div class="project-name-section">
          <div class="project-name font-medium text-sm">{{ projectName }}</div>
          <div v-if="projectType" class="project-type text-xs opacity-75 text-gray-600 dark:text-gray-300">
            {{ projectType }}
          </div>
        </div>
      </div>
      
      <!-- Right side: Project stats and action buttons -->
      <div class="project-actions flex items-center justify-end space-x-3 ml-auto">
        <!-- Project Statistics -->
        <div class="project-stats flex items-center space-x-3 text-xs opacity-75">
          <span class="resource-count flex items-center">
            <Icon icon="lucide:users" class="w-3 h-3 mr-1" />
            {{ resourceCount }}
          </span>
          <span class="total-hours flex items-center">
            <Icon icon="lucide:clock" class="w-3 h-3 mr-1" />
            {{ totalHours }}h
          </span>
          <span class="activity-count flex items-center">
            <Icon icon="lucide:zap" class="w-3 h-3 mr-1" />
            {{ activityCount }}
          </span>
        </div>
        
        <!-- Action Button -->
        <button 
          @click="handleViewProject"
          :class="[
            'action-btn p-1 rounded transition-colors',
            'hover:bg-black hover:bg-opacity-10 dark:hover:bg-white dark:hover:bg-opacity-10'
          ]"
          title="View Project Details"
        >
          <Icon icon="lucide:external-link" class="w-4 h-4" />
        </button>
      </div>
    </div>

    <!-- Date Columns Section -->
    <div class="calendar-row flex overflow-x-hidden">
      <div 
        v-for="dateColumn in dateColumns"
        :key="dateColumn.dateString"
        class="date-cell flex items-center justify-center text-xs font-medium opacity-50"
        style="width: 80px; min-width: 80px; max-width: 80px;"
      >
        {{ totalHoursForDate(dateColumn.dateString) }}h
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
// Composables removed - using direct Tailwind classes

// Props
const props = defineProps({
  projectId: {
    type: String,
    required: true
  },
  projectName: {
    type: String,
    required: true
  },
  projectType: {
    type: String,
    default: null
  },
  collapsed: {
    type: Boolean,
    default: false
  },
  scheduleRows: {
    type: Array,
    default: () => []
  },
  allResources: {
    type: Array,
    default: () => []
  },
  dateColumns: {
    type: Array,
    default: () => []
  },
  fixedColumnsWidth: {
    type: Number,
    default: 500
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
  },
  projectColors: {
    type: Object,
    default: () => ({})
  }
})

// Emits
const emit = defineEmits([
  'toggle-collapse',
  'edit-project', 
  'view-project',
  'add-row',
  'export-project'
])

// Computed
const resourceCount = computed(() => {
  const projectRows = props.scheduleRows.filter(row => 
    row.project === props.projectId && row.resource
  )
  const uniqueResources = new Set(projectRows.map(row => row.resource))
  return uniqueResources.size
})

const totalHours = computed(() => {
  const projectRows = props.scheduleRows.filter(row => 
    row.project === props.projectId && row.dailyEntries
  )
  
  let total = 0
  projectRows.forEach(row => {
    if (row.dailyEntries) {
      Object.values(row.dailyEntries).forEach(entry => {
        total += entry.hours || 0
      })
    }
  })
  
  return total
})

const activityCount = computed(() => {
  const projectRows = props.scheduleRows.filter(row => 
    row.project === props.projectId && row.activity
  )
  const uniqueActivities = new Set(projectRows.map(row => row.activity))
  return uniqueActivities.size
})

// Methods
const totalHoursForDate = (dateString) => {
  const projectRows = props.scheduleRows.filter(row => 
    row.project === props.projectId && row.dailyEntries && row.dailyEntries[dateString]
  )
  
  let total = 0
  projectRows.forEach(row => {
    const entry = row.dailyEntries[dateString]
    if (entry) {
      total += entry.hours || 0
    }
  })
  
  return total
}

const toggleCollapse = () => {
  emit('toggle-collapse', props.projectId)
}

const handleEditProject = () => {
  emit('edit-project', props.projectId)
}

const handleViewProject = () => {
  emit('view-project', props.projectId)
}

const handleAddRow = () => {
  emit('add-row', props.projectId)
}

const handleExportProject = () => {
  emit('export-project', props.projectId)
}

const getDivisionColorStyle = () => {
  if (!props.projectId) return {}
  
  const divisionColor = props.projectColors[props.projectId]
  
  if (!divisionColor || divisionColor === '#6b7280') return {}
  
  return {
    borderTop: `4px solid ${divisionColor} !important`,
    background: `linear-gradient(180deg, ${divisionColor}12 0%, transparent 100%)`
  }
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
</script>

<style scoped>
.project-header-row {
  @apply rounded-lg;
  min-height: 50px;
}

.collapse-btn,
.action-btn {
  @apply transition-all duration-200;
}

.collapse-btn:hover,
.action-btn:hover {
  @apply scale-110;
}

.project-info {
  @apply flex-1 min-w-0;
}

.project-name {
  @apply truncate;
}

.project-name-section {
  @apply flex-1 min-w-0;
  max-width: calc(200% - 60px); /* Reserve space for stats and action button */
}

.project-stats {
  @apply hidden sm:flex;
}

.project-actions {
  @apply flex-shrink-0;
}

.date-cell {
  @apply border-l p-2;
}

:deep(.date-cell) {
  border-left-color: var(--border-color);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .project-stats {
    @apply hidden;
  }
}

@media (max-width: 480px) {
  .project-name {
    max-width: 120px;
  }
}
</style>
