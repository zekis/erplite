<template>
  <div class="scheduler-datatable-container">
    <!-- DataTable with custom styling -->
    <DataTable
      v-model:editingRows="editingRows"
      :value="tableData"
      editMode="row"
      dataKey="id"
      :scrollable="true"
      scrollHeight="calc(100vh - 200px)"
      :frozenColumns="frozenColumns"
      :resizableColumns="true"
      columnResizeMode="expand"
      :class="[
        'scheduler-table',
        colors.bg.card
      ]"
      @row-edit-save="onRowEditSave"
      @row-edit-cancel="onRowEditCancel"
    >
      <!-- Project/Activity Column (Frozen) -->
      <Column 
        field="projectActivity" 
        header="Project / Activity"
        :frozen="true"
        :style="{ width: '180px', minWidth: '180px' }"
        :sortable="false"
      >
        <template #body="{ data, field }">
          <ProjectHeader
            v-if="data.type === 'project-header'"
            :project-id="data.project"
            :project-name="data.projectName"
            :collapsed="data.collapsed || false"
            :schedule-rows="scheduleRows"
            :all-resources="resources"
            @toggle-collapse="handleToggleCollapse"
            @edit-project="handleEditProject"
            @view-project="handleViewProject"
            @add-row="handleAddProjectRow"
            @export-project="handleExportProject"
          />
          <div v-else class="activity-cell p-2">
            <FilterableDropdown
              v-if="!data.project"
              v-model="data.project"
              :options="projectOptions"
              type="project"
              placeholder="Select Project"
              @change="(event) => handleProjectChange(data, event)"
            />
            <FilterableDropdown
              v-else
              v-model="data.activity"
              :options="getActivityOptions(data.project)"
              type="activity"
              placeholder="Select Activity"
              @change="(event) => handleActivityChange(data, event)"
            />
          </div>
        </template>
      </Column>

      <!-- Role Column (Frozen) -->
      <Column 
        field="role" 
        header="Role"
        :frozen="true"
        :style="{ width: '100px', minWidth: '100px' }"
        :sortable="false"
      >
        <template #body="{ data }">
          <div v-if="data.type !== 'project-header' && data.project" class="role-cell p-2">
            <FilterableDropdown
              v-model="data.role"
              :options="roleOptions"
              type="role"
              placeholder="Role"
              @change="(event) => handleRoleChange(data, event)"
            />
          </div>
        </template>
      </Column>

      <!-- Resource Column (Frozen) -->
      <Column 
        field="resource" 
        header="Resource"
        :frozen="true"
        :style="{ width: '120px', minWidth: '120px' }"
        :sortable="false"
      >
        <template #body="{ data }">
          <div v-if="data.type !== 'project-header' && data.project" class="resource-cell p-2">
            <FilterableDropdown
              v-model="data.resource"
              :options="resourceOptionsWithTypes"
              type="resource"
              placeholder="Resource"
              @change="(event) => handleResourceChange(data, event)"
            />
          </div>
        </template>
      </Column>

      <!-- Dynamic Date Columns -->
      <Column
        v-for="dateColumn in dateColumns"
        :key="dateColumn.dateString"
        :field="`day_${dateColumn.dateString}`"
        :style="{ width: '80px', minWidth: '80px', maxWidth: '80px' }"
        :sortable="false"
      >
        <template #header>
          <div :class="[
            'date-header text-center p-2',
            dateColumn.isToday ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 font-semibold' : '',
            dateColumn.isWeekend ? 'bg-blue-50 dark:bg-blue-900/30' : ''
          ]">
            <div class="text-xs font-medium">{{ dateColumn.dayName }}</div>
            <div class="text-xs">{{ dateColumn.dayNumber }}</div>
          </div>
        </template>
        <template #body="{ data }">
          <DayCell
            :date="dateColumn.dateString"
            :date-info="dateColumn"
            :row="data"
            :row-index="data.id"
            :project-color="getProjectColor(data.project)"
            :entries="getDayEntries(data, dateColumn.dateString)"
            :is-interactive="data.type === 'activity-row' && data.project && data.activity"
            @create-entry="handleCreateEntry"
            @update-entry="handleUpdateEntry"
            @delete-entry="handleDeleteEntry"
          />
        </template>
      </Column>
    </DataTable>

    <!-- Add Row Button -->
    <div class="add-row-section p-4 border-t" :class="colors.border.primary">
      <Button
        @click="addNewRow"
        :class="[
          'add-row-btn',
          colors.bg.primary,
          colors.text.white
        ]"
        size="small"
        outlined
      >
        <Icon icon="lucide:plus" class="w-4 h-4 mr-2" />
        Add New Row
      </Button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { format, addDays } from 'date-fns'
import { Icon } from '@iconify/vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import DayCell from './DayCell.vue'
import FilterableDropdown from './FilterableDropdown.vue'
import ProjectHeader from './ProjectHeader.vue'
import { useTheme } from './composables/useTheme'

// Composables
const { colors } = useTheme()

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
const emit = defineEmits(['update-row', 'create-entry', 'update-entry', 'delete-entry', 'add-row'])

// State
const editingRows = ref([])
const frozenColumns = ref(3) // Project/Activity, Role, Resource

// Computed
const tableData = computed(() => {
  return props.scheduleRows.map(row => ({
    ...row,
    // Add computed fields for DataTable
    projectActivity: row.type === 'project-header' ? row.projectName : (row.activityName || 'Select Activity')
  }))
})

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

const projectOptions = computed(() => {
  return props.projects.map(project => ({
    label: project.project_name || project.name,
    value: project.name,
    project: project
  }))
})

const roleOptions = computed(() => {
  return props.roles.map(role => ({
    label: role.role_name || role.name,
    value: role.name,
    description: role.description,
    role: role
  }))
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

// Methods
const getActivityOptions = (projectName) => {
  if (!projectName) return []
  
  const project = props.projects.find(p => p.name === projectName)
  if (!project || !project.activities) return []
  
  return project.activities.map(activity => ({
    label: activity.activity_name || activity.name,
    value: activity.name,
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

const handleProjectChange = (row, event) => {
  const projectValue = event.value
  const project = props.projects.find(p => p.name === projectValue)
  
  const updates = {
    project: projectValue,
    projectName: project?.project_name || project?.name,
    activity: null,
    activityName: null
  }
  
  Object.assign(row, updates)
  emit('update-row', row.id, updates)
}

const handleActivityChange = (row, event) => {
  const activityValue = event.value
  const project = props.projects.find(p => p.name === row.project)
  const activity = project?.activities?.find(a => a.name === activityValue)
  
  const updates = {
    activity: activityValue,
    activityName: activity?.activity_name || activity?.name
  }
  
  Object.assign(row, updates)
  emit('update-row', row.id, updates)
}

const handleRoleChange = (row, event) => {
  const roleValue = event.value
  const role = roleOptions.value.find(r => r.value === roleValue)
  
  const updates = {
    role: roleValue,
    roleName: role?.label
  }
  
  Object.assign(row, updates)
  emit('update-row', row.id, updates)
}

const handleResourceChange = (row, event) => {
  const resourceValue = event.value
  const resource = props.resources.find(r => r.name === resourceValue)
  
  const updates = {
    resource: resourceValue,
    resourceName: resource?.resource_name || resource?.name
  }
  
  Object.assign(row, updates)
  emit('update-row', row.id, updates)
}

const handleCreateEntry = (data) => {
  emit('create-entry', data)
}

const handleUpdateEntry = (data) => {
  emit('update-entry', data)
}

const handleDeleteEntry = (data) => {
  emit('delete-entry', data)
}

const addNewRow = () => {
  emit('add-row')
}

// Project Header handlers
const handleToggleCollapse = (projectId) => {
  // Find and update the project header row
  const projectRow = props.scheduleRows.find(row => 
    row.type === 'project-header' && row.project === projectId
  )
  if (projectRow) {
    const updates = { collapsed: !projectRow.collapsed }
    emit('update-row', projectRow.id, updates)
  }
}

const handleEditProject = (projectId) => {
  // Navigate to ERP project edit page
  const project = props.projects.find(p => p.name === projectId)
  if (project) {
    // Open project in new tab/window
    window.open(`/app/project/${projectId}`, '_blank')
  }
}

const handleViewProject = (projectId) => {
  // Navigate to project details page
  const project = props.projects.find(p => p.name === projectId)
  if (project) {
    window.open(`/app/project/${projectId}`, '_blank')
  }
}

const handleAddProjectRow = (projectId) => {
  // Add a new schedule row for this project
  emit('add-row', { project: projectId })
}

const handleExportProject = (projectId) => {
  // Export project schedule data
  console.log('Exporting project:', projectId)
  // TODO: Implement project export functionality
}

const onRowEditSave = (event) => {
  // Handle row edit save if needed
  console.log('Row edit save:', event)
}

const onRowEditCancel = (event) => {
  // Handle row edit cancel if needed
  console.log('Row edit cancel:', event)
}
</script>

<style scoped>
.scheduler-datatable-container {
  @apply h-full flex flex-col;
}

.scheduler-table {
  @apply flex-1;
}

/* Custom DataTable styling */
:deep(.p-datatable) {
  @apply border-0;
}

:deep(.p-datatable-thead > tr > th) {
  @apply bg-gray-50 border-b border-gray-200 text-xs font-semibold text-gray-700 p-2;
}

:deep(.p-datatable-tbody > tr > td) {
  @apply border-b border-gray-100 p-0;
}

:deep(.p-datatable-tbody > tr:hover) {
  @apply bg-gray-50;
}

:deep(.p-datatable-frozen-column) {
  @apply bg-white border-r border-gray-200;
  z-index: 10 !important;
}

:deep(.p-datatable-scrollable-header-table) {
  z-index: 5 !important;
}

:deep(.p-datatable-scrollable-body-table) {
  z-index: 1 !important;
}

:deep(.p-datatable-frozen-column .p-column-header-content) {
  z-index: 15 !important;
}

.project-header-cell {
  @apply rounded-lg m-1;
}

/* Project header spanning across all frozen columns */
:deep(.p-datatable-tbody tr:has(.project-header-full-width)) {
  position: relative;
}

:deep(.p-datatable-tbody tr:has(.project-header-full-width) td:nth-child(1)) {
  position: relative;
  overflow: visible;
}

:deep(.p-datatable-tbody tr:has(.project-header-full-width) td:nth-child(2),
       .p-datatable-tbody tr:has(.project-header-full-width) td:nth-child(3)) {
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow: hidden;
}

:deep(.p-datatable-tbody tr:has(.project-header-full-width) td:nth-child(2) > *,
       .p-datatable-tbody tr:has(.project-header-full-width) td:nth-child(3) > *) {
  display: none !important;
}

/* Ensure the project header component spans full width */
:deep(.project-header-merged-cell) {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 400px !important; /* 180px + 100px + 120px */
  z-index: 10;
  margin: 0 !important;
}

.activity-cell,
.role-cell,
.resource-cell {
  @apply min-h-[50px] flex items-center;
}

.date-header {
  @apply rounded-lg m-1;
}

.add-row-section {
  @apply flex-shrink-0;
}

.add-row-btn {
  @apply flex items-center;
}
</style>
