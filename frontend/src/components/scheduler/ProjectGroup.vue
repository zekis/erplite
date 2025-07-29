<template>
  <div class="project-group">
    <!-- Project Header Row -->
    <ProjectHeaderRow
      :project-id="projectId"
      :project-name="projectName"
      :project-type="projectType"
      :collapsed="collapsed"
      :schedule-rows="scheduleRows"
      :all-resources="allResources"
      :date-columns="dateColumns"
      :project-colors="projectColors"
      :fixed-columns-width="fixedColumnsWidth"
      :project-column-width="projectColumnWidth"
      :role-column-width="roleColumnWidth"
      :resource-column-width="resourceColumnWidth"
      @toggle-collapse="handleToggleCollapse"
      @edit-project="handleEditProject"
      @view-project="handleViewProject"
      @add-row="handleAddRow"
      @export-project="handleExportProject"
    />
    
    <!-- Activity Rows (collapsible) -->
    <div v-if="!collapsed" class="activity-rows">
      <ActivityRow
        v-for="activityRow in activityRows"
        :key="activityRow.id"
        :row="activityRow"
        :projects="projects"
        :resources="allResources"
        :roles="roles"
        :date-columns="dateColumns"
        :project-colors="projectColors"
        :fixed-columns-width="fixedColumnsWidth"
        :project-column-width="projectColumnWidth"
        :role-column-width="roleColumnWidth"
        :resource-column-width="resourceColumnWidth"
        @update-row="$emit('update-row', $event)"
        @create-entry="$emit('create-entry', $event)"
        @update-entry="$emit('update-entry', $event)"
        @delete-entry="$emit('delete-entry', $event)"
      />
      
      <!-- Add Activity Row Button (when expanded) -->
      <div class="add-activity-row p-2 ml-4" v-if="!collapsed">
        <button 
          @click="addActivityRow"
          class="add-activity-btn flex items-center text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <Icon icon="lucide:plus" class="w-3 h-3 mr-1" />
          Add Activity Row
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import ProjectHeaderRow from './ProjectHeaderRow.vue'
import ActivityRow from './ActivityRow.vue'

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
  scheduleRows: {
    type: Array,
    default: () => []
  },
  projects: {
    type: Array,
    default: () => []
  },
  allResources: {
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
  initialCollapsed: {
    type: Boolean,
    default: false
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
  'edit-project',
  'view-project',
  'add-row',
  'export-project',
  'update-row',
  'create-entry',
  'update-entry',
  'delete-entry',
  'toggle-collapse'
])

// Computed
const collapsed = computed(() => {
  const projectHeaderRow = props.scheduleRows.find(row => 
    row.type === 'project-header' && row.project === props.projectId
  )
  return projectHeaderRow?.collapsed || props.initialCollapsed
})

const activityRows = computed(() => {
  return props.scheduleRows.filter(row => 
    row.project === props.projectId && row.type !== 'project-header'
  )
})

const projectType = computed(() => {
  const project = props.projects.find(p => p.name === props.projectId)
  return project?.work_type || project?.project_type || project?.type || null
})

// Methods
const handleToggleCollapse = () => {
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

const addActivityRow = () => {
  emit('add-row', props.projectId)
}
</script>

<style scoped>
.project-group {
  @apply mb-1;
}

.activity-rows {
  @apply transition-all duration-200;
}

.add-activity-row {
  @apply border-l-2 border-gray-200;
}

.add-activity-btn {
  @apply p-2 rounded hover:bg-gray-50 transition-all duration-200;
}

.add-activity-btn:hover {
  @apply scale-105;
}
</style>
