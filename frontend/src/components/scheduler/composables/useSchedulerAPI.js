import { ref, computed } from 'vue'
import { createListResource, createDocumentResource, call } from 'frappe-ui'

export function useSchedulerAPI() {
  const isLoading = ref(false)

  // ===== DOCUMENT RESOURCES =====
  
  // Projects list resource
  const projectsResource = createListResource({
    doctype: 'Project',
    fields: ['name', 'project_name', 'project_type', 'status', 'activities'],
    filters: { status: ['!=', 'Cancelled'] },
    orderBy: 'project_name asc',
    auto: true, // Auto-fetch on creation
    cache: ['projects'] // Cache key
  })

  // Resources list resource
  const resourcesResource = createListResource({
    doctype: 'Resource',
    fields: ['name', 'resource_name', 'resource_type', 'available_capacity', 'status'],
    filters: { status: 'Active' },
    orderBy: 'resource_name asc',
    auto: true,
    cache: ['resources']
  })

  // Roles list resource
  const rolesResource = createListResource({
    doctype: 'Scheduler Role',
    fields: ['name', 'role_name', 'description', 'hourly_rate'],
    orderBy: 'role_name asc',
    auto: true,
    cache: ['roles']
  })

  // Schedule entries resource (dynamic based on date range)
  const createScheduleEntriesResource = (startDate, endDate) => {
    return createListResource({
      doctype: 'Schedule Entry',
      fields: [
        'name', 'date', 'hours', 'start_time', 'end_time', 
        'description', 'status', 'is_night_shift', 'project', 
        'activity', 'resource', 'role', 'schedule_row'
      ],
      filters: {
        date: ['between', [startDate, endDate]]
      },
      orderBy: 'date asc, start_time asc',
      pageLength: 1000, // Large page size for scheduler view
      auto: false // Manual fetch
    })
  }

  // Schedule rows resource
  const scheduleRowsResource = createListResource({
    doctype: 'Schedule Row',
    fields: [
      'name', 'project', 'activity', 'resource', 'role',
      'project_name', 'activity_name', 'resource_name', 'role_name',
      'daily_entries', 'status', 'creation', 'modified'
    ],
    filters: { status: ['!=', 'Archived'] },
    orderBy: 'project asc, activity asc',
    pageLength: 500,
    auto: false
  })

  // ===== COMPUTED PROPERTIES =====
  
  const projects = computed(() => projectsResource.data || [])
  const resources = computed(() => resourcesResource.data || [])
  const roles = computed(() => rolesResource.data || [])
  
  const isLoadingAny = computed(() => 
    projectsResource.loading || 
    resourcesResource.loading || 
    rolesResource.loading ||
    isLoading.value
  )

  // ===== SCHEDULER DATA METHODS =====

  // Load complete scheduler data for a date range
  const loadSchedulerData = async (startDate, dateRange = 30) => {
    isLoading.value = true
    
    try {
      // Calculate end date
      const startDateObj = new Date(startDate)
      const endDateObj = new Date(startDateObj.getTime() + (dateRange * 24 * 60 * 60 * 1000))
      const endDate = endDateObj.toISOString().split('T')[0]
      
      console.log('Loading scheduler data:', { startDate, endDate })
      
      // Use Frappe UI call method for complex data fetching
      const response = await call('erplite.scheduler.api.get_scheduler_data', {
        start_date: startDate,
        end_date: endDate
      })

      console.log('Scheduler data loaded:', response)
      return response
    } catch (error) {
      console.error('Failed to load scheduler data:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  // ===== SCHEDULE ENTRY METHODS =====

  // Create a new schedule entry using document resource
  const createScheduleEntry = async (entryData) => {
    try {
      const newEntry = createDocumentResource({
        doctype: 'Schedule Entry'
      })

      // Set document fields
      Object.assign(newEntry.doc, {
        date: entryData.date,
        hours: entryData.hours,
        start_time: entryData.start_time,
        end_time: entryData.end_time,
        description: entryData.description || '',
        status: entryData.status || 'Planned',
        is_night_shift: entryData.is_night_shift || 0,
        project: entryData.project,
        activity: entryData.activity,
        resource: entryData.resource,
        role: entryData.role,
        schedule_row: entryData.schedule_row
      })

      await newEntry.save()
      console.log('Schedule entry created:', newEntry.doc)
      return newEntry.doc
    } catch (error) {
      console.error('Failed to create schedule entry:', error)
      throw error
    }
  }

  // Update an existing schedule entry
  const updateScheduleEntry = async (entryId, updates) => {
    try {
      const entry = createDocumentResource({
        doctype: 'Schedule Entry',
        name: entryId
      })

      await entry.get() // Fetch current data
      Object.assign(entry.doc, updates) // Apply updates
      await entry.save()
      
      console.log('Schedule entry updated:', entry.doc)
      return entry.doc
    } catch (error) {
      console.error('Failed to update schedule entry:', error)
      throw error
    }
  }

  // Delete a schedule entry
  const deleteScheduleEntry = async (entryId) => {
    try {
      const entry = createDocumentResource({
        doctype: 'Schedule Entry',
        name: entryId
      })

      await entry.delete()
      console.log('Schedule entry deleted:', entryId)
      return { success: true }
    } catch (error) {
      console.error('Failed to delete schedule entry:', error)
      throw error
    }
  }

  // Bulk create multiple schedule entries
  const createBulkScheduleEntries = async (entriesData) => {
    try {
      // The deployed bundle still calls create_bulk_schedule_entries with `entries`; that
      // name is kept as a whitelisted alias in scheduler/api.py so this can be corrected here
      // without having to rebuild the bundle to fix the live site.
      const response = await call('erplite.scheduler.api.bulk_create_entries', {
        entries_data: entriesData
      })
      
      console.log('Bulk entries created:', response)
      return response
    } catch (error) {
      console.error('Failed to create bulk entries:', error)
      throw error
    }
  }

  // ===== SCHEDULE ROW METHODS =====

  // Create a new schedule row
  const createScheduleRow = async (rowData) => {
    try {
      const newRow = createDocumentResource({
        doctype: 'Schedule Row'
      })

      Object.assign(newRow.doc, {
        project: rowData.project,
        activity: rowData.activity,
        resource: rowData.resource,
        role: rowData.role,
        status: 'Active',
        daily_entries: JSON.stringify({}) // Initialize empty daily entries
      })

      await newRow.save()
      console.log('Schedule row created:', newRow.doc)
      return newRow.doc
    } catch (error) {
      console.error('Failed to create schedule row:', error)
      throw error
    }
  }

  // Update schedule row entries (daily entries JSON)
  const updateScheduleRowEntries = async (scheduleRowId, entriesJson) => {
    try {
      const row = createDocumentResource({
        doctype: 'Schedule Row',
        name: scheduleRowId
      })

      await row.get()
      row.doc.daily_entries = JSON.stringify(entriesJson)
      await row.save()
      
      console.log('Schedule row entries updated:', row.doc)
      return row.doc
    } catch (error) {
      console.error('Failed to update schedule row entries:', error)
      throw error
    }
  }

  // Delete/Archive a schedule row
  const deleteScheduleRow = async (rowId) => {
    try {
      const row = createDocumentResource({
        doctype: 'Schedule Row',
        name: rowId
      })

      await row.get()
      row.doc.status = 'Archived'
      await row.save()
      
      console.log('Schedule row archived:', rowId)
      return { success: true }
    } catch (error) {
      console.error('Failed to archive schedule row:', error)
      throw error
    }
  }

  // ===== MASTER DATA METHODS =====

  // Get projects (using resource)
  const getProjects = async () => {
    if (!projectsResource.data) {
      await projectsResource.fetch()
    }
    return projectsResource.data
  }

  // Get resources (using resource)
  const getResources = async () => {
    if (!resourcesResource.data) {
      await resourcesResource.fetch()
    }
    return resourcesResource.data
  }

  // Get roles (using resource)
  const getRoles = async () => {
    if (!rolesResource.data) {
      await rolesResource.fetch()
    }
    return rolesResource.data
  }

  // Refresh all master data
  const refreshMasterData = async () => {
    await Promise.all([
      projectsResource.reload(),
      resourcesResource.reload(),
      rolesResource.reload()
    ])
  }

  // ===== UTILITY METHODS =====

  // Get schedule entries for a date range
  const getScheduleEntries = async (startDate, endDate) => {
    const entriesResource = createScheduleEntriesResource(startDate, endDate)
    await entriesResource.fetch()
    return entriesResource.data || []
  }

  // Get schedule rows
  const getScheduleRows = async () => {
    if (!scheduleRowsResource.data) {
      await scheduleRowsResource.fetch()
    }
    return scheduleRowsResource.data || []
  }

  // Search projects by name
  const searchProjects = async (searchTerm) => {
    const searchResource = createListResource({
      doctype: 'Project',
      fields: ['name', 'project_name', 'project_type'],
      filters: {
        project_name: ['like', `%${searchTerm}%`]
      },
      pageLength: 10
    })
    
    await searchResource.fetch()
    return searchResource.data || []
  }

  return {
    // ===== STATE =====
    isLoading: isLoadingAny,
    
    // ===== RESOURCES =====
    projectsResource,
    resourcesResource,
    rolesResource,
    
    // ===== COMPUTED DATA =====
    projects,
    resources,
    roles,
    
    // ===== SCHEDULER METHODS =====
    loadSchedulerData,
    
    // ===== SCHEDULE ENTRY METHODS =====
    createScheduleEntry,
    updateScheduleEntry,
    deleteScheduleEntry,
    createBulkScheduleEntries,
    getScheduleEntries,
    
    // ===== SCHEDULE ROW METHODS =====
    createScheduleRow,
    updateScheduleRowEntries,
    deleteScheduleRow,
    getScheduleRows,
    
    // ===== MASTER DATA METHODS =====
    getProjects,
    getResources,
    getRoles,
    refreshMasterData,
    
    // ===== UTILITY METHODS =====
    searchProjects,
    createScheduleEntriesResource
  }
}
