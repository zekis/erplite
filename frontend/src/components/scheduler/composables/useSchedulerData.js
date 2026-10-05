import { ref, reactive } from 'vue'
import { format } from 'date-fns'
import { call } from 'frappe-ui'

export function useSchedulerData() {
  // Reactive state
  const scheduleRows = ref([])
  const projects = ref([])
  const resources = ref([])
  const roles = ref([])
  const projectColors = ref({})
  const currentStartDate = ref(format(new Date(), 'yyyy-MM-dd'))
  const dateRange = ref(30)

  // Load initial data from API using Frappe UI
  const loadInitialData = async () => {
    try {
      // Load basic data first
      const schedulerData = await call('erplite.scheduler.api.get_scheduler_data')
      
      if (schedulerData) {
        projects.value = schedulerData.projects || []
        resources.value = schedulerData.resources || []
        roles.value = schedulerData.roles || []
        projectColors.value = schedulerData.project_colors || {}
        
        // Set date range from API response
        if (schedulerData.date_range) {
          currentStartDate.value = schedulerData.date_range.start_date
        }
        
        console.log('Loaded basic data from API:')
        console.log('- Projects:', projects.value.length)
        console.log('- Resources:', resources.value.length)
        console.log('- Roles:', roles.value.length)
      }
      
      // Load existing schedule rows from the Schedule Row doctype
      const scheduleRowsData = await call('erplite.scheduler.api.get_schedule_rows', {
        start_date: currentStartDate.value,
        end_date: schedulerData?.date_range?.end_date
      })
      
      if (scheduleRowsData && scheduleRowsData.length > 0) {
        scheduleRows.value = processScheduleRowsData(scheduleRowsData)
        console.log('Loaded existing schedule rows:', scheduleRowsData.length)
      } else {
        // No existing schedule rows - create project headers with empty rows
        createProjectHeaders()
        console.log('No existing schedule rows, created project headers')
      }

    } catch (error) {
      console.warn('Failed to load data from API, using sample data:', error)
      setDefaultData()
    }
  }
  
  // Process Schedule Row data from the backend
  const processScheduleRowsData = (scheduleRowsData) => {
    const rows = []
    let rowId = 1
    const projectGroups = {}
    
    // Group schedule rows by project
    scheduleRowsData.forEach(row => {
      if (!projectGroups[row.project]) {
        projectGroups[row.project] = []
      }
      projectGroups[row.project].push(row)
    })
    
    // Create rows for each project group
    Object.keys(projectGroups).forEach(projectName => {
      const project = projects.value.find(p => p.name === projectName)
      
      // Add ONE project header per project
      rows.push({
        id: rowId++,
        type: 'project-header',
        project: projectName,
        projectName: project?.project_name || projectName,
        activity: null,
        activityName: null,
        resource: null,
        resourceName: null,
        role: null,
        roleName: null,
        entries: [],
        dailyEntries: {}
      })
      
      // Add existing schedule rows for this project (no duplicates)
      projectGroups[projectName].forEach(scheduleRow => {
        rows.push({
          id: rowId++,
          type: 'activity-row',
          project: scheduleRow.project,
          projectName: project?.project_name || projectName, // Keep project name for component logic
          activity: scheduleRow.activity,
          activityName: scheduleRow.activity_name,
          resource: scheduleRow.resource,
          resourceName: scheduleRow.resource_name,
          role: scheduleRow.role,
          roleName: scheduleRow.role_name,
          scheduleRowId: scheduleRow.name, // Store the backend ID
          entries: [],
          dailyEntries: scheduleRow.daily_entries ? expandDailyEntries(scheduleRow.daily_entries) : {}
        })
      })
      
      // Add ONE empty row under each project for new entries
      rows.push({
        id: rowId++,
        type: 'activity-row',
        project: projectName,
        projectName: project?.project_name || projectName, // Keep project name for component logic
        activity: null,
        activityName: null,
        resource: null,
        resourceName: null,
        role: null,
        roleName: null,
        entries: [],
        dailyEntries: {}
      })
    })
    
    return rows
  }
  
  // Create project headers when no schedule rows exist
  const createProjectHeaders = () => {
    const rows = []
    let rowId = 1
    
    // Create a header and empty row for each project
    projects.value.forEach(project => {
      // Add project header
      rows.push({
        id: rowId++,
        type: 'project-header',
        project: project.name,
        projectName: project.project_name,
        activity: null,
        activityName: null,
        resource: null,
        resourceName: null,
        role: null,
        roleName: null,
        entries: [],
        dailyEntries: {}
      })
      
      // Add one empty row under each project
      rows.push({
        id: rowId++,
        type: 'activity-row',
        project: project.name,
        projectName: project.project_name,
        activity: null,
        activityName: null,
        resource: null,
        resourceName: null,
        role: null,
        roleName: null,
        entries: [],
        dailyEntries: {}
      })
    })
    
    scheduleRows.value = rows
  }
  
  // Create empty schedule rows for projects when no entries exist
  const createEmptyScheduleRows = () => {
    const rows = []
    let rowId = 1
    
    // Create rows for each project
    projects.value.forEach(project => {
      // Add project header
      rows.push({
        id: rowId++,
        type: 'project-header',
        project: project.name,
        projectName: project.project_name,
        activity: null,
        activityName: null,
        resource: null,
        resourceName: null,
        role: null,
        roleName: null,
        entries: [],
        dailyEntries: {}
      })
      
      // Add empty activity rows for each activity
      if (project.activities && project.activities.length > 0) {
        project.activities.forEach(activity => {
          rows.push({
            id: rowId++,
            type: 'activity-row',
            project: project.name,
            projectName: project.project_name,
            activity: activity.name,
            activityName: activity.activity_name,
            resource: null,
            resourceName: null,
            role: null,
            roleName: null,
            entries: [],
            dailyEntries: {}
          })
        })
      } else {
        // Add one empty activity row for projects without activities
        rows.push({
          id: rowId++,
          type: 'activity-row',
          project: project.name,
          projectName: project.project_name,
          activity: null,
          activityName: null,
          resource: null,
          resourceName: null,
          role: null,
          roleName: null,
          entries: [],
          dailyEntries: {}
        })
      }
    })
    
    // Always add one completely empty row at the end
    rows.push({
      id: rowId++,
      type: 'activity-row',
      project: null,
      projectName: null,
      activity: null,
      activityName: null,
      resource: null,
      resourceName: null,
      role: null,
      roleName: null,
      entries: [],
      dailyEntries: {}
    })
    
    scheduleRows.value = rows
    console.log('Created empty schedule rows:', rows.length)
  }

  // Set default data for development/testing
  const setDefaultData = () => {
    projects.value = [
      {
        name: 'PROJ-001',
        project_name: 'Sample Project 1',
        status: 'Active',
        activities: [
          { name: 'ACT-001', activity_name: 'Planning' },
          { name: 'ACT-002', activity_name: 'Development' },
          { name: 'ACT-003', activity_name: 'Testing' }
        ]
      },
      {
        name: 'PROJ-002',
        project_name: 'Sample Project 2',
        status: 'Active',
        activities: [
          { name: 'ACT-004', activity_name: 'Design' },
          { name: 'ACT-005', activity_name: 'Implementation' }
        ]
      }
    ]

    resources.value = [
      { name: 'RES-001', resource_name: 'John Doe', resource_type: 'Developer' },
      { name: 'RES-002', resource_name: 'Jane Smith', resource_type: 'Designer' },
      { name: 'RES-003', resource_name: 'Bob Johnson', resource_type: 'Tester' }
    ]

    roles.value = [
      { name: 'ROLE-001', role_name: 'Senior Developer' },
      { name: 'ROLE-002', role_name: 'Junior Developer' },
      { name: 'ROLE-003', role_name: 'Project Manager' }
    ]

    projectColors.value = {
      'PROJ-001': '#3b82f6',
      'PROJ-002': '#10b981'
    }

    // Add some sample schedule rows
    scheduleRows.value = [
      {
        id: 1,
        type: 'project-header',
        project: 'PROJ-001',
        projectName: 'Sample Project 1',
        activity: null,
        activityName: null,
        resource: null,
        resourceName: null,
        role: null,
        roleName: null,
        entries: [],
        dailyEntries: {}
      },
      {
        id: 2,
        type: 'activity-row',
        project: 'PROJ-001',
        projectName: 'Sample Project 1',
        activity: 'ACT-001',
        activityName: 'Planning',
        resource: 'RES-001',
        resourceName: 'John Doe',
        role: 'ROLE-001',
        roleName: 'Senior Developer',
        entries: [],
        dailyEntries: {
          [format(new Date(), 'yyyy-MM-dd')]: {
            hours: 8,
            start_time: '09:00',
            end_time: '17:00',
            description: 'Sample planning work',
            status: 'planned'
          }
        }
      },
      {
        id: 3,
        type: 'activity-row',
        project: null,
        projectName: null,
        activity: null,
        activityName: null,
        resource: null,
        resourceName: null,
        role: null,
        roleName: null,
        entries: [],
        dailyEntries: {}
      }
    ]
  }

  // Process schedule entries into grouped rows
  const processScheduleEntries = (entries) => {
    const projectGroups = {}
    
    // Group entries by project and activity
    entries.forEach(entry => {
      const projectKey = entry.project
      const activityKey = `${entry.project}-${entry.activity}`
      
      if (!projectGroups[projectKey]) {
        projectGroups[projectKey] = {
          project: entry.project,
          projectName: entry.project_name || entry.project,
          activities: {}
        }
      }
      
      if (!projectGroups[projectKey].activities[activityKey]) {
        projectGroups[projectKey].activities[activityKey] = {
          project: entry.project,
          projectName: entry.project_name || entry.project,
          activity: entry.activity,
          activityName: entry.activity_name || entry.activity,
          resource: entry.resource,
          resourceName: entry.resource_name || entry.resource,
          role: entry.role,
          roleName: entry.role_name || entry.role,
          entries: []
        }
      }
      
      projectGroups[projectKey].activities[activityKey].entries.push(entry)
    })
    
    // Convert to schedule rows format
    const rows = []
    let rowId = 1
    
    Object.values(projectGroups).forEach(projectGroup => {
      // Add project header
      rows.push({
        id: rowId++,
        type: 'project-header',
        project: projectGroup.project,
        projectName: projectGroup.projectName,
        activity: null,
        activityName: null,
        resource: null,
        resourceName: null,
        role: null,
        roleName: null,
        entries: [],
        dailyEntries: {}
      })
      
      // Add activity rows
      Object.values(projectGroup.activities).forEach(activity => {
        rows.push({
          id: rowId++,
          type: 'activity-row',
          ...activity,
          dailyEntries: convertEntriesToDailyFormat(activity.entries)
        })
      })
    })
    
    // Always ensure there's an empty row at the end
    rows.push({
      id: rowId++,
      type: 'activity-row',
      project: null,
      projectName: null,
      activity: null,
      activityName: null,
      resource: null,
      resourceName: null,
      role: null,
      roleName: null,
      entries: [],
      dailyEntries: {}
    })
    
    return rows
  }

  // Convert legacy entries to daily format
  const convertEntriesToDailyFormat = (entries) => {
    const dailyEntries = {}
    
    entries.forEach(entry => {
      const date = entry.schedule_date
      if (!dailyEntries[date]) {
        dailyEntries[date] = {
          hours: 0,
          start_time: '09:00',
          end_time: '17:00',
          description: '',
          status: 'planned'
        }
      }
      
      dailyEntries[date].hours += parseFloat(entry.duration || 0)
      if (entry.description) {
        dailyEntries[date].description = entry.description
      }
    })
    
    return dailyEntries
  }

  // Add a new schedule row
  const addScheduleRow = () => {
    const newRow = {
      id: Date.now(),
      type: 'activity-row',
      project: null,
      projectName: null,
      activity: null,
      activityName: null,
      resource: null,
      resourceName: null,
      role: null,
      roleName: null,
      entries: [],
      dailyEntries: {}
    }
    
    scheduleRows.value.push(newRow)
  }

  // Add a new activity row for a specific project
  const addProjectActivityRow = (projectId) => {
    const project = projects.value.find(p => p.name === projectId)
    const newRow = {
      id: Date.now(),
      type: 'activity-row',
      project: projectId,
      projectName: project?.project_name || project?.name || projectId,
      activity: null,
      activityName: null,
      resource: null,
      resourceName: null,
      role: null,
      roleName: null,
      entries: [],
      dailyEntries: {}
    }
    
    // Find the last row for this project
    let insertIndex = scheduleRows.value.length
    for (let i = scheduleRows.value.length - 1; i >= 0; i--) {
      if (scheduleRows.value[i].project === projectId) {
        insertIndex = i + 1
        break
      }
    }
    
    // Insert the new row at the correct position
    scheduleRows.value.splice(insertIndex, 0, newRow)
  }

  // Update schedule rows from API data
  const updateScheduleRows = (entries) => {
    scheduleRows.value = processScheduleEntries(entries)
  }

  // Get activities for a project
  const getActivitiesForProject = (projectName) => {
    const project = projects.value.find(p => p.name === projectName)
    return project ? project.activities || [] : []
  }

  // Generate project colors based on loaded projects
  const generateProjectColors = () => {
    const colorPalette = [
      '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
      '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1'
    ]
    
    const colors = {}
    projects.value.forEach((project, index) => {
      if (project.division_color) {
        colors[project.name] = project.division_color
      } else {
        colors[project.name] = colorPalette[index % colorPalette.length]
      }
    })
    
    projectColors.value = colors
  }

  // Expand daily entries from optimized format (blocks + individual_days)
  const expandDailyEntries = (dailyEntriesJson) => {
    try {
      const data = typeof dailyEntriesJson === 'string' ? JSON.parse(dailyEntriesJson) : dailyEntriesJson
      const expanded = {}
      
      // Handle blocks (consecutive days with same schedule)
      if (data.blocks && Array.isArray(data.blocks)) {
        data.blocks.forEach(block => {
          const startDate = new Date(block.start_date)
          const endDate = new Date(block.end_date)
          
          // Expand each day in the block
          for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
            const dateStr = d.toISOString().split('T')[0] // YYYY-MM-DD format
            expanded[dateStr] = {
              hours: block.hours || 8,
              start_time: block.start_time || '09:00',
              end_time: block.end_time || '17:00',
              description: block.description || '',
              status: block.status || 'planned'
            }
          }
        })
      }
      
      // Handle individual days (override any block entries)
      if (data.individual_days && typeof data.individual_days === 'object') {
        Object.keys(data.individual_days).forEach(dateStr => {
          expanded[dateStr] = data.individual_days[dateStr]
        })
      }
      
      return expanded
      
    } catch (error) {
      console.error('Error expanding daily entries:', error)
      return {}
    }
  }

  // Get project color
  const getProjectColor = (projectName) => {
    return projectColors.value[projectName] || '#6b7280'
  }

  return {
    // State
    scheduleRows,
    projects,
    resources,
    roles,
    projectColors,
    currentStartDate,
    dateRange,
    
    // Methods
    loadInitialData,
    processScheduleEntries,
    addScheduleRow,
    addProjectActivityRow,
    updateScheduleRows,
    getActivitiesForProject,
    getProjectColor
  }
}
