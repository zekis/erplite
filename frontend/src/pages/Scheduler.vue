<template>
  <div class="min-h-screen bg-gray-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <!-- Header -->
      <div class="mb-8">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-3xl font-bold text-gray-900">Vue.js Scheduler</h1>
            <p class="text-gray-600 mt-1">Modern scheduler built with Vue.js and Frappe UI</p>
          </div>
          <div class="flex space-x-3">
            <button @click="$router.push('/')" class="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50">
              ← Back to Home
            </button>
            <button @click="refreshData" :disabled="loading" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50">
              {{ loading ? 'Loading...' : 'Refresh Data' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Stats Cards -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <div class="w-8 h-8 bg-blue-100 rounded-md flex items-center justify-center">
                <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                </svg>
              </div>
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">Total Tasks</p>
              <p class="text-2xl font-semibold text-gray-900">{{ stats.totalTasks }}</p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <div class="w-8 h-8 bg-green-100 rounded-md flex items-center justify-center">
                <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
              </div>
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">Completed</p>
              <p class="text-2xl font-semibold text-gray-900">{{ stats.completedTasks }}</p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <div class="w-8 h-8 bg-yellow-100 rounded-md flex items-center justify-center">
                <svg class="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
              </div>
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">Pending</p>
              <p class="text-2xl font-semibold text-gray-900">{{ stats.pendingTasks }}</p>
            </div>
          </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center">
            <div class="flex-shrink-0">
              <div class="w-8 h-8 bg-red-100 rounded-md flex items-center justify-center">
                <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"></path>
                </svg>
              </div>
            </div>
            <div class="ml-4">
              <p class="text-sm font-medium text-gray-500">High Priority</p>
              <p class="text-2xl font-semibold text-gray-900">{{ stats.highPriorityTasks }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Task Management -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Task Form -->
        <div class="lg:col-span-1">
          <div class="bg-white rounded-lg shadow p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Add New Task</h2>
            
            <form @submit.prevent="addTask" class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">
                  Task Title
                </label>
                <input
                  v-model="newTask.title"
                  type="text"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter task title..."
                  required
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">
                  Priority
                </label>
                <select
                  v-model="newTask.priority"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  v-model="newTask.description"
                  rows="3"
                  class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Optional description..."
                ></textarea>
              </div>

              <button
                type="submit"
                :disabled="addingTask"
                class="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {{ addingTask ? 'Adding...' : 'Add Task' }}
              </button>
            </form>
          </div>
        </div>

        <!-- Task List -->
        <div class="lg:col-span-2">
          <div class="bg-white rounded-lg shadow">
            <div class="px-6 py-4 border-b border-gray-200">
              <div class="flex items-center justify-between">
                <h2 class="text-lg font-semibold text-gray-900">Task List</h2>
                <div class="flex space-x-2">
                  <button
                    @click="filter = 'all'"
                    :class="[
                      'px-3 py-1 text-sm rounded-md',
                      filter === 'all'
                        ? 'bg-blue-100 text-blue-700'
                        : 'text-gray-500 hover:text-gray-700'
                    ]"
                  >
                    All
                  </button>
                  <button
                    @click="filter = 'active'"
                    :class="[
                      'px-3 py-1 text-sm rounded-md',
                      filter === 'active'
                        ? 'bg-blue-100 text-blue-700'
                        : 'text-gray-500 hover:text-gray-700'
                    ]"
                  >
                    Active
                  </button>
                  <button
                    @click="filter = 'completed'"
                    :class="[
                      'px-3 py-1 text-sm rounded-md',
                      filter === 'completed'
                        ? 'bg-blue-100 text-blue-700'
                        : 'text-gray-500 hover:text-gray-700'
                    ]"
                  >
                    Completed
                  </button>
                </div>
              </div>
            </div>

            <div class="divide-y divide-gray-200">
              <div
                v-for="task in filteredTasks"
                :key="task.id"
                class="px-6 py-4 hover:bg-gray-50 transition-colors"
              >
                <div class="flex items-center justify-between">
                  <div class="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      :checked="task.completed"
                      @change="toggleTask(task.id)"
                      class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <div :class="{ 'line-through text-gray-500': task.completed }">
                      <p class="font-medium">{{ task.title }}</p>
                      <p class="text-sm text-gray-500">
                        Priority: {{ task.priority }} | 
                        Created: {{ formatDate(task.created_at) }}
                      </p>
                    </div>
                  </div>
                  
                  <div class="flex items-center space-x-2">
                    <span
                      :class="[
                        'px-2 py-1 text-xs rounded-full',
                        task.priority === 'high'
                          ? 'bg-red-100 text-red-800'
                          : task.priority === 'medium'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-green-100 text-green-800'
                      ]"
                    >
                      {{ task.priority }}
                    </span>
                    
                    <button
                      @click="deleteTask(task.id)"
                      class="px-2 py-1 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>

              <div v-if="filteredTasks.length === 0" class="px-6 py-12 text-center">
                <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                </svg>
                <p class="mt-2 text-sm text-gray-500">No tasks found</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Comparison Note -->
      <div class="mt-12 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <div class="flex">
          <div class="flex-shrink-0">
            <svg class="h-5 w-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>
            </svg>
          </div>
          <div class="ml-3">
            <h3 class="text-sm font-medium text-blue-800">
              Vue.js Implementation Benefits
            </h3>
            <div class="mt-2 text-sm text-blue-700">
              <p>
                This scheduler demonstrates how much cleaner and more maintainable Vue.js code is compared to the pure JavaScript version. 
                Notice the reactive state management, component-based architecture, and declarative templates that make the code easier to understand and modify.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

// Reactive state
const tasks = ref([])
const newTask = ref({
  title: '',
  priority: 'medium',
  description: ''
})
const filter = ref('all')
const loading = ref(false)
const addingTask = ref(false)

// Computed properties
const filteredTasks = computed(() => {
  switch (filter.value) {
    case 'active':
      return tasks.value.filter(task => !task.completed)
    case 'completed':
      return tasks.value.filter(task => task.completed)
    default:
      return tasks.value
  }
})

const stats = computed(() => ({
  totalTasks: tasks.value.length,
  completedTasks: tasks.value.filter(t => t.completed).length,
  pendingTasks: tasks.value.filter(t => !t.completed).length,
  highPriorityTasks: tasks.value.filter(t => t.priority === 'high' && !t.completed).length
}))

// Methods
const loadTasks = async () => {
  loading.value = true
  try {
    const response = await fetch('/api/method/erplite.vue_test.api.get_tasks')
    const data = await response.json()
    if (data.message && data.message.success) {
      tasks.value = data.message.data
    }
  } catch (error) {
    console.error('Error loading tasks:', error)
  } finally {
    loading.value = false
  }
}

const addTask = async () => {
  if (!newTask.value.title.trim()) return
  
  addingTask.value = true
  try {
    const response = await fetch('/api/method/erplite.vue_test.api.create_task', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: newTask.value.title,
        priority: newTask.value.priority,
        description: newTask.value.description
      })
    })
    
    const data = await response.json()
    if (data.message && data.message.success) {
      tasks.value.push(data.message.data)
      newTask.value = { title: '', priority: 'medium', description: '' }
    }
  } catch (error) {
    console.error('Error adding task:', error)
  } finally {
    addingTask.value = false
  }
}

const toggleTask = async (taskId) => {
  const task = tasks.value.find(t => t.id === taskId)
  if (task) {
    task.completed = !task.completed
    // In a real app, you'd update the backend here
  }
}

const deleteTask = async (taskId) => {
  if (confirm('Are you sure you want to delete this task?')) {
    tasks.value = tasks.value.filter(t => t.id !== taskId)
    // In a real app, you'd delete from backend here
  }
}

const refreshData = () => {
  loadTasks()
}

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString()
}

// Lifecycle
onMounted(() => {
  loadTasks()
})
</script>
