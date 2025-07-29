import { ref } from 'vue'

// Global state for scroll synchronization
const scrollContainers = ref(new Map())
let isScrolling = false

export function useScrollSync() {
  const registerScrollContainer = (element, className = 'sync-scroll') => {
    if (!element) return
    
    // Add to our registry
    scrollContainers.value.set(element, className)
    
    // Add scroll event listener
    element.addEventListener('scroll', (event) => {
      if (isScrolling) return
      
      isScrolling = true
      const scrollLeft = event.target.scrollLeft
      
      // Sync all other containers
      scrollContainers.value.forEach((containerClass, container) => {
        if (container !== event.target) {
          container.scrollLeft = scrollLeft
        }
      })
      
      // Reset flag after a short delay
      requestAnimationFrame(() => {
        isScrolling = false
      })
    })
  }
  
  const unregisterScrollContainer = (element) => {
    if (!element) return
    scrollContainers.value.delete(element)
  }
  
  const syncScrollPosition = (scrollLeft) => {
    if (isScrolling) return
    
    isScrolling = true
    scrollContainers.value.forEach((containerClass, container) => {
      container.scrollLeft = scrollLeft
    })
    
    requestAnimationFrame(() => {
      isScrolling = false
    })
  }
  
  return {
    registerScrollContainer,
    unregisterScrollContainer,
    syncScrollPosition
  }
}
