<template>
  <div class="scheduler-app h-screen w-full overflow-hidden transition-all duration-300 flex flex-col bg-white dark:bg-gray-900">
    <!-- Header with User Menu and Theme Toggle -->
    <div class="flex items-center justify-between p-4 border-b bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700">
      <!-- Left side: App Title -->
      <div class="flex items-center space-x-3">
        <Icon icon="lucide:calendar" class="w-6 h-6 text-gray-900 dark:text-white" />
        <h1 class="text-lg font-semibold text-gray-900 dark:text-white">
          Project Scheduler
        </h1>
      </div>

      <!-- Right side: User Menu and Theme Toggle -->
      <div class="flex items-center space-x-3">
        <!-- Theme Toggle -->
        <button
          @click="toggleTheme"
          class="p-2 rounded-lg transition-all duration-200 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white hover:scale-105 shadow-sm"
          :title="isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'"
        >
          <Icon 
            :icon="isDark ? 'lucide:sun' : 'lucide:moon'" 
            class="w-4 h-4" 
          />
        </button>

        <!-- User Menu -->
        <UserMenu 
          :current-user="currentUser"
          @profile="handleUserProfile"
          @settings="handleUserSettings"
          @help="handleUserHelp"
        />
      </div>
    </div>

    <!-- Toolbar -->
    <SchedulerToolbar 
      :current-date-range="currentDateRange"
      :is-loading="isLoading"
      @navigate-date="handleDateNavigation"
      @refresh="refreshData"
      @export="exportSchedule"
    />

    <!-- Main Scheduler Table -->
    <SchedulerTable 
      :schedule-rows="scheduleRows"
      :current-start-date="currentStartDate"
      :date-range="dateRange"
      :projects="projects"
      :resources="resources"
      :roles="roles"
      :project-colors="projectColors"
      @create-entry="handleCreateEntry"
      @update-entry="handleUpdateEntry"
      @delete-entry="handleDeleteEntry"
      @update-row="handleUpdateRow"
      @add-row="addNewRow"
      @add-project-row="addProjectRow"
    />

    <!-- Modern Loading Overlay -->
    <div v-if="isLoading" class="absolute inset-0 flex items-center justify-center z-50 backdrop-blur-sm bg-white/80 dark:bg-gray-900/80">
      <div class="text-center p-8 rounded-2xl bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 shadow-xl border border-gray-200 dark:border-gray-700">
        <div class="relative mb-6">
          <div class="w-16 h-16 rounded-full border-4 border-t-blue-600 border-r-transparent border-b-transparent border-l-transparent mx-auto animate-spin"></div>
          <div class="absolute inset-0 w-16 h-16 rounded-full border-4 border-t-transparent border-r-indigo-400 border-b-transparent border-l-transparent mx-auto animate-spin" style="animation-delay: 150ms;"></div>
        </div>
        <h3 class="text-lg font-semibold mb-2 text-gray-900 dark:text-white">
          Loading Scheduler
        </h3>
        <p class="text-sm text-gray-600 dark:text-gray-300">
          Fetching your schedule data...
        </p>
      </div>
    </div>

    <!-- Toast Notifications - positioned at bottom -->
    <Toast position="bottom-right" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import { format, addDays } from 'date-fns'
import { Icon } from '@iconify/vue'
import SchedulerToolbar from './SchedulerToolbar.vue'
import SchedulerTable from './SchedulerTable.vue'
import UserMenu from './UserMenu.vue'
import { useSchedulerData } from './composables/useSchedulerData'
import { useSchedulerAPI } from './composables/useSchedulerAPI'

const toast = useToast()

// Mock current user data (in production, this would come from Frappe session)
const currentUser = ref({
  full_name: 'Administrator',
  email: 'admin@example.com',
  user_image: null,
  role: 'System Manager'
})

// Composables
const { 
  scheduleRows, 
  projects, 
  resources, 
  roles,
  projectColors,
  currentStartDate,
  dateRange,
  loadInitialData,
  addScheduleRow,
  addProjectActivityRow
} = useSchedulerData()

const { 
  loadSchedulerData, 
  createScheduleEntry, 
  updateScheduleEntry, 
  deleteScheduleEntry,
  isLoading 
} = useSchedulerAPI()

// Theme functionality - using direct Tailwind classes
const isDark = ref(false)

const toggleTheme = () => {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }
}

const initializeTheme = () => {
  const savedTheme = localStorage.getItem('theme')
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  
  if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else {
    isDark.value = false
    document.documentElement.classList.remove('dark')
  }
}

// Computed properties
const currentDateRange = computed(() => {
  if (!currentStartDate.value) return 'Loading...'
  
  const start = new Date(currentStartDate.value)
  const end = addDays(start, dateRange.value - 1)
  
  return `${format(start, 'MMM d, yyyy')} - ${format(end, 'MMM d, yyyy')}`
})

// Methods
const handleDateNavigation = (days) => {
  const newDate = addDays(new Date(currentStartDate.value), days)
  currentStartDate.value = format(newDate, 'yyyy-MM-dd')
  refreshData()
}

const refreshData = async () => {
  try {
    await loadSchedulerData(currentStartDate.value, dateRange.value)
    showToast('Data refreshed successfully!', 'success')
  } catch (error) {
    showToast('Failed to refresh data', 'error')
  }
}

const exportSchedule = () => {
  showToast('Export functionality coming soon!', 'info')
}

const handleCreateEntry = async (entryData) => {
  try {
    await createScheduleEntry(entryData)
    await refreshData()
    showToast('Schedule entry created successfully!', 'success')
  } catch (error) {
    showToast('Failed to create entry', 'error')
  }
}

const handleUpdateEntry = async (entryId, updates) => {
  try {
    await updateScheduleEntry(entryId, updates)
    await refreshData()
    showToast('Schedule entry updated successfully!', 'success')
  } catch (error) {
    showToast('Failed to update entry', 'error')
  }
}

const handleDeleteEntry = async (entryId) => {
  try {
    await deleteScheduleEntry(entryId)
    await refreshData()
    showToast('Schedule entry deleted successfully!', 'success')
  } catch (error) {
    showToast('Failed to delete entry', 'error')
  }
}

const handleUpdateRow = (rowId, updates) => {
  // Update the row data in the scheduleRows
  const rowIndex = scheduleRows.value.findIndex(row => row.id === rowId)
  if (rowIndex !== -1) {
    Object.assign(scheduleRows.value[rowIndex], updates)
  }
}

const addNewRow = () => {
  addScheduleRow()
}

const addProjectRow = (projectId) => {
  addProjectActivityRow(projectId)
}

const showToast = (message, severity = 'info') => {
  toast.add({
    severity,
    summary: severity.charAt(0).toUpperCase() + severity.slice(1),
    detail: message,
    life: 3000
  })
}

// User menu handlers
const handleUserProfile = () => {
  // Navigate to user profile page
  window.open('/app/user-profile', '_blank')
}

const handleUserSettings = () => {
  // Navigate to user settings
  window.open('/app/user', '_blank')
}

const handleUserHelp = () => {
  // Open help documentation
  window.open('https://docs.erpnext.com', '_blank')
}

// Lifecycle
onMounted(async () => {
  initializeTheme()
  loadInitialData()
  await refreshData()
})
</script>

<style scoped>
.scheduler-app {
  position: relative;
  min-height: 600px;
}
</style>
