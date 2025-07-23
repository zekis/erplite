/**
 * Data Manager
 * Handles all API calls, data loading, and data processing for the scheduler
 */
class DataManager {
    constructor(app) {
        this.app = app;
    }

    /**
     * Load initial data from window object (set by template)
     */
    loadInitialData() {
        if (window.schedulerData) {
            this.app.state.currentStartDate = window.schedulerData.currentStartDate || this.getTodayString();
            this.app.state.projects = window.schedulerData.projects || [];
            this.app.state.resources = window.schedulerData.resources || [];
            this.app.state.roles = window.schedulerData.roles || [];
            this.app.state.scheduleEntries = window.schedulerData.scheduleEntries || [];
            this.app.state.projectColors = window.schedulerData.projectColors || {};
        } else {
            this.app.state.currentStartDate = this.getTodayString();
        }
    }

    /**
     * Load scheduler data from API
     */
    async loadSchedulerData() {
        try {
            this.app.setLoading(true);
            
            // Calculate end date
            const endDate = this.addDays(this.app.state.currentStartDate, this.app.state.dateRange);
            
            // Make API calls for both old and new data
            const [projectsResponse, scheduleRowsResponse] = await Promise.all([
                this.apiCall('erplite.scheduler.api.get_scheduler_data', {
                    start_date: this.app.state.currentStartDate,
                    end_date: endDate
                }),
                this.apiCall('erplite.scheduler.api.get_schedule_rows', {
                    start_date: this.app.state.currentStartDate,
                    end_date: endDate
                })
            ]);
            
            if (projectsResponse) {
                this.app.state.projects = projectsResponse.projects || [];
                this.app.state.resources = projectsResponse.resources || [];
                this.app.state.roles = projectsResponse.roles || [];
                this.app.state.projectColors = projectsResponse.project_colors || {};
            }
            
            if (scheduleRowsResponse) {
                this.app.state.scheduleRows = this.processScheduleRowsFromAPI(scheduleRowsResponse);
            } else {
                this.processScheduleRows();
            }
            
            return {
                success: true,
                message: 'Data loaded successfully'
            };
        } catch (error) {
            console.error('Failed to load scheduler data:', error);
            this.app.showToast('Failed to load scheduler data: ' + error.message, 'error');
            return {
                success: false,
                message: error.message
            };
        } finally {
            this.app.setLoading(false);
        }
    }

    /**
     * Process schedule rows from API response (Structure only - no time entries)
     */
    processScheduleRowsFromAPI(scheduleRowsData) {
        const processedRows = [];
        
        // Group schedule rows by project
        const projectGroups = {};
        
        scheduleRowsData.forEach(row => {
            const projectKey = row.project || 'unassigned';
            
            if (!projectGroups[projectKey]) {
                projectGroups[projectKey] = {
                    project: row.project,
                    projectName: row.project_name,
                    rows: []
                };
            }
            
            // Only load the structure - no time entries for frontend development
            const processedRow = {
                type: 'activity-row',
                scheduleRowId: row.name,
                project: row.project,
                projectName: row.project_name,
                activity: row.activity,
                activityName: row.activity_name,
                role: row.role,
                roleName: row.role_name,
                resource: row.resource,
                resourceName: row.resource_name,
                entries: [], // Empty entries for frontend development
                dailyEntries: {} // Empty daily entries for frontend development
            };
            
            projectGroups[projectKey].rows.push(processedRow);
        });
        
        // Add default projects that don't have schedule rows yet
        this.addDefaultProjectsToGroups(projectGroups);
        
        // Convert to flat array with project headers and activity rows
        Object.keys(projectGroups).sort().forEach(projectKey => {
            const projectGroup = projectGroups[projectKey];
            
            // Add project header row
            const project = this.app.state.projects.find(p => p.name === projectGroup.project);
            processedRows.push({
                type: 'project-header',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                workType: project ? project.work_type : null,
                activity: null,
                activityName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
            
            // Add existing schedule rows (structure only)
            projectGroup.rows.forEach(row => {
                processedRows.push(row);
            });
            
            // Add blank activity row for this project
            processedRows.push({
                type: 'activity-row',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                activity: null,
                activityName: null,
                role: null,
                roleName: null,
                resource: null,
                resourceName: null,
                entries: [],
                dailyEntries: {}
            });
        });
        
        return processedRows;
    }

    /**
     * Add default projects to project groups
     */
    addDefaultProjectsToGroups(projectGroups) {
        // Get all projects that have status "Active" or "Open"
        const openProjects = this.app.state.projects.filter(project => 
            project.status === 'Active' || project.status === 'Open'
        );
        
        // For each open project, ensure it exists in project groups
        openProjects.forEach(project => {
            const projectKey = project.name;
            if (!projectGroups[projectKey]) {
                projectGroups[projectKey] = {
                    project: project.name,
                    projectName: project.project_name,
                    rows: []
                };
            }
        });
    }

    /**
     * Process schedule entries into rows with project headers and activity rows (legacy fallback)
     */
    processScheduleRows() {
        this.app.state.scheduleRows = [];
        
        // Group entries by project and activity
        const projectGroups = {};
        
        this.app.state.scheduleEntries.forEach(entry => {
            const projectKey = entry.project || 'unassigned';
            const activityKey = entry.activity || 'unassigned';
            const resourceKey = entry.resource || 'unassigned';
            
            if (!projectGroups[projectKey]) {
                projectGroups[projectKey] = {
                    project: entry.project,
                    projectName: entry.project_name || entry.project,
                    activities: {}
                };
            }
            
            if (!projectGroups[projectKey].activities[activityKey]) {
                projectGroups[projectKey].activities[activityKey] = {
                    activity: entry.activity,
                    activityName: entry.activity_name || entry.activity,
                    resources: {}
                };
            }
            
            if (!projectGroups[projectKey].activities[activityKey].resources[resourceKey]) {
                projectGroups[projectKey].activities[activityKey].resources[resourceKey] = {
                    resource: entry.resource,
                    resourceName: entry.resource_name || this.getResourceName(entry.resource),
                    entries: []
                };
            }
            
            projectGroups[projectKey].activities[activityKey].resources[resourceKey].entries.push(entry);
        });
        
        // Add default projects
        this.addDefaultProjects(projectGroups);
        
        // Convert to flat array with project headers and activity rows
        Object.keys(projectGroups).sort().forEach(projectKey => {
            const projectGroup = projectGroups[projectKey];
            
            // Add project header row
            this.app.state.scheduleRows.push({
                type: 'project-header',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                activity: null,
                activityName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
            
            // Add activity rows
            Object.keys(projectGroup.activities).forEach(activityKey => {
                const activityGroup = projectGroup.activities[activityKey];
                
                Object.keys(activityGroup.resources).forEach(resourceKey => {
                    const resourceGroup = activityGroup.resources[resourceKey];
                    
                    this.app.state.scheduleRows.push({
                        type: 'activity-row',
                        project: projectGroup.project,
                        projectName: projectGroup.projectName,
                        activity: activityGroup.activity,
                        activityName: activityGroup.activityName,
                        resource: resourceGroup.resource,
                        resourceName: resourceGroup.resourceName,
                        entries: resourceGroup.entries
                    });
                });
                
                // Add blank row for adding more resources to this activity
                if (activityGroup.activity) {
                    this.app.state.scheduleRows.push({
                        type: 'activity-row',
                        project: projectGroup.project,
                        projectName: projectGroup.projectName,
                        activity: activityGroup.activity,
                        activityName: activityGroup.activityName,
                        resource: null,
                        resourceName: null,
                        entries: []
                    });
                }
            });
            
            // Add blank activity row for this project
            this.app.state.scheduleRows.push({
                type: 'activity-row',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                activity: null,
                activityName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
        });
        
        // No need for empty project rows since we show all active projects
    }

    /**
     * Add default projects to project groups (legacy)
     */
    addDefaultProjects(projectGroups) {
        // Get all projects that have status "Active" or "Open"
        const openProjects = this.app.state.projects.filter(project => 
            project.status === 'Active' || project.status === 'Open'
        );
        
        // For each open project, ensure it exists in project groups
        openProjects.forEach(project => {
            const projectKey = project.name;
            if (!projectGroups[projectKey]) {
                projectGroups[projectKey] = {
                    project: project.name,
                    projectName: project.project_name,
                    activities: {}
                };
            }
        });
    }

    /**
     * Get resource name by ID
     */
    getResourceName(resourceId) {
        if (!resourceId) return 'Unassigned';
        const resource = this.app.state.resources.find(r => r.name === resourceId);
        return resource ? resource.resource_name : resourceId;
    }

    /**
     * Create a schedule entry
     */
    async createScheduleEntry(formData) {
        try {
            this.app.setLoading(true);
            
            const response = await this.apiCall('erplite.scheduler.api.create_schedule_entry', {
                data: JSON.stringify(formData)
            });
            
            if (response && response.success) {
                return {
                    success: true,
                    message: 'Schedule entry created successfully!'
                };
            } else {
                return {
                    success: false,
                    message: response.message || 'Failed to create entry'
                };
            }
        } catch (error) {
            console.error('Error saving entry:', error);
            return {
                success: false,
                message: 'Error saving entry: ' + error.message
            };
        } finally {
            this.app.setLoading(false);
        }
    }

    /**
     * Update a schedule entry
     */
    async updateScheduleEntry(entryId, formData) {
        try {
            this.app.setLoading(true);
            
            const response = await this.apiCall('erplite.scheduler.api.update_schedule_entry', {
                name: entryId,
                data: JSON.stringify(formData)
            });
            
            if (response && response.success) {
                return {
                    success: true,
                    message: 'Entry updated successfully!'
                };
            } else {
                return {
                    success: false,
                    message: response.message || 'Failed to update entry'
                };
            }
        } catch (error) {
            console.error('Error updating entry:', error);
            return {
                success: false,
                message: 'Error updating entry: ' + error.message
            };
        } finally {
            this.app.setLoading(false);
        }
    }

    /**
     * Delete a schedule entry
     */
    async deleteScheduleEntry(entryId) {
        try {
            this.app.setLoading(true);
            
            const response = await this.apiCall('erplite.scheduler.api.delete_schedule_entry', {
                name: entryId
            });
            
            if (response && response.success) {
                return {
                    success: true,
                    message: 'Schedule entry deleted successfully!'
                };
            } else {
                return {
                    success: false,
                    message: response.message || 'Failed to delete entry'
                };
            }
        } catch (error) {
            console.error('Error deleting entry:', error);
            return {
                success: false,
                message: 'Error deleting entry: ' + error.message
            };
        } finally {
            this.app.setLoading(false);
        }
    }

    /**
     * Refresh scheduler data
     */
    async refreshData() {
        const result = await this.loadSchedulerData();
        if (result.success) {
            this.app.renderAll();
        }
        return result;
    }

    /**
     * Navigate to a different date range
     */
    async navigateDate(days) {
        const newDate = this.addDays(this.app.state.currentStartDate, days);
        this.app.state.currentStartDate = newDate;
        
        const result = await this.loadSchedulerData();
        if (result.success) {
            this.app.renderAll();
        }
        return result;
    }

    /**
     * Make API call to Frappe backend
     */
    async apiCall(method, args = {}) {
        if (typeof frappe !== 'undefined' && frappe.call) {
            return new Promise((resolve, reject) => {
                frappe.call({
                    method: method,
                    args: args,
                    callback: (response) => {
                        resolve(response.message);
                    },
                    error: (error) => {
                        reject(error);
                    }
                });
            });
        } else {
            throw new Error('Frappe framework not available');
        }
    }

    /**
     * Get today's date as string (delegated to SchedulerUtils)
     */
    getTodayString() {
        return SchedulerUtils.getTodayString();
    }

    /**
     * Add days to a date string (delegated to SchedulerUtils)
     */
    addDays(dateString, days) {
        return SchedulerUtils.addDays(dateString, days);
    }

    /**
     * Validate schedule entry data
     */
    validateScheduleEntry(formData) {
        const errors = [];

        if (!formData.project) {
            errors.push('Project is required');
        }

        if (!formData.activity) {
            errors.push('Activity is required');
        }

        if (!formData.schedule_date) {
            errors.push('Schedule date is required');
        }

        if (!formData.duration || formData.duration <= 0) {
            errors.push('Duration must be greater than 0');
        }

        return {
            isValid: errors.length === 0,
            errors: errors
        };
    }

    /**
     * Get project by ID
     */
    getProject(projectId) {
        return this.app.state.projects.find(p => p.name === projectId);
    }

    /**
     * Get activity by project and activity ID
     */
    getActivity(projectId, activityId) {
        const project = this.getProject(projectId);
        if (project && project.activities) {
            return project.activities.find(a => a.name === activityId);
        }
        return null;
    }

    /**
     * Get resource by ID
     */
    getResource(resourceId) {
        return this.app.state.resources.find(r => r.name === resourceId);
    }

    /**
     * Get role by ID
     */
    getRole(roleId) {
        return this.app.state.roles.find(r => r.name === roleId);
    }

    /**
     * Get all active projects
     */
    getActiveProjects() {
        return this.app.state.projects.filter(project => 
            project.status === 'Active' || project.status === 'Open'
        );
    }

    /**
     * Get project color
     */
    getProjectColor(projectId) {
        return this.app.state.projectColors[projectId] || '#6b7280';
    }

    /**
     * Check if data is loaded
     */
    isDataLoaded() {
        return this.app.state.projects.length > 0 || 
               this.app.state.scheduleRows.length > 0;
    }

    /**
     * Get data summary for debugging
     */
    getDataSummary() {
        return {
            projects: this.app.state.projects.length,
            resources: this.app.state.resources.length,
            roles: this.app.state.roles.length,
            scheduleRows: this.app.state.scheduleRows.length,
            scheduleEntries: this.app.state.scheduleEntries.length,
            dateRange: this.app.state.dateRange,
            currentStartDate: this.app.state.currentStartDate,
            isLoading: this.app.state.isLoading
        };
    }
}

// Export to global scope for HTML compatibility
window.DataManager = DataManager;
