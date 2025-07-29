import { ref } from 'vue'
import { call } from 'frappe-ui'

export function useSchedulerAPI() {
  const isLoading = ref(false)

  // Get CSRF token from various possible sources
  const getCSRFToken = () => {
    // Try multiple sources for CSRF token
    return window.csrf_token || 
           document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
           document.cookie.split('; ').find(row => row.startsWith('csrf_token='))?.split('=')[1] ||
           ''
  }

  // Make API call to Frappe backend with improved error handling
  const apiCall = async (method, args = {}) => {
    try {
      console.log('API Call:', method, 'Args:', args)
      
      const csrfToken = getCSRFToken()
      console.log('Using CSRF token:', csrfToken ? 'Present' : 'Missing')
      
      const response = await fetch('/api/method/' + method, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': csrfToken,
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(args),
        credentials: 'same-origin'
      })

      console.log('API Response status:', response.status)

      if (!response.ok) {
        const errorText = await response.text()
        console.error('API Error Response:', errorText)
        
        // Handle specific error cases
        if (response.status === 403) {
          throw new Error('Authentication failed. Please refresh the page and try again.')
        } else if (response.status === 404) {
          throw new Error('API endpoint not found. Please check if the scheduler module is installed.')
        } else {
          throw new Error(`HTTP error! status: ${response.status} - ${errorText}`)
        }
      }

      const data = await response.json()
      console.log('API Response data:', data)
      
      if (data.exc) {
        console.error('Frappe Exception:', data.exc)
        throw new Error(data.exc)
      }

      return data.message
    } catch (error) {
      console.error('API call failed:', error)
      throw error
    }
  }

  // Load scheduler data from API using Frappe UI
  const loadSchedulerData = async (startDate, dateRange = 30) => {
    isLoading.value = true
    
    try {
      // Calculate end_date from start_date and dateRange
      const startDateObj = new Date(startDate)
      const endDateObj = new Date(startDateObj.getTime() + (dateRange * 24 * 60 * 60 * 1000))
      const endDate = endDateObj.toISOString().split('T')[0]
      
      console.log('Frappe UI API Call: get_scheduler_data', { start_date: startDate, end_date: endDate })
      
      const response = await call('erplite.scheduler.api.get_scheduler_data', {
        start_date: startDate,
        end_date: endDate
      })

      console.log('Frappe UI API Response:', response)
      return response
    } catch (error) {
      console.error('Failed to load scheduler data:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  // Create a new schedule entry
  const createScheduleEntry = async (entryData) => {
    isLoading.value = true
    
    try {
      const response = await apiCall('erplite.scheduler.api.create_schedule_entry', {
        data: JSON.stringify(entryData)
      })

      return response
    } catch (error) {
      console.warn('API not available for creating entries, using sample data mode:', error)
      // Return success for UI development
      return { success: true, message: 'Entry created (sample mode)' }
    } finally {
      isLoading.value = false
    }
  }

  // Update an existing schedule entry
  const updateScheduleEntry = async (entryId, updates) => {
    isLoading.value = true
    
    try {
      const response = await apiCall('erplite.scheduler.api.update_schedule_entry', {
        name: entryId,
        data: JSON.stringify(updates)
      })

      return response
    } catch (error) {
      console.error('Failed to update schedule entry:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  // Delete a schedule entry
  const deleteScheduleEntry = async (entryId) => {
    isLoading.value = true
    
    try {
      const response = await apiCall('erplite.scheduler.api.delete_schedule_entry', {
        name: entryId
      })

      return response
    } catch (error) {
      console.error('Failed to delete schedule entry:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  // Create or update schedule row
  const createScheduleRow = async (rowData) => {
    isLoading.value = true
    
    try {
      const response = await apiCall('erplite.scheduler.api.create_schedule_row_entry', {
        project: rowData.project,
        activity: rowData.activity,
        resource: rowData.resource,
        role: rowData.role
      })

      return response
    } catch (error) {
      console.error('Failed to create schedule row:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  // Update schedule row entries (daily entries JSON)
  const updateScheduleRowEntries = async (scheduleRowId, entriesJson) => {
    isLoading.value = true
    
    try {
      const response = await apiCall('erplite.scheduler.api.update_schedule_row_entries', {
        schedule_row: scheduleRowId,
        entries_json: JSON.stringify(entriesJson)
      })

      return response
    } catch (error) {
      console.error('Failed to update schedule row entries:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  // Get projects data
  const getProjects = async () => {
    try {
      const response = await apiCall('erplite.scheduler.api.get_projects')
      return response
    } catch (error) {
      console.error('Failed to get projects:', error)
      throw error
    }
  }

  // Get resources data
  const getResources = async () => {
    try {
      const response = await apiCall('erplite.scheduler.api.get_resources')
      return response
    } catch (error) {
      console.error('Failed to get resources:', error)
      throw error
    }
  }

  // Get roles data
  const getRoles = async () => {
    try {
      const response = await apiCall('erplite.scheduler.api.get_roles')
      return response
    } catch (error) {
      console.error('Failed to get roles:', error)
      throw error
    }
  }

  return {
    // State
    isLoading,
    
    // Methods
    apiCall,
    loadSchedulerData,
    createScheduleEntry,
    updateScheduleEntry,
    deleteScheduleEntry,
    createScheduleRow,
    updateScheduleRowEntries,
    getProjects,
    getResources,
    getRoles
  }
}
