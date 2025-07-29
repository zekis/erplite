<template>
  <div v-if="isVisible" class="shift-popup-overlay fixed inset-0 z-50 flex items-center justify-center">
    <!-- Backdrop -->
    <div 
      class="absolute inset-0 bg-black bg-opacity-50 backdrop-blur-sm"
      @click="handleCancel"
    ></div>
    
    <!-- Popup Content -->
    <div class="shift-popup relative bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 max-w-md w-full mx-4">
      <!-- Header -->
      <div class="popup-header p-6 border-b border-gray-300 dark:border-gray-600">
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
            Create Shift
          </h3>
          <button 
            @click="handleCancel"
            class="p-1 rounded-lg transition-colors text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <Icon icon="lucide:x" class="w-5 h-5" />
          </button>
        </div>
        
        <!-- Selected Date Range -->
        <div class="mt-2 text-sm text-gray-600 dark:text-gray-300">
          {{ formatDateRange() }}
        </div>
      </div>

      <!-- Form Content -->
      <div class="popup-content p-6 space-y-4">
        <!-- Start Time -->
        <div class="form-group">
          <label class="block text-sm font-medium mb-2 text-gray-900 dark:text-white">
            Start Time
          </label>
          <input
            v-model="formData.startTime"
            type="time"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg transition-colors bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
          />
        </div>

        <!-- End Time -->
        <div class="form-group">
          <label class="block text-sm font-medium mb-2 text-gray-900 dark:text-white">
            End Time
          </label>
          <input
            v-model="formData.endTime"
            type="time"
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg transition-colors bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
          />
        </div>

        <!-- Calculated Hours -->
        <div class="calculated-hours">
          <div class="text-sm text-gray-600 dark:text-gray-300">
            Total Hours: <span class="font-medium">{{ calculatedHours }}h</span>
          </div>
        </div>

        <!-- Night Shift Checkbox -->
        <div class="form-group">
          <label class="flex items-center space-x-2 cursor-pointer">
            <input
              v-model="formData.isNightShift"
              type="checkbox"
              class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <span class="text-sm font-medium text-gray-900 dark:text-white">
              Night Shift
            </span>
          </label>
          <div class="text-xs mt-1 text-gray-600 dark:text-gray-300">
            Shift spans across midnight
          </div>
        </div>

        <!-- Notes -->
        <div class="form-group">
          <label class="block text-sm font-medium mb-2 text-gray-900 dark:text-white">
            Notes (Optional)
          </label>
          <textarea
            v-model="formData.notes"
            rows="3"
            placeholder="Add any notes about this shift..."
            class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg transition-colors resize-none bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
          ></textarea>
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="popup-footer p-6 border-t border-gray-300 dark:border-gray-600 flex justify-end space-x-3">
        <button
          @click="handleCancel"
          class="px-4 py-2 text-sm font-medium rounded-lg transition-colors text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600"
        >
          Cancel
        </button>
        <button
          @click="handleCreate"
          :disabled="!isFormValid"
          class="px-4 py-2 text-sm font-medium rounded-lg transition-colors bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed focus:ring-2 focus:ring-blue-200"
        >
          Create Shift
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { format, parseISO } from 'date-fns'
import { Icon } from '@iconify/vue'
// Composables removed - using direct Tailwind classes

// Props
const props = defineProps({
  isVisible: {
    type: Boolean,
    default: false
  },
  selectedDates: {
    type: Array,
    default: () => []
  },
  rowData: {
    type: Object,
    default: () => ({})
  }
})

// Emits
const emit = defineEmits(['create', 'cancel'])

// Form data
const formData = ref({
  startTime: '09:00',
  endTime: '17:00',
  notes: '',
  isNightShift: false
})

// Computed
const calculatedHours = computed(() => {
  if (!formData.value.startTime || !formData.value.endTime) return 0
  
  const start = new Date(`2000-01-01T${formData.value.startTime}:00`)
  const end = new Date(`2000-01-01T${formData.value.endTime}:00`)
  
  let diff = end - start
  
  // Handle night shift (end time is next day)
  if (formData.value.isNightShift && end <= start) {
    diff = (24 * 60 * 60 * 1000) - (start - end)
  } else if (end <= start) {
    // Regular shift but end is before start (assume next day)
    diff = (24 * 60 * 60 * 1000) + diff
  }
  
  return Math.round(diff / (1000 * 60 * 60) * 10) / 10 // Round to 1 decimal
})

const isFormValid = computed(() => {
  return formData.value.startTime && 
         formData.value.endTime && 
         calculatedHours.value > 0 &&
         props.selectedDates.length > 0
})

// Methods
const formatDateRange = () => {
  if (!props.selectedDates.length) return ''
  
  if (props.selectedDates.length === 1) {
    return format(parseISO(props.selectedDates[0]), 'MMM d, yyyy')
  }
  
  const sortedDates = [...props.selectedDates].sort()
  const startDate = format(parseISO(sortedDates[0]), 'MMM d')
  const endDate = format(parseISO(sortedDates[sortedDates.length - 1]), 'MMM d, yyyy')
  
  return `${startDate} - ${endDate} (${props.selectedDates.length} days)`
}

const handleCreate = () => {
  if (!isFormValid.value) return
  
  const shiftData = {
    dates: props.selectedDates,
    startTime: formData.value.startTime,
    endTime: formData.value.endTime,
    hours: calculatedHours.value,
    notes: formData.value.notes,
    isNightShift: formData.value.isNightShift,
    rowData: props.rowData
  }
  
  emit('create', shiftData)
  resetForm()
}

const handleCancel = () => {
  emit('cancel')
  resetForm()
}

const resetForm = () => {
  formData.value = {
    startTime: '09:00',
    endTime: '17:00',
    notes: '',
    isNightShift: false
  }
}

// Watch for night shift changes to adjust default times
watch(() => formData.value.isNightShift, (isNightShift) => {
  if (isNightShift) {
    // Default night shift times
    formData.value.startTime = '22:00'
    formData.value.endTime = '06:00'
  } else {
    // Default day shift times
    formData.value.startTime = '09:00'
    formData.value.endTime = '17:00'
  }
})
</script>

<style scoped>
.shift-popup-overlay {
  animation: fadeIn 0.2s ease-out;
}

.shift-popup {
  animation: slideIn 0.2s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideIn {
  from { 
    opacity: 0; 
    transform: translateY(-20px) scale(0.95); 
  }
  to { 
    opacity: 1; 
    transform: translateY(0) scale(1); 
  }
}

/* Form styling */
input[type="time"]::-webkit-calendar-picker-indicator {
  filter: invert(0.5);
}

.dark input[type="time"]::-webkit-calendar-picker-indicator {
  filter: invert(0.8);
}

input:focus, textarea:focus {
  outline: none;
}

/* Checkbox styling */
input[type="checkbox"] {
  @apply rounded border-gray-300 text-blue-600 focus:ring-blue-500 focus:ring-2;
}
</style>
