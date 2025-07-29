<template>
  <div :class="['scheduler-grid h-full', colors.bg.primary]">
    <!-- Grid Container -->
    <div :class="[
      'schedule-grid-container flex rounded-xl overflow-hidden',
      colors.border.primary,
      shadows.lg,
      'border backdrop-blur-sm'
    ]">
      <!-- Fixed Left Section -->
      <div :class="[
        'fixed-left-section flex-shrink-0 border-r',
        colors.border.primary,
        colors.gradients.secondary
      ]">
        <!-- Fixed Left Header -->
        <div :class="[
          'fixed-left-header flex border-b',
          colors.gradients.primary,
          colors.border.primary
        ]">
          <div :class="[
            'column-header project-activity-column flex items-center justify-center px-4 py-3',
            'text-sm font-semibold border-r',
            colors.text.primary,
            colors.border.primary
          ]">
            <Icon icon="lucide:folder" class="w-4 h-4 mr-2" />
            Project / Activity
          </div>
          <div :class="[
            'column-header role-column flex items-center justify-center px-4 py-3',
            'text-sm font-semibold border-r',
            colors.text.primary,
            colors.border.primary
          ]">
            <Icon icon="lucide:user-check" class="w-4 h-4 mr-2" />
            Role
          </div>
          <div :class="[
            'column-header resource-column flex items-center justify-center px-4 py-3',
            'text-sm font-semibold',
            colors.text.primary
          ]">
            <Icon icon="lucide:users" class="w-4 h-4 mr-2" />
            Resource
          </div>
        </div>
        
        <!-- Fixed Left Body -->
        <div class="fixed-left-body" ref="fixedLeftBody">
          <SchedulerRow
            v-for="(row, index) in scheduleRows"
            :key="row.id"
            :row="row"
            :row-index="index"
            :projects="projects"
            :resources="resources"
            :roles="roles"
            :is-fixed-columns="true"
            @update-row="handleRowUpdate"
            @delete-row="handleRowDelete"
          />
        </div>
      </div>
      
      <!-- Scrollable Right Section -->
      <div :class="['scrollable-right-section flex-1 overflow-hidden']">
        <!-- Scrollable Right Header -->
        <div :class="[
          'scrollable-right-header flex border-b',
          colors.gradients.primary,
          colors.border.primary
        ]">
          <div 
            v-for="(date, index) in dateColumns"
            :key="date.dateString"
            :class="[
              'date-column flex-shrink-0 flex flex-col items-center justify-center px-3 py-2',
              'text-sm border-r transition-all duration-200',
              colors.border.primary,
              date.isToday ? [
                'bg-gradient-to-b from-blue-500 to-indigo-600 text-white font-bold',
                'border-blue-400 shadow-lg transform scale-105'
              ] : date.isWeekend ? [
                'bg-gradient-to-b from-orange-100 to-orange-200 text-orange-800 font-medium',
                colors.text.secondary
              ] : [
                colors.text.primary,
                'hover:bg-opacity-50',
                colors.bg.hover
              ]
            ]"
          >
            <div :class="[
              'date-weekday text-xs font-medium',
              date.isToday ? 'text-blue-100' : ''
            ]">
              {{ date.weekday }}
            </div>
            <div :class="[
              'date-day text-sm',
              date.isToday ? 'text-white' : ''
            ]">
              {{ date.display }}
            </div>
            <!-- Today indicator -->
            <div 
              v-if="date.isToday"
              class="absolute bottom-1 w-2 h-2 bg-white rounded-full opacity-80"
            />
          </div>
        </div>
        
        <!-- Scrollable Right Body -->
        <div class="scrollable-right-body" ref="scrollableRightBody">
          <SchedulerRow
            v-for="(row, index) in scheduleRows"
            :key="row.id"
            :row="row"
            :row-index="index"
            :date-columns="dateColumns"
            :project-colors="projectColors"
            :is-fixed-columns="false"
            @create-entry="$emit('create-entry', $event)"
            @update-entry="$emit('update-entry', $event)"
            @delete-entry="$emit('delete-entry', $event)"
          />
        </div>
      </div>
    </div>

    <!-- Modern Add Row Section -->
    <div :class="[
      'add-row-section p-4 border-t',
      colors.border.primary,
      colors.gradients.secondary
    ]">
      <button
        :class="[
          'flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200',
          'border-2 border-dashed hover:border-solid',
          colors.border.secondary,
          colors.text.secondary,
          'hover:scale-105',
          colors.bg.hover,
          shadows.sm,
          isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
        ]"
        :disabled="isLoading"
        @click="$emit('add-row')"
      >
        <Icon icon="lucide:plus" class="w-4 h-4" />
        <span class="text-sm font-medium">Add New Row</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { format, addDays, isToday, isWeekend } from 'date-fns'
import { Icon } from '@iconify/vue'
import SchedulerRow from './SchedulerRow.vue'
import { useTheme } from './composables/useTheme'

// Composables
const { colors, shadows } = useTheme()

// Props
const props = defineProps({
  scheduleRows: {
    type: Array,
    default: () => []
  },
  dateRange: {
    type: Number,
    default: 30
  },
  currentStartDate: {
    type: String,
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
  isLoading: {
    type: Boolean,
    default: false
  }
})

// Emits
defineEmits(['create-entry', 'update-entry', 'delete-entry', 'add-row'])

// Refs
const fixedLeftBody = ref(null)
const scrollableRightBody = ref(null)

// Computed properties
const dateColumns = computed(() => {
  if (!props.currentStartDate) return []
  
  const columns = []
  const startDate = new Date(props.currentStartDate)
  
  for (let i = 0; i < props.dateRange; i++) {
    const date = addDays(startDate, i)
    const dateString = format(date, 'yyyy-MM-dd')
    
    columns.push({
      date: date,
      dateString: dateString,
      weekday: format(date, 'EEE'),
      display: format(date, 'MMM d'),
      isToday: isToday(date),
      isWeekend: isWeekend(date)
    })
  }
  
  return columns
})

// Methods
const handleRowUpdate = (rowIndex, updates) => {
  // Handle row updates (project, activity, resource selection)
  console.log('Row update:', rowIndex, updates)
}

const handleRowDelete = (rowIndex) => {
  // Handle row deletion
  console.log('Delete row:', rowIndex)
}

// Setup scroll synchronization
const setupScrollSynchronization = () => {
  if (!fixedLeftBody.value || !scrollableRightBody.value) return
  
  let isScrolling = false
  
  // Sync right section when left section scrolls
  const leftScrollHandler = () => {
    if (isScrolling) return
    isScrolling = true
    scrollableRightBody.value.scrollTop = fixedLeftBody.value.scrollTop
    setTimeout(() => { isScrolling = false }, 10)
  }
  
  // Sync left section when right section scrolls
  const rightScrollHandler = () => {
    if (isScrolling) return
    isScrolling = true
    fixedLeftBody.value.scrollTop = scrollableRightBody.value.scrollTop
    setTimeout(() => { isScrolling = false }, 10)
  }
  
  // Add scroll event listeners
  fixedLeftBody.value.addEventListener('scroll', leftScrollHandler)
  scrollableRightBody.value.addEventListener('scroll', rightScrollHandler)
  
  console.log('Scroll synchronization setup complete')
}

// Lifecycle
onMounted(async () => {
  await nextTick()
  setupScrollSynchronization()
})
</script>

<style scoped>
.scheduler-grid {
  @apply bg-white;
}

.schedule-grid-container {
  @apply flex border border-gray-200 rounded-lg overflow-hidden;
  min-height: 400px;
}

/* Fixed Left Section */
.fixed-left-section {
  @apply flex-shrink-0 border-r border-gray-200;
  width: 400px;
}

.fixed-left-header {
  @apply flex bg-gray-100 border-b border-gray-200;
  height: 60px;
}

.column-header {
  @apply flex items-center justify-center px-3 py-2 text-sm font-semibold text-gray-700 border-r border-gray-200;
}

.project-activity-column {
  width: 200px;
}

.role-column {
  width: 100px;
}

.resource-column {
  width: 100px;
}

.fixed-left-body {
  @apply overflow-y-auto;
  max-height: 500px;
}

/* Scrollable Right Section */
.scrollable-right-section {
  @apply flex-1 overflow-hidden;
}

.scrollable-right-header {
  @apply flex bg-gray-100 border-b border-gray-200;
  height: 60px;
}

.date-column {
  @apply flex-shrink-0 flex flex-col items-center justify-center px-2 py-1 text-sm border-r border-gray-200;
  width: 80px;
}

.date-column.today {
  @apply bg-gradient-to-b from-blue-100 to-blue-200 text-blue-800 font-bold border-blue-300;
  box-shadow: inset 0 2px 4px rgba(59, 130, 246, 0.1);
}

.date-column.weekend {
  @apply bg-gradient-to-b from-orange-50 to-orange-100 text-orange-700 font-medium;
}

.date-weekday {
  @apply text-xs font-medium;
}

.date-day {
  @apply text-sm;
}

.scrollable-right-body {
  @apply overflow-auto;
  max-height: 500px;
}

.add-row-section {
  @apply flex justify-start;
}
</style>
