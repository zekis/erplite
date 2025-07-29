<template>
  <div :class="[
    'project-header-merged-cell flex items-center justify-between p-3 font-semibold',
    colors.gradients.secondary,
    colors.text.primary,
    'project-header-full-width'
  ]">
    <!-- Left side: Project info -->
    <div class="project-info flex items-center">
      <button 
        @click="toggleCollapse"
        class="collapse-btn mr-2 p-1 rounded hover:bg-black hover:bg-opacity-10 transition-colors"
        :title="collapsed ? 'Expand project' : 'Collapse project'"
      >
        <Icon 
          :icon="collapsed ? 'lucide:chevron-right' : 'lucide:chevron-down'" 
          class="w-4 h-4" 
        />
      </button>
      <Icon icon="lucide:folder" class="w-4 h-4 mr-2" />
      <span class="project-name">{{ projectName }}</span>
      <div class="project-stats ml-4 flex items-center space-x-3 text-xs opacity-75">
        <span class="resource-count">
          <Icon icon="lucide:users" class="w-3 h-3 mr-1 inline" />
          {{ resourceCount }} resources
        </span>
        <span class="total-hours">
          <Icon icon="lucide:clock" class="w-3 h-3 mr-1 inline" />
          {{ totalHours }}h total
        </span>
        <span class="activity-count">
          <Icon icon="lucide:zap" class="w-3 h-3 mr-1 inline" />
          {{ activityCount }} activities
        </span>
      </div>
    </div>
    
    <!-- Right side: Action buttons -->
    <div class="project-actions flex items-center space-x-1">
      <button 
        @click="handleEditProject"
        class="action-btn p-1 rounded hover:bg-black hover:bg-opacity-10 transition-colors"
        title="Edit Project in ERP"
      >
        <Icon icon="lucide:edit" class="w-4 h-4" />
      </button>
      <button 
        @click="handleViewProject"
        class="action-btn p-1 rounded hover:bg-black hover:bg-opacity-10 transition-colors"
        title="View Project Details"
      >
        <Icon icon="lucide:external-link" class="w-4 h-4" />
      </button>
      <button 
        @click="handleAddRow"
        class="action-btn p-1 rounded hover:bg-black hover:bg-opacity-10 transition-colors"
        title="Add Schedule Row"
      >
        <Icon icon="lucide:plus" class="w-4 h-4" />
      </button>
      <button 
        @click="handleExportProject"
        class="action-btn p-1 rounded hover:bg-black hover:bg-opacity-10 transition-colors"
        title="Export Project Schedule"
      >
        <Icon icon="lucide:download" class="w-4 h-4" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useTheme } from './composables/useTheme'

// Composables
const { colors } = useTheme()

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
</script>

<style scoped>
.project-header-merged-cell {
  @apply rounded-lg;
  /* Positioned absolutely to span all three columns */
  position: absolute;
  top: 4px;
  left: 4px;
  right: 4px;
  bottom: 4px;
  width: calc(400px - 8px); /* 180px + 100px + 120px - margins */
  z-index: 15;
  margin: 0;
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
  @apply flex-1 min-w-0; /* Allow text to truncate if needed */
}

.project-name {
  @apply font-semibold truncate;
  max-width: 200px;
}

.project-stats {
  @apply hidden sm:flex; /* Hide on small screens */
}

.project-actions {
  @apply flex-shrink-0;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .project-stats {
    @apply hidden;
  }
  
  .project-name {
    max-width: 150px;
  }
}
</style>
