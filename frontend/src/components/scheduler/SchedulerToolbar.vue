<template>
  <div class="scheduler-toolbar border-b p-4 transition-all duration-300 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 border-gray-200 dark:border-gray-700">
    <div class="flex items-center justify-between">
      <!-- Left side - Tools -->
      <div class="flex items-center space-x-3">
        <div class="text-sm font-medium mr-2 flex items-center text-gray-900 dark:text-white">
          <Icon icon="lucide:wrench" class="w-4 h-4 mr-2" />
          Tools:
        </div>
        
        <!-- Copy Tool -->
        <button 
          class="tool-button"
          :class="{ 'active': activeTool === 'copy' }"
          @click="selectTool('copy')"
          title="Copy - Click to copy shifts, then click elsewhere to paste"
        >
          <Icon icon="lucide:copy" class="w-4 h-4" />
          <span class="ml-1">Copy</span>
        </button>

        <!-- Paste Tool -->
        <button 
          class="tool-button"
          :class="{ 'active': activeTool === 'paste', 'disabled': !hasCopiedData }"
          :disabled="!hasCopiedData"
          @click="selectTool('paste')"
          title="Paste - Click to paste copied shifts"
        >
          <Icon icon="lucide:clipboard" class="w-4 h-4" />
          <span class="ml-1">Paste</span>
        </button>

        <!-- Split Shift Tool -->
        <button 
          class="tool-button"
          :class="{ 'active': activeTool === 'split' }"
          @click="selectTool('split')"
          title="Split Shift - Click on a shift to split it into multiple parts"
        >
          <Icon icon="lucide:scissors" class="w-4 h-4" />
          <span class="ml-1">Split</span>
        </button>

        <!-- Clone Down Tool -->
        <button 
          class="tool-button"
          :class="{ 'active': activeTool === 'clone-down' }"
          @click="selectTool('clone-down')"
          title="Clone Down - Click on a shift to copy it to the row below"
        >
          <Icon icon="lucide:arrow-down" class="w-4 h-4" />
          <span class="ml-1">Clone Down</span>
        </button>

        <!-- Clone Up Tool -->
        <button 
          class="tool-button"
          :class="{ 'active': activeTool === 'clone-up' }"
          @click="selectTool('clone-up')"
          title="Clone Up - Click on a shift to copy it to the row above"
        >
          <Icon icon="lucide:arrow-up" class="w-4 h-4" />
          <span class="ml-1">Clone Up</span>
        </button>

        <!-- Add Leave Tool -->
        <button 
          class="tool-button"
          :class="{ 'active': activeTool === 'add-leave' }"
          @click="selectTool('add-leave')"
          title="Add Leave - Click on calendar cells to add leave entries"
        >
          <Icon icon="lucide:calendar-x" class="w-4 h-4" />
          <span class="ml-1">Add Leave</span>
        </button>

        <!-- Add Note Tool -->
        <button 
          class="tool-button"
          :class="{ 'active': activeTool === 'add-note' }"
          @click="selectTool('add-note')"
          title="Add Note - Click on shifts or cells to add notes"
        >
          <Icon icon="lucide:sticky-note" class="w-4 h-4" />
          <span class="ml-1">Add Note</span>
        </button>

        <!-- Clear Tool Selection -->
        <button 
          v-if="activeTool"
          class="clear-tool-button"
          @click="clearTool"
          title="Clear tool selection"
        >
          <Icon icon="lucide:x" class="w-4 h-4" />
        </button>
      </div>

      <!-- Right side - Navigation and actions -->
      <div class="flex items-center space-x-4">
        <!-- Active Tool Indicator -->
        <div v-if="activeTool" class="active-tool-indicator">
          <Icon icon="lucide:mouse-pointer-click" class="w-4 h-4 mr-2" />
          <span class="text-sm font-medium">{{ getToolDisplayName(activeTool) }} mode active</span>
        </div>

        <!-- Date Navigation -->
        <div class="flex items-center space-x-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2">
          <button 
            class="p-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isLoading"
            @click="$emit('navigate-date', -30)"
            title="Previous month"
          >
            <Icon icon="lucide:chevrons-left" class="w-4 h-4" />
          </button>
          <button 
            class="p-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isLoading"
            @click="$emit('navigate-date', -7)"
            title="Previous week"
          >
            <Icon icon="lucide:chevron-left" class="w-4 h-4" />
          </button>
          
          <div class="px-3 py-1 text-sm font-medium text-gray-700 dark:text-gray-300 min-w-[200px] text-center">
            {{ currentDateRange }}
          </div>
          
          <button 
            class="p-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isLoading"
            @click="$emit('navigate-date', 7)"
            title="Next week"
          >
            <Icon icon="lucide:chevron-right" class="w-4 h-4" />
          </button>
          <button 
            class="p-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isLoading"
            @click="$emit('navigate-date', 30)"
            title="Next month"
          >
            <Icon icon="lucide:chevrons-right" class="w-4 h-4" />
          </button>
        </div>

        <!-- Action Buttons -->
        <div class="flex items-center space-x-2">
          <button 
            class="flex items-center px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isLoading"
            @click="$emit('refresh')"
          >
            <Icon 
              :icon="isLoading ? 'lucide:loader-2' : 'lucide:refresh-cw'" 
              :class="['w-4 h-4 mr-2', { 'animate-spin': isLoading }]" 
            />
            Refresh
          </button>
          <button 
            class="flex items-center px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isLoading"
            @click="$emit('export')"
          >
            <Icon icon="lucide:download" class="w-4 h-4 mr-2" />
            Export
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'

// Props
defineProps({
  currentDateRange: {
    type: String,
    default: 'Loading...'
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits([
  'navigate-date', 
  'refresh', 
  'export',
  'tool-selected',
  'tool-cleared'
])

// State
const activeTool = ref(null)
const copiedData = ref(null)

// Computed
const hasCopiedData = computed(() => {
  return copiedData.value !== null
})

// Methods
const selectTool = (tool) => {
  if (activeTool.value === tool) {
    // If clicking the same tool, deactivate it
    clearTool()
  } else {
    activeTool.value = tool
    emit('tool-selected', tool)
    console.log(`Selected tool: ${tool}`)
  }
}

const clearTool = () => {
  activeTool.value = null
  emit('tool-cleared')
  console.log('Cleared tool selection')
}

const getToolDisplayName = (tool) => {
  const names = {
    'copy': 'Copy',
    'paste': 'Paste',
    'split': 'Split Shift',
    'clone-down': 'Clone Down',
    'clone-up': 'Clone Up',
    'add-leave': 'Add Leave',
    'add-note': 'Add Note'
  }
  return names[tool] || tool
}

// Expose methods for parent components
defineExpose({
  activeTool,
  clearTool,
  setCopiedData: (data) => {
    copiedData.value = data
  },
  getCopiedData: () => copiedData.value
})
</script>

<style scoped>
.tool-button {
  @apply flex items-center px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border-2 border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-all duration-200 cursor-pointer;
}

.tool-button:hover {
  @apply border-blue-300 dark:border-blue-500 shadow-md transform scale-105;
}

.tool-button.active {
  @apply bg-blue-500 text-white border-blue-500 shadow-lg;
}

.tool-button.active:hover {
  @apply bg-blue-600 border-blue-600;
}

.tool-button.disabled {
  @apply opacity-50 cursor-not-allowed;
}

.tool-button.disabled:hover {
  @apply transform-none scale-100 shadow-none border-gray-300 dark:border-gray-600;
}

.clear-tool-button {
  @apply flex items-center justify-center w-8 h-8 text-gray-500 dark:text-gray-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-full hover:bg-red-100 dark:hover:bg-red-900/40 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200 cursor-pointer;
}

.clear-tool-button:hover {
  @apply shadow-md transform scale-110;
}

.active-tool-indicator {
  @apply flex items-center px-3 py-2 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg text-blue-700 dark:text-blue-300;
}

.active-tool-indicator .text-sm {
  @apply font-medium;
}
</style>
