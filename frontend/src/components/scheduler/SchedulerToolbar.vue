<template>
  <div class="scheduler-toolbar border-b p-4 transition-all duration-300 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 border-gray-200 dark:border-gray-700">
    <div class="flex items-center justify-between">
      <!-- Left side - Template cards -->
      <div class="flex items-center space-x-3">
        <div class="text-sm font-medium mr-2 flex items-center text-gray-900 dark:text-white">
          <Icon icon="lucide:layout-template" class="w-4 h-4 mr-2" />
          Quick Templates:
        </div>
        
        <!-- 8 Hour Template -->
        <div 
          class="template-card"
          :class="{ 'opacity-50 cursor-not-allowed': isLoading }"
          draggable="true"
          @dragstart="handleTemplateDragStart($event, '8h')"
          @dragend="handleTemplateDragEnd"
        >
          <i class="pi pi-clock text-blue-600"></i>
          <span class="ml-1">8h Day</span>
        </div>

        <!-- 12 Hour Template -->
        <div 
          class="template-card"
          :class="{ 'opacity-50 cursor-not-allowed': isLoading }"
          draggable="true"
          @dragstart="handleTemplateDragStart($event, '12h')"
          @dragend="handleTemplateDragEnd"
        >
          <i class="pi pi-clock text-green-600"></i>
          <span class="ml-1">12h Shift</span>
        </div>

        <!-- Leave Template -->
        <div 
          class="template-card"
          :class="{ 'opacity-50 cursor-not-allowed': isLoading }"
          draggable="true"
          @dragstart="handleTemplateDragStart($event, 'leave')"
          @dragend="handleTemplateDragEnd"
        >
          <i class="pi pi-calendar-times text-orange-600"></i>
          <span class="ml-1">Leave</span>
        </div>
      </div>

      <!-- Right side - Navigation and actions -->
      <div class="flex items-center space-x-4">
        <!-- Date Navigation -->
        <div class="flex items-center space-x-2 bg-white rounded-lg border border-gray-300 px-3 py-2">
          <Button 
            icon="pi pi-angle-double-left" 
            text 
            size="small"
            :disabled="isLoading"
            @click="$emit('navigate-date', -30)"
            title="Previous month"
          />
          <Button 
            icon="pi pi-angle-left" 
            text 
            size="small"
            :disabled="isLoading"
            @click="$emit('navigate-date', -7)"
            title="Previous week"
          />
          
          <div class="px-3 py-1 text-sm font-medium text-gray-700 min-w-[200px] text-center">
            {{ currentDateRange }}
          </div>
          
          <Button 
            icon="pi pi-angle-right" 
            text 
            size="small"
            :disabled="isLoading"
            @click="$emit('navigate-date', 7)"
            title="Next week"
          />
          <Button 
            icon="pi pi-angle-double-right" 
            text 
            size="small"
            :disabled="isLoading"
            @click="$emit('navigate-date', 30)"
            title="Next month"
          />
        </div>

        <!-- Action Buttons -->
        <div class="flex items-center space-x-2">
          <Button 
            icon="pi pi-refresh" 
            label="Refresh"
            severity="secondary"
            outlined
            size="small"
            :loading="isLoading"
            @click="$emit('refresh')"
          />
          <Button 
            icon="pi pi-download" 
            label="Export"
            severity="secondary"
            outlined
            size="small"
            :disabled="isLoading"
            @click="$emit('export')"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
// Composables removed - using direct Tailwind classes

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
defineEmits(['navigate-date', 'refresh', 'export'])

// Template drag state
const isDragging = ref(false)

// Template drag handlers
const handleTemplateDragStart = (event, template) => {
  isDragging.value = true
  
  // Set drag data
  event.dataTransfer.setData('text/plain', JSON.stringify({
    type: 'template',
    template: template
  }))
  
  // Set drag effect
  event.dataTransfer.effectAllowed = 'copy'
  
  // Add visual feedback
  event.target.classList.add('dragging')
  
  console.log(`Started dragging template: ${template}`)
}

const handleTemplateDragEnd = (event) => {
  isDragging.value = false
  event.target.classList.remove('dragging')
  console.log('Template drag ended')
}
</script>

<style scoped>
.template-card {
  @apply flex items-center px-4 py-3 bg-gradient-to-r from-white to-gray-50 border-2 border-transparent rounded-xl cursor-grab text-sm font-semibold text-gray-700 hover:from-blue-50 hover:to-indigo-50 hover:border-blue-300 hover:shadow-lg transform hover:scale-105 transition-all duration-200;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}

.template-card:hover {
  @apply shadow-xl;
  background: linear-gradient(135deg, #dbeafe 0%, #e0e7ff 100%);
}

.template-card.dragging {
  @apply opacity-75 cursor-grabbing scale-110;
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  color: white;
}

.template-card:active {
  @apply cursor-grabbing scale-95;
}

/* Individual template card colors */
.template-card:nth-child(2) {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
}

.template-card:nth-child(2):hover {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
}

.template-card:nth-child(3) {
  background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
}

.template-card:nth-child(3):hover {
  background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
  color: white;
}

.template-card:nth-child(4) {
  background: linear-gradient(135deg, #fed7aa 0%, #fdba74 100%);
}

.template-card:nth-child(4):hover {
  background: linear-gradient(135deg, #ea580c 0%, #dc2626 100%);
  color: white;
}
</style>
