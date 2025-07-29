<template>
  <div class="user-menu relative" ref="userMenuRef">
    <!-- User Avatar/Button -->
    <button
      @click="toggleMenu"
      :class="[
        'user-menu-trigger flex items-center space-x-2 p-2 rounded-lg transition-all duration-200 bg-gray-50 dark:bg-gray-700 hover:bg-opacity-80 text-gray-900 dark:text-white',
        isOpen ? 'ring-2 ring-blue-500' : ''
      ]"
      :title="currentUser?.full_name || 'User Menu'"
    >
      <!-- User Avatar -->
      <Avatar
        :name="currentUser?.full_name || 'User'"
        :src="currentUser?.user_image"
        size="sm"
        class="flex-shrink-0"
      />
      
      <!-- User Info (hidden on mobile) -->
      <div class="hidden sm:block text-left min-w-0">
        <div class="text-sm font-medium truncate text-gray-900 dark:text-white">
          {{ currentUser?.full_name || 'User' }}
        </div>
        <div class="text-xs truncate text-gray-600 dark:text-gray-300">
          {{ currentUser?.email || '' }}
        </div>
      </div>
      
      <!-- Chevron -->
      <Icon
        icon="lucide:chevron-down"
        :class="[
          'w-4 h-4 transition-transform duration-200 flex-shrink-0 text-gray-600 dark:text-gray-300',
          isOpen ? 'rotate-180' : ''
        ]"
      />
    </button>

    <!-- Dropdown Menu -->
    <div
      v-if="isOpen"
      class="user-menu-dropdown absolute top-full right-0 mt-2 w-64 rounded-lg border shadow-xl z-50 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
    >
      <!-- User Info Header -->
      <div class="user-info-header p-4 border-b border-gray-300 dark:border-gray-600">
        <div class="flex items-center space-x-3">
          <Avatar
            :name="currentUser?.full_name || 'User'"
            :src="currentUser?.user_image"
            size="md"
            class="flex-shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="font-semibold truncate text-gray-900 dark:text-white">
              {{ currentUser?.full_name || 'User' }}
            </div>
            <div class="text-sm truncate text-gray-600 dark:text-gray-300">
              {{ currentUser?.email || '' }}
            </div>
            <div v-if="currentUser?.role" class="text-xs truncate text-gray-500 dark:text-gray-400">
              {{ currentUser.role }}
            </div>
          </div>
        </div>
      </div>

      <!-- Menu Items -->
      <div class="menu-items py-2">
        <!-- Profile -->
        <button
          @click="handleProfile"
          class="menu-item w-full flex items-center px-4 py-3 text-left transition-all duration-200 text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          <Icon icon="lucide:user" class="w-4 h-4 mr-3 flex-shrink-0" />
          <span class="text-sm">My Profile</span>
        </button>

        <!-- Settings -->
        <button
          @click="handleSettings"
          class="menu-item w-full flex items-center px-4 py-3 text-left transition-all duration-200 text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          <Icon icon="lucide:settings" class="w-4 h-4 mr-3 flex-shrink-0" />
          <span class="text-sm">Settings</span>
        </button>

        <div class="divider border-t my-2 border-gray-300 dark:border-gray-600"></div>

        <!-- Desk View -->
        <button
          @click="handleDeskView"
          class="menu-item w-full flex items-center px-4 py-3 text-left transition-all duration-200 text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          <Icon icon="lucide:layout-dashboard" class="w-4 h-4 mr-3 flex-shrink-0" />
          <span class="text-sm">Go to Desk</span>
        </button>

        <!-- Help -->
        <button
          @click="handleHelp"
          class="menu-item w-full flex items-center px-4 py-3 text-left transition-all duration-200 text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          <Icon icon="lucide:help-circle" class="w-4 h-4 mr-3 flex-shrink-0" />
          <span class="text-sm">Help & Support</span>
        </button>

        <div class="divider border-t my-2 border-gray-300 dark:border-gray-600"></div>

        <!-- Logout -->
        <button
          @click="handleLogout"
          class="menu-item w-full flex items-center px-4 py-3 text-left transition-all duration-200 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
        >
          <Icon icon="lucide:log-out" class="w-4 h-4 mr-3 flex-shrink-0" />
          <span class="text-sm">Sign Out</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import Avatar from './Avatar.vue'
// Composables removed - using direct Tailwind classes

// Props
const props = defineProps({
  currentUser: {
    type: Object,
    default: () => ({
      full_name: 'Administrator',
      email: 'admin@example.com',
      user_image: null,
      role: 'System Manager'
    })
  }
})

// Emits
const emit = defineEmits(['logout', 'profile', 'settings', 'desk-view', 'help'])

// Refs
const userMenuRef = ref(null)

// State
const isOpen = ref(false)

// Methods
const toggleMenu = () => {
  isOpen.value = !isOpen.value
}

const closeMenu = () => {
  isOpen.value = false
}

const handleProfile = () => {
  emit('profile')
  closeMenu()
}

const handleSettings = () => {
  emit('settings')
  closeMenu()
}

const handleDeskView = () => {
  // Navigate to Frappe desk
  window.location.href = '/app'
}

const handleHelp = () => {
  emit('help')
  closeMenu()
}

const handleLogout = () => {
  if (confirm('Are you sure you want to sign out?')) {
    // Call Frappe logout
    window.location.href = '/api/method/logout'
  }
  closeMenu()
}

// Click outside handler
const handleClickOutside = (event) => {
  if (userMenuRef.value && !userMenuRef.value.contains(event.target)) {
    closeMenu()
  }
}

// Lifecycle
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.user-menu {
  @apply relative;
}

.user-menu-trigger {
  @apply cursor-pointer;
}

.user-menu-trigger:hover {
  @apply scale-105;
}

.user-menu-dropdown {
  @apply opacity-0 transform translate-y-2 transition-all duration-200;
  min-width: 256px;
  animation: slideIn 0.2s ease-out forwards;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.menu-item {
  @apply transition-all duration-200;
}

.menu-item:hover {
  @apply scale-[1.02];
}

.menu-item:active {
  @apply scale-[0.98];
}

/* Responsive adjustments */
@media (max-width: 640px) {
  .user-menu-dropdown {
    @apply w-56 right-0;
  }
}
</style>
