<template>
  <div class="filterable-dropdown relative w-full" ref="dropdownRef">
    <!-- Trigger Button -->
    <button
      @click="toggleDropdown"
      :disabled="disabled"
      :class="[
        'dropdown-trigger w-full h-full border-0 transition-all duration-200 flex items-center justify-between',
        type === 'resource' ? 'p-1' : 'p-2',
        disabled ? [
          'bg-gray-100 dark:bg-gray-900 cursor-not-allowed opacity-60'
        ] : [
          'bg-gray-50 dark:bg-gray-800',
          isOpen ? 'bg-gray-100 dark:bg-gray-700' : 'hover:bg-gray-100 dark:hover:bg-gray-700'
        ],
        'text-gray-900 dark:text-white'
      ]"
      style="min-height: 50px;"
    >
      <div class="flex items-center flex-1 min-w-0">
        <!-- Avatar for resources (positioned like an icon) -->
        <Avatar
          v-if="selectedOption && type === 'resource' && selectedOption.resource_type"
          :name="selectedOption.label"
          :show-status="false"
          :is-online="false"
          size="md"
          class="mr-2 flex-shrink-0 w-6 h-6"
          style="min-width: 24px; min-height: 24px; max-width: 24px; max-height: 24px;"
        />
        <!-- Icon for other types -->
        <Icon
          v-else-if="selectedOption && getIcon() && type !== 'resource'"
          :icon="getIcon()"
          class="w-4 h-4 mr-2 flex-shrink-0"
          :class="getIconColor()"
        />
        
        <!-- Text content -->
        <div class="flex-1 min-w-0 text-left">
          <div v-if="selectedOption" class="flex flex-col text-left">
            <span class="text-xs font-medium truncate block text-left">{{ selectedOption.label }}</span>
            <span v-if="getSelectedOptionDescription()" class="text-xs text-gray-600 dark:text-gray-300 truncate block text-left">{{ getSelectedOptionDescription() }}</span>
          </div>
          <span v-else class="text-xs block italic text-gray-600 dark:text-gray-300 text-left">{{ placeholder }}</span>
        </div>
      </div>
      
      <!-- Clear button (when option is selected and allow-clear is true) -->
      <button
        v-if="selectedOption && allowClear"
        @click.stop="clearSelection"
        class="clear-btn p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors duration-200 flex-shrink-0 mr-1 text-gray-600 dark:text-gray-300 hover:text-red-500"
        title="Clear selection"
      >
        <Icon icon="lucide:x" class="w-3 h-3" />
      </button>
      
      <Icon
        icon="lucide:chevron-down"
        :class="[
          'w-3 h-3 transition-transform duration-200 flex-shrink-0 text-gray-600 dark:text-gray-300',
          isOpen ? 'rotate-180' : ''
        ]"
      />
    </button>

    <!-- Dropdown Panel -->
    <div
      v-if="isOpen"
      :class="[
        'dropdown-panel absolute border shadow-lg max-h-80 overflow-hidden bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700',
        getDropdownPositionClass()
      ]"
      :style="getDropdownStyle()"
      style="top: 100%; margin-top: 4px; z-index: 9999;"
    >
      <!-- Search Input -->
      <div class="search-section p-3 border-b border-gray-300 dark:border-gray-600">
        <div class="search-input-wrapper flex items-center px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700">
          <Icon icon="lucide:search" class="w-4 h-4 mr-2 text-gray-600 dark:text-gray-300" />
          <input
            v-model="searchQuery"
            placeholder="Search..."
            class="flex-1 bg-transparent text-sm outline-none text-gray-900 dark:text-white"
            @keydown.escape="closeDropdown"
            ref="searchInput"
          />
        </div>
      </div>

      <!-- Filter Tabs (for resources) -->
      <div v-if="type === 'resource'" class="filter-tabs flex p-2 space-x-1 border-b border-gray-300 dark:border-gray-600">
        <button
          v-for="filter in resourceFilters"
          :key="filter.key"
          @click="activeFilter = filter.key"
          :class="[
            'filter-tab px-3 py-1 rounded-md text-xs font-medium transition-all duration-200',
            activeFilter === filter.key ? [
              'bg-blue-500 text-white'
            ] : [
              'bg-gray-50 dark:bg-gray-700',
              'text-gray-600 dark:text-gray-300',
              'hover:bg-blue-100'
            ]
          ]"
        >
          <Icon :icon="filter.icon" class="w-3 h-3 mr-1" />
          {{ filter.label }}
        </button>
      </div>

      <!-- Options List -->
      <div 
        class="options-list" 
        :class="type === 'resource' ? 'max-h-80' : 'max-h-64'"
        style="overflow-y: scroll; overflow-x: hidden; padding-bottom: 8px;"
      >
        <!-- Unassigned Option (for resources) -->
        <div
          v-if="type === 'resource' && showUnassigned"
          @click="selectOption({ value: '__no_resource__', label: 'No resource set', resource_type: 'None' })"
          :class="[
            'option-item flex items-center p-3 cursor-pointer transition-all duration-200',
            selectedValue === '__no_resource__' ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-700'
          ]"
        >
          <div class="option-avatar w-8 h-8 rounded-full flex items-center justify-center mr-3 bg-gray-100 dark:bg-gray-700">
            <Icon icon="lucide:user-x" class="w-4 h-4 text-gray-600 dark:text-gray-300" />
          </div>
          <div class="option-content flex-1">
            <div class="option-name text-sm font-medium text-gray-900 dark:text-white">No resource set</div>
            <div class="option-description text-xs text-gray-600 dark:text-gray-300">Rows with no resource assigned</div>
          </div>
        </div>

        <!-- Filtered Options -->
        <template v-for="option in filteredOptions" :key="option.value || option.type">
          <!-- Divider -->
          <div
            v-if="option.type === 'divider'"
            class="divider-item border-t my-2 border-gray-300 dark:border-gray-600"
          >
            <div class="divider-text text-xs font-medium text-center py-2 text-gray-600 dark:text-gray-300">
              Activities
            </div>
          </div>
          
          <!-- Regular Option -->
          <div
            v-else
            @click="selectOption(option)"
            :class="[
              'option-item flex items-center p-3 cursor-pointer transition-all duration-200',
              selectedValue === option.value ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-700'
            ]"
          >
            <!-- Avatar for resources -->
            <Avatar
              v-if="type === 'resource'"
              :name="option.label"
              :show-status="false"
              :is-online="false"
              size="sm"
              class="mr-3 flex-shrink-0"
            />
            <!-- Icon for other types -->
            <div
              v-else
              :class="['option-icon w-9 h-9 rounded-full flex items-center justify-center mr-3', getOptionBgColor(option)]"
            >
              <Icon
                :icon="getOptionIcon(option)"
                :class="['w-4.5 h-4.5', getOptionIconColor(option)]"
              />
            </div>

            <div class="option-content flex-1 min-w-0 text-left">
              <div class="option-name text-sm font-medium text-left text-gray-900 dark:text-white">
                {{ option.label }}
              </div>
              <div v-if="getOptionDescription(option)" class="option-description text-xs text-left text-gray-600 dark:text-gray-300">
                {{ getOptionDescription(option) }}
              </div>
            </div>

            <!-- Status indicator for resources -->
            <div v-if="type === 'resource'" class="option-status flex-shrink-0">
              <div class="w-2 h-2 rounded-full bg-orange-400"></div>
            </div>
          </div>
        </template>

        <!-- No results -->
        <div
          v-if="filteredOptions.length === 0"
          class="no-results p-4 text-center text-gray-600 dark:text-gray-300"
        >
          <Icon icon="lucide:search-x" class="w-8 h-8 mx-auto mb-2 opacity-50" />
          <div class="text-sm">No {{ type }}s found</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import Avatar from './Avatar.vue'
// Composables removed - using direct Tailwind classes

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
    default: 'Select option'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  allowClear: {
    type: Boolean,
    default: false
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
const activeFilter = ref('all')

// Resource filters
const resourceFilters = [
  { key: 'all', label: 'All', icon: 'lucide:users' },
  { key: 'people', label: 'People', icon: 'lucide:user' },
  { key: 'equipment', label: 'Equipment', icon: 'lucide:wrench' },
  { key: 'available', label: 'Available', icon: 'lucide:check-circle' }
]

// Computed
const selectedValue = computed(() => props.modelValue)

const selectedOption = computed(() => {
  return props.options.find(option => 
    option.value === selectedValue.value && option.type !== 'divider'
  )
})

const showUnassigned = computed(() => {
  return props.type === 'resource'
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

  // Apply resource type filter
  if (props.type === 'resource' && activeFilter.value !== 'all') {
    if (activeFilter.value === 'people') {
      filtered = filtered.filter(option => option.resource_type === 'Person')
    } else if (activeFilter.value === 'equipment') {
      filtered = filtered.filter(option => option.resource_type === 'Equipment')
    } else if (activeFilter.value === 'available') {
      // Filter by availability - you can customize this logic
      filtered = filtered.filter(option => option.available_capacity > 0)
    }
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
    project: 'bg-blue-100',
    activity: 'bg-green-100',
    role: 'bg-purple-100',
    resource: 'bg-indigo-100'
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

const getSelectedOptionDescription = () => {
  if (!selectedOption.value) return null
  
  if (props.type === 'resource') {
    return selectedOption.value.resource_type
  } else if (props.type === 'role') {
    return selectedOption.value.description
  } else if (props.type === 'activity') {
    // Could show project name or activity description
    return selectedOption.value.description || selectedOption.value.project_name
  } else if (props.type === 'project') {
    // Could show project description or client info
    return selectedOption.value.description || selectedOption.value.client
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
  // All dropdowns align to left edge of trigger for consistent positioning
  return 'left-0'
}

const getDropdownStyle = () => {
  // Set minimum width to ensure dropdown is usable
  const minWidth = props.type === 'project' ? '300px' : 
                   props.type === 'activity' ? '250px' :
                   props.type === 'resource' ? '320px' : '280px'
  
  const style = {
    minWidth,
    width: 'max-content',
    maxWidth: '400px'
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
  // Reset filter when searching
  if (searchQuery.value && activeFilter.value !== 'all') {
    activeFilter.value = 'all'
  }
})
</script>

<style scoped>
.filterable-dropdown {
  @apply relative;
}

.dropdown-trigger {
  @apply w-full p-2 border transition-all duration-200 flex items-center justify-between cursor-pointer;
  @apply border-gray-300 dark:border-gray-600;
}

.dropdown-trigger:hover {
  @apply border-blue-400 dark:border-blue-500;
}

.dropdown-trigger:focus {
  @apply outline-none border-blue-500 dark:border-blue-400;
}

.dropdown-panel {
  @apply absolute top-full mt-1 border shadow-xl overflow-hidden;
  @apply border-gray-200 dark:border-gray-600;
  z-index: 9999; /* Ensure it appears above all other elements */
}

.search-input-wrapper {
  @apply flex items-center px-3 py-2 rounded-lg border;
}

.filter-tab {
  @apply px-3 py-1 rounded-md text-xs font-medium transition-all duration-200 cursor-pointer;
}

.option-item {
  @apply flex items-center p-3 cursor-pointer transition-all duration-200;
}

.option-item:hover {
  @apply bg-gray-50;
}

.option-avatar {
  @apply w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0;
}

.option-icon {
  @apply w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0;
}

.option-content {
  @apply flex-1 min-w-0;
}

.option-name {
  @apply text-sm font-medium truncate;
}

.option-description {
  @apply text-xs truncate;
}

.option-status {
  @apply flex-shrink-0;
}

.no-results {
  @apply p-4 text-center;
}

/* Ensure scrollbars are visible on options list */
.options-list::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.options-list::-webkit-scrollbar-track {
  @apply bg-gray-100 dark:bg-gray-800;
}

.options-list::-webkit-scrollbar-thumb {
  @apply bg-gray-400 dark:bg-gray-600 rounded;
}

.options-list::-webkit-scrollbar-thumb:hover {
  @apply bg-gray-500 dark:bg-gray-500;
}

/* Firefox scrollbar */
.options-list {
  scrollbar-width: thin;
  scrollbar-color: #9ca3af #f3f4f6;
}

/* Dark mode Firefox scrollbar */
@media (prefers-color-scheme: dark) {
  .options-list {
    scrollbar-color: #6b7280 #374151;
  }
}
</style>
