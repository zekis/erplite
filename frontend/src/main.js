import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

// Frappe UI
import { frappeRequest, setConfig } from 'frappe-ui'

// PrimeVue
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
// Remove primeicons import - we'll use iconify instead

// PrimeVue Components - Global Registration
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import Toast from 'primevue/toast'
import ToastService from 'primevue/toastservice'

import './index.css'

// Initialize Frappe UI
async function initializeApp() {
  let boot = {}
  
  // Get boot data - either from window (production) or API (development)
  if (window.frappe?.boot) {
    // Production mode - boot data injected by Jinja2
    boot = window.frappe.boot
  } else {
    // Development mode - fetch boot data from API
    try {
      const response = await frappeRequest({
        url: '/api/method/erplite.www.erplite.get_context_for_dev',
        type: 'GET'
      })
      boot = response
    } catch (error) {
      console.error('Failed to get boot data:', error)
      // Fallback for development without backend
      boot = {
        user: 'Administrator',
        csrf_token: 'development-token',
        site_name: 'localhost'
      }
    }
  }
  
  // Configure Frappe UI
  setConfig('resourceFetcher', frappeRequest)
  
  // Store boot data globally
  window.frappe = window.frappe || {}
  window.frappe.boot = boot
  
  // Create and configure Vue app
  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  app.use(router)
app.use(PrimeVue, {
    theme: {
        preset: Aura,
        options: {
            prefix: 'p',
            darkModeSelector: false,
            cssLayer: {
                name: 'primevue',
                order: 'tailwind-base, primevue, tailwind-utilities'
            }
        }
    }
})
app.use(ToastService)

// Register PrimeVue components globally
app.component('Button', Button)
app.component('Card', Card)
app.component('InputText', InputText)
app.component('Textarea', Textarea)
app.component('Dropdown', Dropdown)
app.component('DataTable', DataTable)
app.component('Column', Column)
app.component('Dialog', Dialog)
app.component('Toast', Toast)

  app.mount('#app')
}

// Initialize the app
initializeApp().catch(console.error)
