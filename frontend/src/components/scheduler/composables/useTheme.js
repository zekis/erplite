import { ref, computed, watch } from 'vue'

export function useTheme() {
  // Theme state
  const isDark = ref(false)
  
  // Load theme from localStorage on initialization
  const initializeTheme = () => {
    const savedTheme = localStorage.getItem('scheduler-theme')
    
    if (savedTheme) {
      isDark.value = savedTheme === 'dark'
    } else {
      // Default to system preference
      isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
    }
    
    applyTheme()
  }
  
  // Apply theme to document
  const applyTheme = () => {
    if (isDark.value) {
      document.documentElement.classList.add('dark')
      document.documentElement.setAttribute('data-theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      document.documentElement.setAttribute('data-theme', 'light')
    }
  }
  
  // Toggle theme
  const toggleTheme = () => {
    isDark.value = !isDark.value
    localStorage.setItem('scheduler-theme', isDark.value ? 'dark' : 'light')
    applyTheme()
  }
  
  // Watch for theme changes
  watch(isDark, applyTheme)
  
  // Pure Tailwind CSS classes with dark mode support
  const colors = computed(() => ({
    // Background colors using Tailwind classes
    bg: {
      primary: 'bg-white dark:bg-gray-900',
      secondary: 'bg-gray-50 dark:bg-gray-800', 
      tertiary: 'bg-gray-100 dark:bg-gray-700',
      card: 'bg-white dark:bg-gray-800',
      hover: 'bg-gray-50 dark:bg-gray-700',
      active: 'bg-blue-50 dark:bg-blue-900',
      muted: 'bg-gray-100 dark:bg-gray-700',
      disabled: 'bg-gray-100 dark:bg-gray-700'
    },
    
    // Text colors using Tailwind classes
    text: {
      primary: 'text-gray-900 dark:text-white',
      secondary: 'text-gray-600 dark:text-gray-300',
      tertiary: 'text-gray-500 dark:text-gray-400',
      muted: 'text-gray-400 dark:text-gray-500',
      inverse: 'text-white dark:text-gray-900',
      link: 'text-blue-600 dark:text-blue-400',
      linkHover: 'text-blue-700 dark:text-blue-300'
    },
    
    // Border colors using Tailwind classes
    border: {
      primary: 'border-gray-200 dark:border-gray-700',
      secondary: 'border-gray-300 dark:border-gray-600',
      tertiary: 'border-gray-100 dark:border-gray-800',
      focus: 'border-blue-500 dark:border-blue-400',
      error: 'border-red-500 dark:border-red-400',
      success: 'border-green-500 dark:border-green-400'
    },
    
    // Shadow utilities using CSS custom properties
    shadow: {
      sm: 'shadow-sm',
      md: 'shadow-md', 
      lg: 'shadow-lg',
      xl: 'shadow-xl'
    },
    
    // Scheduler specific classes
    scheduler: {
      header: 'scheduler-header',
      row: 'scheduler-row',
      rowHover: 'scheduler-row:hover',
      rowActive: 'scheduler-row active',
      projectHeader: 'scheduler-project-header'
    },
    
    // Dropdown specific classes
    dropdown: {
      panel: 'dropdown-panel',
      item: 'dropdown-item',
      itemHover: 'dropdown-item:hover',
      itemActive: 'dropdown-item active'
    },
    
    // Resize handle classes
    resize: {
      handle: 'resize-handle',
      handleHover: 'resize-handle:hover',
      handleActive: 'resize-handle resizing'
    },
    
    // Brand colors (consistent across themes)
    brand: {
      primary: 'bg-blue-600 text-white',
      primaryHover: 'hover:bg-blue-700',
      secondary: 'bg-indigo-600 text-white',
      secondaryHover: 'hover:bg-indigo-700',
      success: 'bg-green-600 text-white',
      successHover: 'hover:bg-green-700',
      warning: 'bg-yellow-600 text-white',
      warningHover: 'hover:bg-yellow-700',
      danger: 'bg-red-600 text-white',
      dangerHover: 'hover:bg-red-700'
    },
    
    // Status colors using CSS custom properties
    status: {
      online: 'text-green-500',
      busy: 'text-yellow-500', 
      away: 'text-gray-400',
      offline: 'text-gray-300',
      planned: isDark.value ? 'bg-blue-900 text-blue-200 border-blue-700' : 'bg-blue-100 text-blue-800 border-blue-200',
      inProgress: isDark.value ? 'bg-yellow-900 text-yellow-200 border-yellow-700' : 'bg-yellow-100 text-yellow-800 border-yellow-200',
      completed: isDark.value ? 'bg-green-900 text-green-200 border-green-700' : 'bg-green-100 text-green-800 border-green-200',
      cancelled: isDark.value ? 'bg-red-900 text-red-200 border-red-700' : 'bg-red-100 text-red-800 border-red-200'
    },
    
    // Gradient backgrounds using CSS custom properties
    gradients: {
      primary: 'bg-gradient-primary',
      secondary: 'bg-gradient-secondary', 
      success: 'bg-gradient-success'
    }
  }))
  
  // CSS Custom Property values for direct style binding
  const cssVars = computed(() => ({
    // Background colors
    '--bg-primary': 'var(--bg-primary)',
    '--bg-secondary': 'var(--bg-secondary)',
    '--bg-tertiary': 'var(--bg-tertiary)',
    '--bg-card': 'var(--bg-card)',
    '--bg-hover': 'var(--bg-hover)',
    '--bg-active': 'var(--bg-active)',
    
    // Text colors
    '--text-primary': 'var(--text-primary)',
    '--text-secondary': 'var(--text-secondary)',
    '--text-tertiary': 'var(--text-tertiary)',
    '--text-muted': 'var(--text-muted)',
    
    // Border colors
    '--border-primary': 'var(--border-primary)',
    '--border-secondary': 'var(--border-secondary)',
    '--border-tertiary': 'var(--border-tertiary)',
    
    // Scheduler specific
    '--scheduler-header-bg': 'var(--scheduler-header-bg)',
    '--scheduler-row-bg': 'var(--scheduler-row-bg)',
    '--scheduler-row-hover': 'var(--scheduler-row-hover)',
    '--scheduler-resize-handle': 'var(--scheduler-resize-handle)',
    
    // Dropdown colors
    '--dropdown-bg': 'var(--dropdown-bg)',
    '--dropdown-border': 'var(--dropdown-border)',
    '--dropdown-item-hover': 'var(--dropdown-item-hover)'
  }))
  
  // Shadow utilities (for backward compatibility)
  const shadows = computed(() => ({
    sm: isDark.value ? 'shadow-lg shadow-black/20' : 'shadow-sm',
    md: isDark.value ? 'shadow-xl shadow-black/25' : 'shadow-md',
    lg: isDark.value ? 'shadow-2xl shadow-black/30' : 'shadow-lg',
    xl: isDark.value ? 'shadow-2xl shadow-black/40' : 'shadow-xl'
  }))
  
  // Animation classes
  const animations = {
    fadeIn: 'animate-in fade-in duration-200',
    slideIn: 'animate-in slide-in-from-top-2 duration-300',
    scaleIn: 'animate-in zoom-in-95 duration-200',
    bounce: 'animate-bounce',
    pulse: 'animate-pulse',
    spin: 'animate-spin'
  }
  
  return {
    // State
    isDark,
    
    // Methods
    toggleTheme,
    initializeTheme,
    
    // Computed
    colors,
    shadows,
    cssVars,
    animations
  }
}
