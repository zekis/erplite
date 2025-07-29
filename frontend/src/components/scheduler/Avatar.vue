<template>
  <div 
    :class="[
      'relative inline-flex items-center justify-center rounded-full font-medium select-none',
      sizeClasses,
      shadows.sm,
      'transition-all duration-200 hover:scale-105'
    ]"
    :style="(!src || imageError) ? { 
      backgroundColor: customColor,
      color: 'white'
    } : {}"
    :title="name"
  >
    <!-- Profile Image -->
    <img 
      v-if="src && !imageError" 
      :src="src" 
      :alt="name"
      :class="['rounded-full object-cover', sizeClasses]"
      @error="handleImageError"
    />
    
    <!-- Initials Fallback -->
    <span 
      v-else
      :class="[
        'font-semibold uppercase',
        textSizeClasses
      ]"
    >
      {{ initials }}
    </span>
    
    <!-- Online Status Indicator -->
    <div 
      v-if="showStatus && isOnline"
      :class="[
        'absolute -bottom-0.5 -right-0.5 rounded-full border-2 border-white',
        statusSizeClasses,
        'bg-green-500'
      ]"
    />
    
    <!-- Role Badge -->
    <div 
      v-if="role && showRole"
      :class="[
        'absolute -top-1 -right-1 px-1.5 py-0.5 text-xs font-medium rounded-full',
        'bg-blue-600 text-white',
        shadows.sm
      ]"
    >
      {{ role }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useTheme } from './composables/useTheme'

const props = defineProps({
  name: {
    type: String,
    required: true
  },
  src: {
    type: String,
    default: null
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['xs', 'sm', 'md', 'lg', 'xl', '2xl'].includes(value)
  },
  color: {
    type: String,
    default: null
  },
  role: {
    type: String,
    default: null
  },
  showRole: {
    type: Boolean,
    default: false
  },
  showStatus: {
    type: Boolean,
    default: false
  },
  isOnline: {
    type: Boolean,
    default: false
  }
})

const { colors, shadows } = useTheme()

const imageError = ref(false)

// Handle image loading errors
const handleImageError = () => {
  imageError.value = true
}

// Generate initials from name
const initials = computed(() => {
  if (!props.name) return '?'
  
  const words = props.name.trim().split(' ')
  if (words.length === 1) {
    return words[0].substring(0, 2).toUpperCase()
  }
  
  return (words[0][0] + words[words.length - 1][0]).toUpperCase()
})

// Size-based classes
const sizeClasses = computed(() => {
  const sizes = {
    xs: 'w-6 h-6',
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
    xl: 'w-16 h-16',
    '2xl': 'w-20 h-20'
  }
  return sizes[props.size]
})

const textSizeClasses = computed(() => {
  const sizes = {
    xs: 'text-xs',
    sm: 'text-sm',
    md: 'text-sm',
    lg: 'text-base',
    xl: 'text-lg',
    '2xl': 'text-xl'
  }
  return sizes[props.size]
})

const statusSizeClasses = computed(() => {
  const sizes = {
    xs: 'w-2 h-2',
    sm: 'w-2.5 h-2.5',
    md: 'w-3 h-3',
    lg: 'w-3.5 h-3.5',
    xl: 'w-4 h-4',
    '2xl': 'w-5 h-5'
  }
  return sizes[props.size]
})

// Custom color or generated color
const customColor = computed(() => {
  if (props.color) return props.color
  
  // Generate a consistent color based on name
  const colors = [
    '#3B82F6', // blue
    '#8B5CF6', // violet
    '#06B6D4', // cyan
    '#10B981', // emerald
    '#F59E0B', // amber
    '#EF4444', // red
    '#EC4899', // pink
    '#84CC16', // lime
    '#6366F1', // indigo
    '#14B8A6'  // teal
  ]
  
  let hash = 0
  for (let i = 0; i < props.name.length; i++) {
    hash = props.name.charCodeAt(i) + ((hash << 5) - hash)
  }
  
  return colors[Math.abs(hash) % colors.length]
})
</script>

<style scoped>
/* Additional custom styles if needed */
</style>
