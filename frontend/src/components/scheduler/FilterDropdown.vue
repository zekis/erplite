<template>
  <div class="filter-dropdown relative w-full" ref="dropdownRef">
    <!-- Trigger Button -->
    <button
      @click="toggleDropdown"
      :disabled="disabled"
      :class="[
        'filter-trigger w-full h-8 border-0 transition-all duration-200 flex items-center justify-between px-3',
        disabled ? [
          'bg-gray-100 dark:bg-gray-900 cursor-not-allowed opacity-60'
        ] : [
          'bg-gray-50 dark:bg-gray-800',
          isOpen ? 'bg-gray-100 dark:bg-gray-700' : 'hover:bg-gray-100 dark:hover:bg-gray-700'
        ],
        'text-gray-900 dark:text-white'
      ]"
    >
      <div class="flex items-center flex-1 min-w-0">
        <!-- Icon -->
        <Icon
          v-if="getIcon()"
          :icon="getIcon()"
          class="w-3 h-3 mr-2 flex-shrink-0"
          :class="getIconColor()"
        />
        
        <!-- Text content -->
        <div class="flex-1 min-w-0">
          <span v-if="selectedOption" class="text-xs font-medium truncate block">{{ selectedOption.label }}</span>
          <span v-else class="text-xs block italic text-gray-500 dark:text-gray-400">{{ placeholder }}</span>
        </div>
      </div>
      
      <!-- Clear button (when option is selected and allow-clear is true) -->
      <button
        v-if="selectedOption && allowClear"
        @click.stop="clearSelection"
        class="clear-btn p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors duration-200 flex-shrink-0 mr-1 text-gray-500 dark:text-gray-400 hover:text-red-500"
        title="Clear selection"
      >
        <Icon icon="lucide:x" class="w-2.5 h-2.5" />
      </button>
      
      <Icon
        icon="lucide:chevron-down"
        :class="[
          'w-3 h-3 transition-transform duration-200 flex-shrink-0 text-gray-500 dark:text-gray-400',
          isOpen ? 'rotate-180' : ''
        ]"
      />
    </button>

    <!-- Dropdown Panel -->
    <div
      v-if="isOpen"
      :class="[
        'dropdown-panel absolute border shadow-lg max-h-80 overflow-hidden bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-600',
        getDropdownPositionClass()
      ]"
      :style="getDropdownStyle()"
      style="top: 100%; margin-top: 4px; z-index: 9999;"
    >
      <!-- Search Input -->
      <div class="search-section p-2 border-b border-gray-300 dark:border-gray-600">
        <div class="search-input-wrapper flex items-center px-2 py-1.5 border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700">
          <Icon icon="lucide:search" class="w-3 h-3 mr-2 text-gray-500 dark:text-gray-400" />
          <input
            v-model="searchQuery"
            placeholder="Search..."
            class="flex-1 bg-transparent text-xs outline-none text-gray-900 dark:text-white"
            @keydown.escape="closeDropdown"
            ref="searchInput"
          />
        </div>
      </div>

      <!-- Options List -->
      <div 
        class="options-list max-h-64"
        style="overflow-y: scroll; overflow-x: hidden; padding-bottom: 4px;"
      >
        <!-- Filtered Options -->
        <template v-for="option in filteredOptions" :key="option.value || option.type">
          <!-- Divider -->
          <div
            v-if="option.type === 'divider'"
            class="divider-item border-t my-1 border-gray-300 dark:border-gray-600"
          >
            <div class="divider-text text-xs font-medium text-center py-1 text-gray-600 dark:text-gray-300">
              Activities
            </div>
          </div>
          
          <!-- Regular Option -->
          <div
            v-else
            @click="selectOption(option)"
            :class="[
              'option-item flex items-center p-2 cursor-pointer transition-all duration-200',
              selectedValue === option.value ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-700'
            ]"
          >
            <!-- Icon -->
            <div
              :class="['option-icon w-7 h-7 rounded flex items-center justify-center mr-3', getOptionBgColor(option)]"
            >
              <Icon
                :icon="getOptionIcon(option)"
                :class="['w-3.5 h-3.5', getOptionIconColor(option)]"
              />
            </div>

            <div class="option-content flex-1 min-w-0">
              <div class="option-name text-xs font-medium text-left text-gray-900 dark:text-white">
                {{ option.label }}
              </div>
              <div v-if="getOptionDescription(option)" class="option-description text-xs text-left text-gray-500 dark:text-gray-400">
                {{ getOptionDescription(option) }}
              </div>
            </div>
          </div>
        </template>

        <!-- No results -->
        <div
          v-if="filteredOptions.length === 0"
          class="no-results p-3 text-center text-gray-500 dark:text-gray-400"
        >
          <Icon icon="lucide:search-x" class="w-6 h-6 mx-auto mb-1 opacity-50" />
          <div class="text-xs">No {{ type }}s found</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'

// Props
const props = defineProps({
  modelValue: {
    type: [String, Number, null],
    default: null
  },
  options: {
    type: Array,
    default: () => []
  },
  type: {
    type: String,
    required: true, // 'project', 'activity', 'role', 'resource'
    validator: (value) => ['project', 'activity', 'role', 'resource'].includes(value)
  },
  placeholder: {
    type: String,
    default: 'Filter...'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  allowClear: {
    type: Boolean,
    default: true
  }
})

// Emits
const emit = defineEmits(['update:modelValue', 'change'])

// Refs
const dropdownRef = ref(null)
const searchInput = ref(null)

// State
const isOpen = ref(false)
const searchQuery = ref('')

// Computed
const selectedValue = computed(() => props.modelValue)

const selectedOption = computed(() => {
  return props.options.find(option => 
    option.value === selectedValue.value && option.type !== 'divider'
  )
})

const filteredOptions = computed(() => {
  let filtered = props.options

  // Apply search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(option =>
      option.type !== 'divider' && (
        option.label.toLowerCase().includes(query) ||
        (option.description && option.description.toLowerCase().includes(query))
      )
    )
  }

  return filtered
})

// Methods
const toggleDropdown = () => {
  if (props.disabled) return
  
  isOpen.value = !isOpen.value
  
  if (isOpen.value) {
    nextTick(() => {
      searchInput.value?.focus()
    })
  }
}

const closeDropdown = () => {
  isOpen.value = false
  searchQuery.value = ''
}

const selectOption = (option) => {
  const value = option ? option.value : null
  emit('update:modelValue', value)
  emit('change', { value, option })
  closeDropdown()
}

const clearSelection = () => {
  emit('update:modelValue', null)
  emit('change', { value: null, option: null })
}

const getIcon = () => {
  const icons = {
    project: 'lucide:folder',
    activity: 'lucide:zap',
    role: 'lucide:user-check',
    resource: 'lucide:user'
  }
  return icons[props.type]
}

const getIconColor = () => {
  const colors = {
    project: 'text-blue-500',
    activity: 'text-green-500',
    role: 'text-purple-500',
    resource: 'text-indigo-500'
  }
  return colors[props.type]
}

const getOptionBgColor = (option) => {
  const colors = {
    project: 'bg-blue-100 dark:bg-blue-900/30',
    activity: 'bg-green-100 dark:bg-green-900/30',
    role: 'bg-purple-100 dark:bg-purple-900/30',
    resource: 'bg-indigo-100 dark:bg-indigo-900/30'
  }
  return colors[props.type]
}

const getOptionDescription = (option) => {
  if (props.type === 'resource') {
    return option.resource_type
  } else if (props.type === 'role') {
    return option.description
  }
  return null
}

const getOptionIcon = (option) => {
  // For project filter, show different icons for projects vs activities
  if (props.type === 'project') {
    if (option.type === 'project') {
      return 'lucide:folder'
    } else if (option.type === 'activity') {
      return 'lucide:zap'
    }
  }
  
  // Default to the type-based icon
  return getIcon()
}

const getOptionIconColor = (option) => {
  // For project filter, show different colors for projects vs activities
  if (props.type === 'project') {
    if (option.type === 'project') {
      return 'text-blue-500'
    } else if (option.type === 'activity') {
      return 'text-green-500'
    }
  }
  
  // Default to the type-based color
  return getIconColor()
}

// Dropdown positioning
const getDropdownPositionClass = () => {
  return 'left-0'
}

const getDropdownStyle = () => {
  const minWidth = props.type === 'project' ? '280px' : 
                   props.type === 'activity' ? '240px' :
                   props.type === 'resource' ? '300px' : '260px'
  
  const style = {
    minWidth,
    width: 'max-content',
    maxWidth: '360px'
  }
  
  return style
}

// Click outside handler
const handleClickOutside = (event) => {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target)) {
    closeDropdown()
  }
}

// Lifecycle
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

// Watch for search query changes
watch(searchQuery, () => {
  // Could add debouncing here if needed
})
</script>

<style scoped>
.filter-dropdown {
  @apply relative;
}

.filter-trigger {
  @apply w-full transition-all duration-200 flex items-center justify-between cursor-pointer;
  @apply border-gray-300 dark:border-gray-600;
  height: 32px;
}

.filter-trigger:hover {
  @apply bg-gray-100 dark:bg-gray-600;
}

.filter-trigger:focus {
  @apply outline-none;
}

.dropdown-panel {
  @apply absolute top-full border shadow-xl overflow-hidden;
  @apply border-gray-200 dark:border-gray-600;
  z-index: 9999;
}

.search-input-wrapper {
  @apply flex items-center border;
}

.option-item {
  @apply flex items-center cursor-pointer transition-all duration-200;
}

.option-item:hover {
  @apply bg-gray-50 dark:bg-gray-700;
}

.option-icon {
  @apply flex items-center justify-center flex-shrink-0;
}

.option-content {
  @apply flex-1 min-w-0;
}

.option-name {
  @apply font-medium truncate;
}

.option-description {
  @apply truncate;
}

.no-results {
  @apply text-center;
}

/* Scrollbar styles */
.options-list::-webkit-scrollbar {
  width: 6px;
}

.options-list::-webkit-scrollbar-track {
  @apply bg-gray-100 dark:bg-gray-800;
}

.options-list::-webkit-scrollbar-thumb {
  @apply bg-gray-400 dark:bg-gray-600 rounded;
}

.options-list::-webkit-scrollbar-thumb:hover {
  @apply bg-gray-500;
}

/* Firefox scrollbar */
.options-list {
  scrollbar-width: thin;
  scrollbar-color: #9ca3af #f3f4f6;
}

@media (prefers-color-scheme: dark) {
  .options-list {
    scrollbar-color: #6b7280 #374151;
  }
}
</style>
