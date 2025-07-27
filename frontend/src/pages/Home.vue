<template>
  <div class="min-h-screen bg-gray-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <!-- Header -->
      <div class="text-center mb-12">
        <h1 class="text-4xl font-bold text-gray-900 mb-4">
          Welcome to ERPLite Vue.js Frontend
        </h1>
        <p class="text-xl text-gray-600 max-w-3xl mx-auto">
          This is a modern Vue.js frontend built with Vite, Frappe UI, and Tailwind CSS.
          It demonstrates the proper way to build Vue applications in Frappe.
        </p>
      </div>

      <!-- Feature Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
            </svg>
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">Vue.js 3</h3>
          <p class="text-gray-600">
            Built with the latest Vue.js 3 using Composition API for better performance and developer experience.
          </p>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">Frappe UI</h3>
          <p class="text-gray-600">
            Integrated with Frappe UI components for consistent design and seamless backend integration.
          </p>
        </div>

        <div class="bg-white rounded-lg shadow-md p-6">
          <div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zM21 5a2 2 0 00-2-2h-4a2 2 0 00-2 2v12a4 4 0 004 4h4a2 2 0 002-2V5z"></path>
            </svg>
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">Modern Tooling</h3>
          <p class="text-gray-600">
            Vite for fast development, Tailwind CSS for styling, and Pinia for state management.
          </p>
        </div>
      </div>

      <!-- Demo Section -->
      <div class="bg-white rounded-lg shadow-md p-8 mb-12">
        <h2 class="text-2xl font-bold text-gray-900 mb-6">Interactive Demo</h2>
        
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <!-- Task Counter -->
          <div class="space-y-4">
            <h3 class="text-lg font-semibold text-gray-900">Reactive State Demo</h3>
            <div class="flex items-center space-x-4">
              <Button @click="decrementTasks" severity="secondary" size="small">-</Button>
              <span class="text-2xl font-bold text-blue-600">{{ taskCount }}</span>
              <Button @click="incrementTasks" size="small">+</Button>
            </div>
            <p class="text-sm text-gray-600">
              Tasks: {{ taskCount }} | Status: {{ taskStatus }}
            </p>
          </div>

          <!-- API Demo -->
          <div class="space-y-4">
            <h3 class="text-lg font-semibold text-gray-900">API Integration Demo</h3>
            <div class="flex space-x-2">
              <Button @click="testAPI" :loading="apiLoading" :label="apiLoading ? 'Testing...' : 'Test API Connection'" />
            </div>
            <div v-if="apiResponse" class="p-3 bg-gray-50 rounded-md">
              <pre class="text-sm text-gray-700">{{ JSON.stringify(apiResponse, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </div>

      <!-- PrimeVue Advanced Components Demo -->
      <div class="bg-white rounded-lg shadow-md p-8 mb-12">
        <h2 class="text-2xl font-bold text-gray-900 mb-6">PrimeVue Advanced Components Demo</h2>
        
        <!-- Customer Management Interface -->
        <div class="space-y-6">
          <!-- Header with Search and Actions -->
          <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <h3 class="text-xl font-semibold text-gray-900 flex items-center gap-2">
                <i class="pi pi-users text-blue-600"></i>
                Customers
              </h3>
              <p class="text-gray-600 text-sm">The analysis list here shows all users</p>
            </div>
            <div class="flex items-center gap-2">
              <span class="flex items-center gap-2 text-sm text-gray-600">
                <span class="w-2 h-2 bg-green-500 rounded-full"></span>
                {{ customers.filter(c => c.status === 'Active').length }} Active Users
              </span>
            </div>
          </div>

          <!-- Search and Filter Bar -->
          <div class="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
            <div class="relative flex-1">
              <i class="pi pi-search absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"></i>
              <InputText 
                v-model="searchQuery" 
                placeholder="Search customers..." 
                class="w-full pl-10"
              />
            </div>
            <div class="flex gap-2">
              <Button icon="pi pi-filter" outlined />
              <Button icon="pi pi-refresh" outlined @click="refreshCustomers" />
            </div>
          </div>

          <!-- Advanced DataTable -->
          <DataTable 
            :value="filteredCustomers" 
            :paginator="true" 
            :rows="10"
            :rowsPerPageOptions="[5, 10, 20]"
            paginatorTemplate="RowsPerPageDropdown FirstPageLink PrevPageLink CurrentPageReport NextPageLink LastPageLink"
            currentPageReportTemplate="{first} to {last} of {totalRecords}"
            class="p-datatable-sm"
            stripedRows
            :loading="loading"
          >
            <Column selectionMode="multiple" headerStyle="width: 3rem"></Column>
            
            <Column field="name" header="Name" sortable>
              <template #body="slotProps">
                <div class="flex items-center gap-3">
                  <img 
                    :src="slotProps.data.avatar" 
                    :alt="slotProps.data.name"
                    class="w-8 h-8 rounded-full object-cover"
                  />
                  <div>
                    <div class="font-medium text-gray-900">{{ slotProps.data.name }}</div>
                    <div class="text-sm text-gray-500">{{ slotProps.data.title }}</div>
                  </div>
                </div>
              </template>
            </Column>
            
            <Column field="company" header="Company" sortable>
              <template #body="slotProps">
                <div class="flex items-center gap-2">
                  <i :class="slotProps.data.companyIcon" class="text-gray-600"></i>
                  <span>{{ slotProps.data.company }}</span>
                </div>
              </template>
            </Column>
            
            <Column field="email" header="Email Address" sortable>
              <template #body="slotProps">
                <a :href="`mailto:${slotProps.data.email}`" class="text-blue-600 hover:text-blue-800">
                  {{ slotProps.data.email }}
                </a>
              </template>
            </Column>
            
            <Column field="leadSource" header="Lead Source" sortable>
              <template #body="slotProps">
                <span class="text-gray-600">{{ slotProps.data.leadSource }}</span>
              </template>
            </Column>
            
            <Column field="status" header="Status" sortable>
              <template #body="slotProps">
                <span 
                  :class="[
                    'px-2 py-1 text-xs font-medium rounded-full',
                    slotProps.data.status === 'Active' 
                      ? 'bg-green-100 text-green-800' 
                      : slotProps.data.status === 'Prospect'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-red-100 text-red-800'
                  ]"
                >
                  {{ slotProps.data.status }}
                </span>
              </template>
            </Column>
            
            <Column header="Actions">
              <template #body="slotProps">
                <Button 
                  icon="pi pi-search" 
                  text 
                  rounded 
                  severity="secondary" 
                  @click="viewCustomer(slotProps.data)"
                />
              </template>
            </Column>
          </DataTable>

          <!-- Additional PrimeVue Components Showcase -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
            <!-- Toast Demo -->
            <div class="space-y-3">
              <h4 class="font-semibold text-gray-900">Toast Notifications</h4>
              <div class="flex flex-wrap gap-2">
                <Button label="Success" severity="success" size="small" @click="showSuccess" />
                <Button label="Info" severity="info" size="small" @click="showInfo" />
                <Button label="Warning" severity="warning" size="small" @click="showWarn" />
                <Button label="Error" severity="danger" size="small" @click="showError" />
              </div>
            </div>

            <!-- Dialog Demo -->
            <div class="space-y-3">
              <h4 class="font-semibold text-gray-900">Dialog</h4>
              <Button label="Show Dialog" @click="showDialog = true" />
            </div>

            <!-- Form Components -->
            <div class="space-y-3">
              <h4 class="font-semibold text-gray-900">Form Components</h4>
              <InputText v-model="testInput" placeholder="Type something..." class="w-full" />
              <Dropdown 
                v-model="selectedStatus" 
                :options="statusOptions" 
                optionLabel="label" 
                placeholder="Select Status" 
                class="w-full" 
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Customer Detail Dialog -->
      <Dialog 
        v-model:visible="showDialog" 
        modal 
        header="Customer Details" 
        :style="{ width: '50rem' }"
        :breakpoints="{ '1199px': '75vw', '575px': '90vw' }"
      >
        <div v-if="selectedCustomer" class="space-y-4">
          <div class="flex items-center gap-4">
            <img 
              :src="selectedCustomer.avatar" 
              :alt="selectedCustomer.name"
              class="w-16 h-16 rounded-full object-cover"
            />
            <div>
              <h3 class="text-xl font-semibold">{{ selectedCustomer.name }}</h3>
              <p class="text-gray-600">{{ selectedCustomer.title }} at {{ selectedCustomer.company }}</p>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700">Email</label>
              <p class="text-gray-900">{{ selectedCustomer.email }}</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700">Status</label>
              <span 
                :class="[
                  'px-2 py-1 text-xs font-medium rounded-full',
                  selectedCustomer.status === 'Active' 
                    ? 'bg-green-100 text-green-800' 
                    : selectedCustomer.status === 'Prospect'
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-red-100 text-red-800'
                ]"
              >
                {{ selectedCustomer.status }}
              </span>
            </div>
          </div>
        </div>
        <template #footer>
          <Button label="Close" @click="showDialog = false" />
          <Button label="Edit" severity="success" @click="editCustomer" />
        </template>
      </Dialog>

      <!-- Toast Component -->
      <Toast />

      <!-- Navigation -->
      <div class="text-center">
        <h2 class="text-2xl font-bold text-gray-900 mb-6">Explore the App</h2>
        <div class="flex justify-center space-x-4">
          <Button @click="$router.push('/scheduler')" label="View Scheduler (Vue.js)" size="large" />
          <Button @click="openLegacyScheduler" label="Legacy Scheduler (Pure JS)" severity="secondary" size="large" />
        </div>
      </div>

      <!-- Comparison Section -->
      <div class="mt-16 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-8">
        <h2 class="text-2xl font-bold text-gray-900 mb-6 text-center">
          Vue.js vs Pure JavaScript Comparison
        </h2>
        
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div class="bg-white rounded-lg p-6">
            <h3 class="text-lg font-semibold text-green-600 mb-4">✅ Vue.js Advantages</h3>
            <ul class="space-y-2 text-sm text-gray-700">
              <li>• Reactive state management</li>
              <li>• Component-based architecture</li>
              <li>• Declarative templates</li>
              <li>• Built-in routing and state management</li>
              <li>• Hot module replacement</li>
              <li>• TypeScript support</li>
              <li>• Rich ecosystem and tooling</li>
              <li>• Better testing capabilities</li>
            </ul>
          </div>
          
          <div class="bg-white rounded-lg p-6">
            <h3 class="text-lg font-semibold text-red-600 mb-4">❌ Pure JS Challenges</h3>
            <ul class="space-y-2 text-sm text-gray-700">
              <li>• Manual DOM manipulation</li>
              <li>• Complex state synchronization</li>
              <li>• Event listener management</li>
              <li>• No component reusability</li>
              <li>• Difficult debugging</li>
              <li>• Hard to maintain and scale</li>
              <li>• No build-time optimizations</li>
              <li>• Limited testing options</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useToast } from 'primevue/usetoast'

const $toast = useToast()

// Reactive state
const taskCount = ref(5)
const apiLoading = ref(false)
const apiResponse = ref(null)

// PrimeVue test data
const testInput = ref('')
const testTextarea = ref('')
const selectedCity = ref(null)
const cities = ref([
  { name: 'New York', code: 'NY' },
  { name: 'Rome', code: 'RM' },
  { name: 'London', code: 'LDN' },
  { name: 'Istanbul', code: 'IST' },
  { name: 'Paris', code: 'PRS' }
])

// Advanced demo data
const searchQuery = ref('')
const loading = ref(false)
const showDialog = ref(false)
const selectedCustomer = ref(null)
const selectedStatus = ref(null)

const statusOptions = ref([
  { label: 'Active', value: 'Active' },
  { label: 'Inactive', value: 'Inactive' },
  { label: 'Prospect', value: 'Prospect' }
])

const customers = ref([
  {
    id: 1,
    name: 'Brook Simmons',
    title: 'Sales Executive',
    company: 'Mistranet',
    companyIcon: 'pi pi-building',
    email: 'hi@brooksmmns.co',
    leadSource: 'LinkedIn',
    status: 'Active',
    avatar: 'https://images.unsplash.com/photo-1494790108755-2616b612b786?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 2,
    name: 'Dianne Russell',
    title: 'CEO',
    company: 'BriteMonk',
    companyIcon: 'pi pi-star',
    email: 'hi@diannerussell.com',
    leadSource: 'Website',
    status: 'Inactive',
    avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 3,
    name: 'Amy Elsner',
    title: 'Product Manager',
    company: 'ZenTrailMs',
    companyIcon: 'pi pi-compass',
    email: 'hi@amyelsner.com',
    leadSource: 'Cold Call',
    status: 'Prospect',
    avatar: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 4,
    name: 'Jacob Jones',
    title: 'Manager',
    company: 'Streamlinz',
    companyIcon: 'pi pi-chart-line',
    email: 'jacobjones@gmail.com',
    leadSource: 'Partner',
    status: 'Prospect',
    avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 5,
    name: 'Cameron Watson',
    title: 'Product Manager',
    company: 'BriteMonk',
    companyIcon: 'pi pi-star',
    email: 'hi@cameronwilliamson',
    leadSource: 'Social Media',
    status: 'Active',
    avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 6,
    name: 'Wade Warren',
    title: 'Director',
    company: 'Streamlinz',
    companyIcon: 'pi pi-chart-line',
    email: 'hi@annetteblack.com',
    leadSource: 'Cold Call',
    status: 'Inactive',
    avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 7,
    name: 'Guy Hawkins',
    title: 'Director',
    company: 'Wavelength',
    companyIcon: 'pi pi-wave-pulse',
    email: 'hi@darrellsteward.com',
    leadSource: 'LinkedIn',
    status: 'Active',
    avatar: 'https://images.unsplash.com/photo-1519345182560-3f2917c472ef?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 8,
    name: 'Annette Black',
    title: 'Manager',
    company: 'Wavelength',
    companyIcon: 'pi pi-wave-pulse',
    email: 'jeromebell@gmail.com',
    leadSource: 'Website',
    status: 'Inactive',
    avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 9,
    name: 'Darrell Steward',
    title: 'Product Manager',
    company: 'ZenTrailMs',
    companyIcon: 'pi pi-compass',
    email: 'hi@onyamalimba.co',
    leadSource: 'Website',
    status: 'Active',
    avatar: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 10,
    name: 'Jerome Bell',
    title: 'Marketing Manager',
    company: 'Mistranet',
    companyIcon: 'pi pi-building',
    email: 'hi@courtneyhenryo',
    leadSource: 'Social Media',
    status: 'Active',
    avatar: 'https://images.unsplash.com/photo-1507591064344-4c6ce005b128?w=150&h=150&fit=crop&crop=face'
  },
  {
    id: 11,
    name: 'Onyama Limba',
    title: 'Sales Executive',
    company: 'BriteMonk',
    companyIcon: 'pi pi-star',
    email: 'hi@orlenemccoy.com',
    leadSource: 'Social Media',
    status: 'Active',
    avatar: 'https://images.unsplash.com/photo-1531427186611-ecfd6d936c79?w=150&h=150&fit=crop&crop=face'
  }
])

// Computed properties
const taskStatus = computed(() => {
  if (taskCount.value === 0) return 'No tasks'
  if (taskCount.value < 5) return 'Few tasks'
  if (taskCount.value < 10) return 'Some tasks'
  return 'Many tasks'
})

const filteredCustomers = computed(() => {
  if (!searchQuery.value) return customers.value
  
  const query = searchQuery.value.toLowerCase()
  return customers.value.filter(customer => 
    customer.name.toLowerCase().includes(query) ||
    customer.email.toLowerCase().includes(query) ||
    customer.company.toLowerCase().includes(query) ||
    customer.title.toLowerCase().includes(query)
  )
})

// Methods
const incrementTasks = () => {
  taskCount.value++
}

const decrementTasks = () => {
  if (taskCount.value > 0) {
    taskCount.value--
  }
}

const testAPI = async () => {
  apiLoading.value = true
  try {
    const response = await fetch('/api/method/erplite.vue_test.api.test_connection')
    const data = await response.json()
    apiResponse.value = data
  } catch (error) {
    apiResponse.value = { error: error.message }
  } finally {
    apiLoading.value = false
  }
}

const openLegacyScheduler = () => {
  window.open('/scheduler', '_blank')
}

// Advanced demo methods
const refreshCustomers = () => {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    showSuccess('Customer data refreshed successfully!')
  }, 1000)
}

const viewCustomer = (customer) => {
  selectedCustomer.value = customer
  showDialog.value = true
}

const editCustomer = () => {
  showInfo(`Editing ${selectedCustomer.value.name}...`)
  showDialog.value = false
}

// Toast methods
const showSuccess = (message = 'Success! Operation completed.') => {
  $toast.add({ severity: 'success', summary: 'Success', detail: message, life: 3000 })
}

const showInfo = (message = 'Info: Here is some information.') => {
  $toast.add({ severity: 'info', summary: 'Info', detail: message, life: 3000 })
}

const showWarn = (message = 'Warning: Please check your input.') => {
  $toast.add({ severity: 'warn', summary: 'Warning', detail: message, life: 3000 })
}

const showError = (message = 'Error: Something went wrong.') => {
  $toast.add({ severity: 'error', summary: 'Error', detail: message, life: 3000 })
}
</script>
