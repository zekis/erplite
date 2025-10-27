<template>
  <!-- Modal Overlay -->
  <div 
    v-if="isVisible"
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50"
    @click.self="handleClose"
  >
    <!-- Modal Dialog -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
      <!-- Header -->
      <div class="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
        <h2 class="text-xl font-semibold text-gray-900 dark:text-white">Edit Shift Notes</h2>
        <button
          @click="handleClose"
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
        >
          <Icon icon="lucide:x" class="w-6 h-6" />
        </button>
      </div>

      <!-- Content -->
      <div class="p-6 space-y-4">
        <!-- Shift Info -->
        <div v-if="shift" class="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600">
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
              {{ formatTimeRange(shift.start_time, shift.end_time) }}
            </h3>
            <span :class="[
              'px-2 py-1 text-xs font-medium rounded-full',
              shift.is_night_shift 
                ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
            ]">
              {{ shift.is_night_shift ? 'Night Shift' : 'Day Shift' }}
            </span>
          </div>
          <div class="text-sm text-gray-600 dark:text-gray-400">
            {{ formatDuration(shift.hours) }} • {{ formatDates(dates) }}
          </div>
        </div>

        <!-- Notes Editor -->
        <div class="space-y-2">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Notes
          </label>
          <textarea 
            v-model="localNotes"
            placeholder="Add notes about this shift..."
            rows="6"
            class="w-full p-3 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:focus:ring-blue-400 dark:focus:border-blue-400 resize-none"
          ></textarea>
          <div class="text-xs text-gray-500 dark:text-gray-400">
            {{ localNotes.length }}/500 characters
          </div>
        </div>

        <!-- Quick Notes Templates -->
        <div class="space-y-2">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Quick Templates
          </label>
          <div class="grid grid-cols-2 gap-2">
            <button
              v-for="template in noteTemplates"
              :key="template.id"
              @click="addTemplate(template.text)"
              class="p-2 text-left text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors border border-gray-200 dark:border-gray-600"
            >
              {{ template.label }}
            </button>
          </div>
        </div>

        <!-- Tags -->
        <div class="space-y-2">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Tags
          </label>
          <div class="flex flex-wrap gap-2 mb-2">
            <span
              v-for="tag in selectedTags"
              :key="tag"
              class="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full dark:bg-blue-900 dark:text-blue-200"
            >
              {{ tag }}
              <button
                @click="removeTag(tag)"
                class="ml-1 text-blue-600 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-100"
              >
                <Icon icon="lucide:x" class="w-3 h-3" />
              </button>
            </span>
          </div>
          <div class="flex flex-wrap gap-1">
            <button
              v-for="tag in filteredAvailableTags"
              :key="tag"
              @click="addTag(tag)"
              class="px-2 py-1 text-xs text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-full transition-colors border border-gray-200 dark:border-gray-600"
            >
              + {{ tag }}
            </button>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex justify-between items-center p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700 rounded-b-lg">
        <div class="flex space-x-2">
          <button 
            @click="clearNotes"
            :disabled="!localNotes && selectedTags.length === 0"
            class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-600 border border-gray-300 dark:border-gray-500 rounded-md hover:bg-gray-50 dark:hover:bg-gray-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Clear
          </button>
        </div>
        <div class="flex space-x-2">
          <button 
            @click="handleClose"
            class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-600 border border-gray-300 dark:border-gray-500 rounded-md hover:bg-gray-50 dark:hover:bg-gray-500 transition-colors"
          >
            Cancel
          </button>
          <button 
            @click="handleSave"
            class="px-4 py-2 text-sm font-medium text-white bg-blue-600 dark:bg-blue-500 border border-blue-600 dark:border-blue-500 rounded-md hover:bg-blue-700 dark:hover:bg-blue-600 transition-colors"
          >
            Save Notes
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Icon } from '@iconify/vue'

// Props
const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  shift: {
    type: Object,
    default: () => ({})
  },
  dates: {
    type: Array,
    default: () => []
  }
})

// Emits
const emit = defineEmits(['update:visible', 'save', 'close'])

// Local state
const isVisible = ref(props.visible)
const localNotes = ref('')
const selectedTags = ref([])

// Watch for prop changes
watch(() => props.visible, (newVal) => {
  isVisible.value = newVal
  if (newVal && props.shift) {
    localNotes.value = props.shift.notes || props.shift.description || ''
    selectedTags.value = props.shift.tags || []
  }
})

watch(isVisible, (newVal) => {
  emit('update:visible', newVal)
})

// Note templates
const noteTemplates = ref([
  { id: 1, label: 'Training Required', text: 'Training required for this shift' },
  { id: 2, label: 'Special Equipment', text: 'Special equipment needed' },
  { id: 3, label: 'Client Meeting', text: 'Client meeting scheduled' },
  { id: 4, label: 'Overtime Approved', text: 'Overtime pre-approved' },
  { id: 5, label: 'Remote Work', text: 'Remote work approved' },
  { id: 6, label: 'On-Call', text: 'On-call availability required' }
])

// Available tags
const availableTags = ref([
  'Important', 'Training', 'Meeting', 'Overtime', 'Remote', 'On-Call', 
  'Equipment', 'Travel', 'Client', 'Urgent', 'Flexible', 'Break'
])

// Computed
const filteredAvailableTags = computed(() => {
  return availableTags.value.filter(tag => !selectedTags.value.includes(tag))
})

// Methods
const formatTimeRange = (startTime, endTime) => {
  if (!startTime || !endTime) return 'No time'
  
  const formatTime = (time) => {
    const [hours, minutes] = time.split(':')
    const hour = parseInt(hours)
    const ampm = hour >= 12 ? 'PM' : 'AM'
    const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour
    return `${displayHour}:${minutes}${ampm}`
  }
  
  return `${formatTime(startTime)} - ${formatTime(endTime)}`
}

const formatDuration = (hours) => {
  if (!hours) return '0h'
  
  if (hours < 1) {
    return `${Math.round(hours * 60)}m`
  }
  
  const wholeHours = Math.floor(hours)
  const minutes = Math.round((hours - wholeHours) * 60)
  
  if (minutes === 0) {
    return `${wholeHours}h`
  }
  
  return `${wholeHours}h ${minutes}m`
}

const formatDates = (dates) => {
  if (!dates || dates.length === 0) return 'No dates'
  if (dates.length === 1) return dates[0]
  
  const sortedDates = [...dates].sort()
  const firstDate = new Date(sortedDates[0])
  const lastDate = new Date(sortedDates[sortedDates.length - 1])
  
  const formatDate = (date) => {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }
  
  return `${formatDate(firstDate)} - ${formatDate(lastDate)} (${dates.length} days)`
}

const addTemplate = (templateText) => {
  if (localNotes.value) {
    localNotes.value += '\n' + templateText
  } else {
    localNotes.value = templateText
  }
}

const addTag = (tag) => {
  if (!selectedTags.value.includes(tag)) {
    selectedTags.value.push(tag)
  }
}

const removeTag = (tag) => {
  const index = selectedTags.value.indexOf(tag)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  }
}

const clearNotes = () => {
  localNotes.value = ''
  selectedTags.value = []
}

const handleSave = () => {
  const updatedShift = {
    ...props.shift,
    notes: localNotes.value,
    tags: selectedTags.value
  }
  
  emit('save', {
    shift: updatedShift,
    dates: props.dates
  })
  
  handleClose()
}

const handleClose = () => {
  isVisible.value = false
  emit('close')
}
</script>

<style scoped>
/* Custom styles for the notes dialog */
.notes-dialog {
  max-height: 80vh;
  overflow-y: auto;
}

/* Tag styling */
.tag-item {
  transition: all 0.2s ease;
}

.tag-item:hover {
  transform: scale(1.05);
}

/* Template button styling */
.template-btn {
  transition: all 0.2s ease;
}

.template-btn:hover {
  transform: translateY(-1px);
}
</style>
