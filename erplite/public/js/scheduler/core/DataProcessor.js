/**
 * DataProcessor - Data transformation and processing for the scheduler
 * Handles all data manipulation, grouping, and transformation logic
 */
class DataProcessor {
    constructor(eventBus, stateManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.dateUtils = window.SchedulerDateUtils;
    }

    /**
     * Process schedule rows from API response (Structure only - no time entries)
     * @param {Array} scheduleRowsData - Raw schedule rows data from API
     * @returns {Array} Processed schedule rows
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
            projectGroups[projectKey].rows.push({
                type: 'task-row',
                scheduleRowId: row.name,
                project: row.project,
                projectName: row.project_name,
                task: row.task,
                taskName: row.task_name,
                resource: row.resource,
                resourceName: row.resource_name,
                entries: [], // Empty entries for frontend development
                dailyEntries: {} // Empty daily entries for frontend development
            });
        });
        
        // Add default projects that don't have schedule rows yet
        this.addDefaultProjectsToGroups(projectGroups);
        
        // Convert to flat array with project headers and task rows
        Object.keys(projectGroups).sort().forEach(projectKey => {
            const projectGroup = projectGroups[projectKey];
            
            // Add project header row
            processedRows.push({
                type: 'project-header',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                task: null,
                taskName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
            
            // Add existing schedule rows (structure only)
            projectGroup.rows.forEach(row => {
                processedRows.push(row);
            });
            
            // Add blank task row for this project
            processedRows.push({
                type: 'task-row',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                task: null,
                taskName: null,
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
     * @param {Object} projectGroups - Project groups object to modify
     */
    addDefaultProjectsToGroups(projectGroups) {
        const projects = this.stateManager.get('projects');
        
        // Get all projects that have status "Active" or "Open"
        const openProjects = projects.filter(project => 
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
     * Process schedule entries into rows with project headers and task rows (legacy fallback)
     * @param {Array} scheduleEntries - Legacy schedule entries
     * @returns {Array} Processed schedule rows
     */
    processLegacyScheduleEntries(scheduleEntries) {
        const scheduleRows = [];
        
        // Group entries by project and task
        const projectGroups = {};
        
        scheduleEntries.forEach(entry => {
            const projectKey = entry.project || 'unassigned';
            const taskKey = entry.task || 'unassigned';
            const resourceKey = entry.resource || 'unassigned';
            
            if (!projectGroups[projectKey]) {
                projectGroups[projectKey] = {
                    project: entry.project,
                    projectName: entry.project_name || entry.project,
                    tasks: {}
                };
            }
            
            if (!projectGroups[projectKey].tasks[taskKey]) {
                projectGroups[projectKey].tasks[taskKey] = {
                    task: entry.task,
                    taskName: entry.task_name || entry.task,
                    resources: {}
                };
            }
            
            if (!projectGroups[projectKey].tasks[taskKey].resources[resourceKey]) {
                projectGroups[projectKey].tasks[taskKey].resources[resourceKey] = {
                    resource: entry.resource,
                    resourceName: entry.resource_name || this.getResourceName(entry.resource),
                    entries: []
                };
            }
            
            projectGroups[projectKey].tasks[taskKey].resources[resourceKey].entries.push(entry);
        });
        
        // Add default projects
        this.addDefaultProjectsToGroups(projectGroups);
        
        // Convert to flat array with project headers and task rows
        Object.keys(projectGroups).sort().forEach(projectKey => {
            const projectGroup = projectGroups[projectKey];
            
            // Add project header row
            scheduleRows.push({
                type: 'project-header',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                task: null,
                taskName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
            
            // Add task rows
            Object.keys(projectGroup.tasks).forEach(taskKey => {
                const taskGroup = projectGroup.tasks[taskKey];
                
                Object.keys(taskGroup.resources).forEach(resourceKey => {
                    const resourceGroup = taskGroup.resources[resourceKey];
                    
                    scheduleRows.push({
                        type: 'task-row',
                        project: projectGroup.project,
                        projectName: projectGroup.projectName,
                        task: taskGroup.task,
                        taskName: taskGroup.taskName,
                        resource: resourceGroup.resource,
                        resourceName: resourceGroup.resourceName,
                        entries: resourceGroup.entries
                    });
                });
                
                // Add blank row for adding more resources to this task
                if (taskGroup.task) {
                    scheduleRows.push({
                        type: 'task-row',
                        project: projectGroup.project,
                        projectName: projectGroup.projectName,
                        task: taskGroup.task,
                        taskName: taskGroup.taskName,
                        resource: null,
                        resourceName: null,
                        entries: []
                    });
                }
            });
            
            // Add blank task row for this project
            scheduleRows.push({
                type: 'task-row',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                task: null,
                taskName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
        });
        
        return scheduleRows;
    }

    /**
     * Get resource name by ID
     * @param {string} resourceId - Resource ID
     * @returns {string} Resource name
     */
    getResourceName(resourceId) {
        if (!resourceId) return 'Unassigned';
        
        const resources = this.stateManager.get('resources');
        const resource = resources.find(r => r.name === resourceId);
        return resource ? resource.resource_name : resourceId;
    }

    /**
     * Group consecutive entries with identical properties into blocks
     * @param {Object} entries - Daily entries object
     * @returns {Array} Array of blocks
     */
    groupConsecutiveEntries(entries) {
        const sortedDates = Object.keys(entries).sort();
        const blocks = [];
        
        if (sortedDates.length === 0) return blocks;
        
        let currentBlock = null;
        
        for (const date of sortedDates) {
            const entry = entries[date];
            
            if (!currentBlock) {
                // Start new block
                currentBlock = {
                    start_date: date,
                    end_date: date,
                    hours: entry.hours || 8,
                    start_time: entry.start_time || '09:00',
                    end_time: entry.end_time || '17:00',
                    description: entry.description || '',
                    status: entry.status || 'planned'
                };
            } else {
                // Check if this entry can extend the current block
                const canExtend = this.canEntriesBeGrouped(currentBlock, entry) &&
                                this.dateUtils.isConsecutiveDate(currentBlock.end_date, date);
                
                if (canExtend) {
                    // Extend current block
                    currentBlock.end_date = date;
                } else {
                    // Finalize current block and start new one
                    blocks.push(currentBlock);
                    currentBlock = {
                        start_date: date,
                        end_date: date,
                        hours: entry.hours || 8,
                        start_time: entry.start_time || '09:00',
                        end_time: entry.end_time || '17:00',
                        description: entry.description || '',
                        status: entry.status || 'planned'
                    };
                }
            }
        }
        
        // Add the last block
        if (currentBlock) {
            blocks.push(currentBlock);
        }
        
        return blocks;
    }

    /**
     * Check if two entries can be grouped together
     * @param {Object} block - Current block
     * @param {Object} entry - Entry to check
     * @returns {boolean} True if entries can be grouped
     */
    canEntriesBeGrouped(block, entry) {
        return (
            (entry.hours || 8) === block.hours &&
            (entry.start_time || '09:00') === block.start_time &&
            (entry.end_time || '17:00') === block.end_time &&
            (entry.status || 'planned') === block.status
        );
    }

    /**
     * Transform daily entries to optimized format
     * @param {Object} dailyEntries - Daily entries object
     * @returns {Object} Optimized entries format
     */
    optimizeDailyEntries(dailyEntries) {
        if (!dailyEntries || Object.keys(dailyEntries).length === 0) {
            return { blocks: [], individual_days: {} };
        }

        const blocks = this.groupConsecutiveEntries(dailyEntries);
        const optimized = {
            blocks: [],
            individual_days: {}
        };

        blocks.forEach(block => {
            if (block.start_date === block.end_date) {
                // Single day entry
                optimized.individual_days[block.start_date] = {
                    hours: block.hours,
                    start_time: block.start_time,
                    end_time: block.end_time,
                    description: block.description,
                    status: block.status
                };
            } else {
                // Multi-day block
                optimized.blocks.push(block);
            }
        });

        return optimized;
    }

    /**
     * Expand optimized entries back to daily format
     * @param {Object} optimizedEntries - Optimized entries format
     * @returns {Object} Daily entries object
     */
    expandOptimizedEntries(optimizedEntries) {
        const dailyEntries = {};

        // Process blocks
        if (optimizedEntries.blocks) {
            optimizedEntries.blocks.forEach(block => {
                const dates = this.dateUtils.getDateRangeBetween(block.start_date, block.end_date);
                dates.forEach(date => {
                    dailyEntries[date] = {
                        hours: block.hours,
                        start_time: block.start_time,
                        end_time: block.end_time,
                        description: block.description,
                        status: block.status
                    };
                });
            });
        }

        // Process individual days
        if (optimizedEntries.individual_days) {
            Object.assign(dailyEntries, optimizedEntries.individual_days);
        }

        return dailyEntries;
    }

    /**
     * Calculate total hours for a project on a specific date
     * @param {string} projectName - Project name
     * @param {string} date - Date in YYYY-MM-DD format
     * @returns {number} Total hours
     */
    calculateProjectHoursForDate(projectName, date) {
        const scheduleRows = this.stateManager.get('scheduleRows');
        let totalHours = 0;
        
        const projectRows = scheduleRows.filter(row => 
            row.project === projectName && row.type === 'task-row' && row.dailyEntries
        );
        
        projectRows.forEach(row => {
            if (row.dailyEntries && row.dailyEntries[date]) {
                const entry = row.dailyEntries[date];
                const hours = typeof entry === 'object' ? entry.hours : entry;
                totalHours += parseFloat(hours) || 0;
            }
        });
        
        return totalHours;
    }

    /**
     * Get all unique resources for a project
     * @param {string} projectName - Project name
     * @returns {Array} Array of unique resource names
     */
    getProjectResources(projectName) {
        const scheduleRows = this.stateManager.get('scheduleRows');
        const projectRows = scheduleRows.filter(row => 
            row.project === projectName && row.type === 'task-row' && row.resource
        );
        
        const uniqueResources = new Set(projectRows.map(row => row.resource));
        return Array.from(uniqueResources);
    }

    /**
     * Validate schedule row data
     * @param {Object} rowData - Row data to validate
     * @returns {Object} Validation result
     */
    validateScheduleRow(rowData) {
        const errors = [];
        const warnings = [];

        // Check required fields
        if (!rowData.project) {
            errors.push('Project is required');
        }

        if (!rowData.task) {
            warnings.push('Task is recommended');
        }

        // Validate daily entries
        if (rowData.dailyEntries) {
            Object.keys(rowData.dailyEntries).forEach(date => {
                if (!this.dateUtils.isValidDateString(date)) {
                    errors.push(`Invalid date format: ${date}`);
                }

                const entry = rowData.dailyEntries[date];
                if (typeof entry === 'object') {
                    if (entry.hours && (isNaN(entry.hours) || entry.hours <= 0)) {
                        errors.push(`Invalid hours for ${date}: ${entry.hours}`);
                    }
                }
            });
        }

        return {
            isValid: errors.length === 0,
            errors,
            warnings
        };
    }

    /**
     * Generate unique entry ID
     * @returns {string} Unique entry ID
     */
    generateEntryId() {
        return 'entry_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Clean up empty rows and optimize data structure
     * @param {Array} scheduleRows - Schedule rows to clean
     * @returns {Array} Cleaned schedule rows
     */
    cleanupScheduleRows(scheduleRows) {
        return scheduleRows.filter(row => {
            // Keep project headers
            if (row.type === 'project-header') {
                return true;
            }

            // Keep rows with data or at least project/task selection
            if (row.type === 'task-row') {
                const hasData = row.entries && row.entries.length > 0;
                const hasDailyEntries = row.dailyEntries && Object.keys(row.dailyEntries).length > 0;
                const hasStructure = row.project && row.task;
                
                return hasData || hasDailyEntries || hasStructure;
            }

            return true;
        });
    }
}

// Export for use in other modules
window.SchedulerDataProcessor = DataProcessor;
