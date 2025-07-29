<template>
  <div class="scheduler-row-wrapper">
    <!-- Project Header Row -->
    <ProjectHeaderRow
      v-if="row.type === 'project-header'"
      :project-id="row.project"
      :project-name="row.projectName"
      :collapsed="row.collapsed || false"
      :schedule-rows="allRows"
      :all-resources="resources"
      :date-columns="dateColumns"
      @toggle-collapse="$emit('toggle-collapse', $event)"
      @edit-project="$emit('edit-project', $event)"
      @view-project="$emit('view-project', $event)"
      @add-row="$emit('add-row', $event)"
      @export-project="$emit('export-project', $event)"
    />
    
    <!-- Activity Row -->
    <ActivityRow
      v-else
      :row="row"
      :projects="projects"
      :resources="resources"
      :roles="roles"
      :date-columns="dateColumns"
      :project-colors="projectColors"
      @update-row="$emit('update-row', $event)"
      @create-entry="$emit('create-entry', $event)"
      @update-entry="$emit('update-entry', $event)"
      @delete-entry="$emit('delete-entry', $event)"
    />
  </div>
</template>

<script setup>
import ProjectHeaderRow from './ProjectHeaderRow.vue'
import ActivityRow from './ActivityRow.vue'

// Props
const props = defineProps({
  row: {
    type: Object,
    required: true
  },
  allRows: {
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
  dateColumns: {
    type: Array,
    default: () => []
  }
})

// Emits
defineEmits([
  'toggle-collapse',
  'edit-project',
  'view-project', 
  'add-row',
  'export-project',
  'update-row',
  'create-entry',
  'update-entry',
  'delete-entry'
])
</script>

<style scoped>
.scheduler-row-wrapper {
  @apply w-full;
}
</style>
