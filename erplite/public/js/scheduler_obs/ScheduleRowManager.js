/**
 * Schedule Row Manager
 * Handles all schedule row operations and backend API calls
 */
class ScheduleRowManager {
    constructor(schedulerApp) {
        this.app = schedulerApp;
    }

    /**
     * Create a new schedule row entry
     */
    async createScheduleRow(project, activity, resource = null, role = null) {
        try {
            const response = await this.app.apiCall('erplite.scheduler.api.create_schedule_row_entry', {
                project: project,
                activity: activity,
                resource: resource,
                role: role
            });
            
            if (response && response.success) {
                console.log('Schedule Row created:', response.name);
                return {
                    success: true,
                    scheduleRowId: response.name,
                    message: 'Schedule row created successfully'
                };
            } else {
                console.warn('Failed to create schedule row:', response ? response.message : 'No response');
                return {
                    success: false,
                    message: response ? response.message : 'Failed to create schedule row'
                };
            }
        } catch (error) {
            console.error('Error creating schedule row:', error);
            return {
                success: false,
                message: error.message
            };
        }
    }

    /**
     * Update schedule row role
     */
    async updateScheduleRowRole(scheduleRowId, role) {
        try {
            const response = await this.app.apiCall('erplite.scheduler.api.update_schedule_row_role', {
                schedule_row: scheduleRowId,
                role: role
            });
            
            if (response && response.success) {
                console.log('Role updated in backend:', response);
                return {
                    success: true,
                    message: 'Role updated successfully'
                };
            } else {
                console.warn('Failed to update role in backend:', response ? response.message : 'No response');
                return {
                    success: false,
                    message: response ? response.message : 'Failed to update role'
                };
            }
        } catch (error) {
            console.error('Error updating role in backend:', error);
            return {
                success: false,
                message: error.message
            };
        }
    }

    /**
     * Update schedule row resource
     */
    async updateScheduleRowResource(scheduleRowId, resource) {
        try {
            const response = await this.app.apiCall('erplite.scheduler.api.update_schedule_row_resource', {
                schedule_row: scheduleRowId,
                resource: resource
            });
            
            if (response && response.success) {
                console.log('Resource updated in backend:', response);
                return {
                    success: true,
                    message: 'Resource updated successfully'
                };
            } else {
                console.warn('Failed to update resource in backend:', response ? response.message : 'No response');
                return {
                    success: false,
                    message: response ? response.message : 'Failed to update resource'
                };
            }
        } catch (error) {
            console.error('Error updating resource in backend:', error);
            return {
                success: false,
                message: error.message
            };
        }
    }

    /**
     * Update schedule row entries (time entries)
     */
    async updateScheduleRowEntries(scheduleRowId, entriesJson) {
        try {
            const response = await this.app.apiCall('erplite.scheduler.api.update_schedule_row_entries', {
                schedule_row: scheduleRowId,
                entries_json: entriesJson
            });
            
            if (response && response.success) {
                return {
                    success: true,
                    optimizedEntries: response.optimized_entries,
                    message: 'Entries updated successfully'
                };
            } else {
                return {
                    success: false,
                    message: response ? response.message : 'Failed to update entries'
                };
            }
        } catch (error) {
            console.error('Error updating schedule row entries:', error);
            return {
                success: false,
                message: error.message
            };
        }
    }

    /**
     * Get expanded schedule row entries
     */
    async getScheduleRowExpanded(scheduleRowId) {
        try {
            const response = await this.app.apiCall('erplite.scheduler.api.get_schedule_row_expanded', {
                schedule_row: scheduleRowId
            });
            
            if (response && response.success) {
                return {
                    success: true,
                    dailyEntries: response.daily_entries,
                    message: 'Entries retrieved successfully'
                };
            } else {
                return {
                    success: false,
                    message: response ? response.message : 'Failed to get entries'
                };
            }
        } catch (error) {
            console.error('Error getting schedule row entries:', error);
            return {
                success: false,
                message: error.message
            };
        }
    }

    /**
     * Select project for a row
     */
    selectProject(rowIndex, project) {
        const row = this.app.state.scheduleRows[rowIndex];
        row.project = project.name;
        row.projectName = project.project_name;
        row.activity = null;
        row.activityName = null;
        row.role = null;
        row.roleName = null;
        row.resource = null;
        row.resourceName = null;
        
        // Add a new blank row below when a project is selected
        this.app.addNewRow();
        this.app.renderScheduleRows();
        
        this.app.showToast(`Project set to ${project.project_name}`, 'success');
    }

    /**
     * Select activity for a row
     */
    async selectActivity(rowIndex, activity) {
        const row = this.app.state.scheduleRows[rowIndex];
        row.activity = activity.name;
        row.activityName = activity.subject;
        
        // Automatically create a Schedule Row when activity is selected
        const result = await this.createScheduleRow(
            row.project,
            activity.name,
            row.resource || null,
            row.role || null
        );
        
        if (result.success) {
            row.scheduleRowId = result.scheduleRowId;
            row.dailyEntries = {};
            this.app.showToast('Schedule row created for activity', 'success');
        } else {
            console.warn('Failed to create schedule row:', result.message);
            this.app.showToast('Activity selected (backend save failed)', 'warning');
        }
        
        // When an activity is selected, add a new row with the same project but no activity
        this.app.state.scheduleRows.splice(rowIndex + 1, 0, {
            type: 'activity-row',
            project: row.project,
            projectName: row.projectName,
            activity: null,
            activityName: null,
            role: null,
            roleName: null,
            resource: null,
            resourceName: null,
            entries: [],
            dailyEntries: {}
        });
        
        this.app.renderScheduleRows();
    }

    /**
     * Select role for a row
     */
    async selectRole(rowIndex, role) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        // Handle different possible role data structures
        const roleId = role ? (role.name || role.id) : null;
        const roleName = role ? (role.role_name || role.name || role.title || 'Unknown Role') : null;
        
        row.role = roleId;
        row.roleName = roleName;
        
        // If we have a schedule row ID, save the role to the backend
        if (row.scheduleRowId) {
            const result = await this.updateScheduleRowRole(row.scheduleRowId, roleId);
            
            if (result.success) {
                if (role) {
                    this.app.showToast(`Role set to ${roleName}`, 'success');
                } else {
                    this.app.showToast('Role set to Any', 'success');
                }
            } else {
                // Still update locally but show warning
                if (role) {
                    this.app.showToast(`Role set to ${roleName} (local only)`, 'warning');
                } else {
                    this.app.showToast('Role set to Any (local only)', 'warning');
                }
            }
        } else {
            // No schedule row yet, just update locally
            if (role) {
                this.app.showToast(`Role set to ${roleName}`, 'success');
            } else {
                this.app.showToast('Role set to Any', 'success');
            }
        }
        
        this.app.renderScheduleRows();
    }

    /**
     * Select resource for a row
     */
    async selectResource(rowIndex, resource) {
        const row = this.app.state.scheduleRows[rowIndex];
        row.resource = resource ? resource.name : null;
        row.resourceName = resource ? resource.resource_name : 'Unassigned';
        
        // If we have a project and activity, create/update Schedule Row with resource
        if (row.project && row.activity) {
            if (row.scheduleRowId) {
                // Update existing schedule row with resource
                const result = await this.updateScheduleRowResource(row.scheduleRowId, resource ? resource.name : null);
                
                if (result.success) {
                    this.app.showToast('Schedule row updated with resource', 'success');
                } else {
                    this.app.showToast('Resource updated locally only', 'warning');
                }
            } else {
                // Create new schedule row with resource
                const result = await this.createScheduleRow(
                    row.project,
                    row.activity,
                    resource ? resource.name : null,
                    row.role || null
                );
                
                if (result.success) {
                    row.scheduleRowId = result.scheduleRowId;
                    row.dailyEntries = {};
                    this.app.showToast('Schedule row created with resource', 'success');
                } else {
                    this.app.showToast('Resource selected (backend save failed)', 'warning');
                }
            }
        } else {
            // Just update locally if no project/activity yet
            if (resource) {
                this.app.showToast(`Resource set to ${resource.resource_name}`, 'success');
            } else {
                this.app.showToast('Resource set to Unassigned', 'success');
            }
        }
        
        this.app.renderScheduleRows();
    }

    /**
     * Add a single time entry (8 hours, 9-5)
     */
    async addSingleTimeEntry(rowIndex, date) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        if (!row.scheduleRowId) {
            this.app.showToast('Schedule row not created yet', 'error');
            return;
        }
        
        // Create time entry in Schedule Row
        const timeEntry = {
            hours: 8,
            start_time: "09:00",
            end_time: "17:00",
            description: "",
            status: "planned"
        };
        
        // Update the row's daily entries
        if (!row.dailyEntries) {
            row.dailyEntries = {};
        }
        row.dailyEntries[date] = timeEntry;
        
        // Update the Schedule Row in database
        const result = await this.updateScheduleRowEntries(row.scheduleRowId, JSON.stringify(row.dailyEntries));
        
        if (result.success) {
            // Update local state with optimized entries if provided
            if (result.optimizedEntries) {
                row.dailyEntries = result.optimizedEntries;
            }
            this.app.showToast('Time entry added successfully!', 'success');
            this.app.renderScheduleRows();
        } else {
            this.app.showToast('Failed to add time entry: ' + result.message, 'error');
        }
    }

    /**
     * Add time entries for multiple dates
     */
    async addMultipleTimeEntries(rowIndex, dates) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        if (!row.scheduleRowId) {
            this.app.showToast('Schedule row not created yet', 'error');
            return;
        }
        
        // Create time entries for all dates
        if (!row.dailyEntries) {
            row.dailyEntries = {};
        }
        
        dates.forEach(date => {
            row.dailyEntries[date] = {
                hours: 8,
                start_time: "09:00",
                end_time: "17:00",
                description: "",
                status: "planned"
            };
        });
        
        // Update the Schedule Row in database
        const result = await this.updateScheduleRowEntries(row.scheduleRowId, JSON.stringify(row.dailyEntries));
        
        if (result.success) {
            // Update local state with optimized entries if provided
            if (result.optimizedEntries) {
                row.dailyEntries = result.optimizedEntries;
            }
            this.app.showToast(`Time entries added for ${dates.length} days!`, 'success');
            this.app.renderScheduleRows();
        } else {
            this.app.showToast('Failed to add time entries: ' + result.message, 'error');
        }
    }

    /**
     * Update a time entry
     */
    async updateTimeEntry(scheduleRowId, date, hours) {
        // Find the row
        const row = this.app.state.scheduleRows.find(r => r.scheduleRowId === scheduleRowId);
        if (!row) {
            this.app.showToast('Schedule row not found', 'error');
            return;
        }
        
        // Update the entry
        if (!row.dailyEntries) {
            row.dailyEntries = {};
        }
        
        row.dailyEntries[date] = {
            hours: hours,
            start_time: "09:00",
            end_time: "17:00",
            description: "",
            status: "planned"
        };
        
        // Update in database
        const result = await this.updateScheduleRowEntries(scheduleRowId, JSON.stringify(row.dailyEntries));
        
        if (result.success) {
            // Update local state with optimized entries if provided
            if (result.optimizedEntries) {
                row.dailyEntries = result.optimizedEntries;
            }
            this.app.showToast('Time entry updated successfully!', 'success');
            this.app.renderScheduleRows();
        } else {
            this.app.showToast('Failed to update time entry: ' + result.message, 'error');
        }
    }

    /**
     * Update a time block
     */
    async updateTimeBlock(rowIndex, blockData, updates) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        if (!row.scheduleRowId) {
            this.app.showToast('Schedule row not found', 'error');
            return;
        }
        
        // Get current entries in daily format for editing
        const expandedResult = await this.getScheduleRowExpanded(row.scheduleRowId);
        
        if (expandedResult.success) {
            const dailyEntries = expandedResult.dailyEntries;
            
            // Update the affected dates
            const startDate = new Date(blockData.start_date);
            const endDate = new Date(blockData.end_date);
            const currentDate = new Date(startDate);
            
            while (currentDate <= endDate) {
                const dateStr = currentDate.toISOString().split('T')[0];
                if (dailyEntries[dateStr]) {
                    Object.assign(dailyEntries[dateStr], updates);
                }
                currentDate.setDate(currentDate.getDate() + 1);
            }
            
            // Save the updated entries
            const updateResult = await this.updateScheduleRowEntries(row.scheduleRowId, JSON.stringify(dailyEntries));
            
            if (updateResult.success) {
                // Update local state with optimized entries
                if (updateResult.optimizedEntries) {
                    row.dailyEntries = updateResult.optimizedEntries;
                }
                this.app.showToast('Time block updated successfully!', 'success');
                this.app.renderTimeBlockCards(); // Re-render cards
            } else {
                this.app.showToast('Failed to update time block: ' + updateResult.message, 'error');
            }
        } else {
            this.app.showToast('Failed to get current entries: ' + expandedResult.message, 'error');
        }
    }

    /**
     * Handle template drop on day cell
     */
    async handleTemplateDrop(template, rowIndex, date) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        if (!row.project || !row.activity) {
            this.app.showToast('Please select project and activity first', 'warning');
            return;
        }
        
        // Get template configuration
        const templateConfig = this.app.getTemplateConfig(template);
        
        // Initialize dailyEntries if not exists
        if (!row.dailyEntries) {
            row.dailyEntries = {};
        }
        
        // Add the new entry to frontend state
        row.dailyEntries[date] = {
            hours: templateConfig.hours,
            start_time: templateConfig.start_time,
            end_time: templateConfig.end_time,
            description: templateConfig.description,
            status: templateConfig.status,
            id: this.app.generateEntryId() // Generate unique ID for frontend tracking
        };
        
        // If we have a schedule row ID, save to backend
        if (row.scheduleRowId) {
            const result = await this.updateScheduleRowEntries(row.scheduleRowId, JSON.stringify(row.dailyEntries));
            
            if (result.success) {
                // Update local state with optimized entries if provided
                if (result.optimizedEntries) {
                    row.dailyEntries = result.optimizedEntries;
                }
                this.app.showToast(`${templateConfig.name} template added!`, 'success');
            } else {
                this.app.showToast(`${templateConfig.name} template added (local only)`, 'warning');
            }
        } else {
            this.app.showToast(`${templateConfig.name} template added (local only)`, 'warning');
        }
        
        // Re-render the schedule to show the new entry
        this.app.renderScheduleRows();
        this.app.renderTimeBlockCards();
    }

    /**
     * Delete a schedule row
     */
    deleteRow(rowIndex) {
        if (rowIndex >= 0 && rowIndex < this.app.state.scheduleRows.length) {
            this.app.state.scheduleRows.splice(rowIndex, 1);
            this.app.renderScheduleRows();
            this.app.showToast('Row deleted successfully!', 'success');
        }
    }

    /**
     * Copy activity down - creates a duplicate activity row below the current one
     */
    copyActivityDown(rowIndex) {
        if (rowIndex >= 0 && rowIndex < this.app.state.scheduleRows.length) {
            const sourceRow = this.app.state.scheduleRows[rowIndex];
            
            // Create a copy of the activity row
            const newRow = {
                type: 'activity-row',
                project: sourceRow.project,
                projectName: sourceRow.projectName,
                activity: sourceRow.activity,
                activityName: sourceRow.activityName,
                role: sourceRow.role,
                roleName: sourceRow.roleName,
                resource: sourceRow.resource,
                resourceName: sourceRow.resourceName,
                entries: [] // New row starts with no entries
            };
            
            // Insert the new row right after the current one
            this.app.state.scheduleRows.splice(rowIndex + 1, 0, newRow);
            
            // Add another blank row after the copied row
            this.app.state.scheduleRows.splice(rowIndex + 2, 0, {
                type: 'activity-row',
                project: sourceRow.project,
                projectName: sourceRow.projectName,
                activity: null,
                activityName: null,
                role: null,
                roleName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
            
            this.app.renderScheduleRows();
            this.app.showToast('Activity copied down successfully!', 'success');
        }
    }
}

// Export to global scope for HTML compatibility
window.ScheduleRowManager = ScheduleRowManager;
