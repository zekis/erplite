/**
 * Manages data persistence and API communication
 */
class StorageManager {
    constructor(app) {
        this.app = app;
        this.saveTimeout = null;
        this.isSaving = false;
    }
    
    /**
     * Save timesheet entries to the server
     */
    saveTimesheet() {
        // Prevent multiple simultaneous saves
        if (this.isSaving) {
            return;
        }
        
        // Clear any pending save timeout
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
        }
        
        this.isSaving = true;
        
        const entries = this.prepareEntriesForSave();
        
        // Prepare arguments for API call
        const args = { entries: entries };
        
        // If admin is viewing another user's timesheet, pass target user
        if (this.app.state.isTimesheetAdmin && this.app.state.currentTargetUser) {
            args.target_user = this.app.state.currentTargetUser;
            console.log('Saving timesheet entries for target user:', this.app.state.currentTargetUser);
        } else {
            console.log('Saving timesheet entries for current user (no target user)');
        }
        
        console.log('Save args:', args);
        
        frappe.call({
            method: 'erplite.projects.api.save_timesheet_entries',
            args: args,
            callback: (r) => {
                this.handleSaveResponse(r);
            },
            error: (err) => {
                this.handleSaveError(err);
            },
            always: () => {
                this.isSaving = false;
            }
        });
    }
    
    /**
     * Prepare time block entries for saving
     */
    prepareEntriesForSave() {
        const entries = [];
        
        // Clean up timeBlocks array - remove any null or detached elements
        this.app.state.timeBlocks = this.app.state.timeBlocks.filter(block => {
            return block && block.parentNode && block.dataset;
        });
        
        this.app.state.timeBlocks.forEach(block => {
            // Double check the block is still valid
            if (!block || !block.parentNode || !block.dataset) {
                return; // Skip invalid blocks
            }
            
            const dayColumn = block.closest('.day-column');
            if (!dayColumn) {
                return; // Skip blocks not in a day column
            }
            
            const date = dayColumn.dataset.date;
            const startHour = parseInt(block.dataset.startHour);
            const startMinute = parseInt(block.dataset.startMinute || 0);
            const duration = parseFloat(block.dataset.duration);
            
            // Generate a temporary ID for new entries if they don't have one
            let tempId = block.dataset.tempId;
            if (!tempId && (!block.dataset.id || block.dataset.id === 'null')) {
                tempId = 'temp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                block.dataset.tempId = tempId;
            }
            
            entries.push({
                id: block.dataset.id || null,
                temp_id: tempId,
                project: block.dataset.project,
                activity: block.dataset.activity,
                date: date,
                start_time: TimeUtils.formatTime(startHour, startMinute),
                duration: duration,
                description: block.dataset.description || ''
            });
        });
        
        return entries;
    }
    
    /**
     * Handle successful save response
     */
    handleSaveResponse(response) {
        if (response.message && response.message.success) {
            // Update time blocks with new IDs from the server
            if (response.message.entries) {
                response.message.entries.forEach(savedEntry => {
                    if (savedEntry.temp_id) {
                        // Find the time block with this temp_id and update it with the real ID
                        const timeBlock = this.app.state.timeBlocks.find(block => 
                            block.dataset.tempId === savedEntry.temp_id
                        );
                        if (timeBlock) {
                            timeBlock.dataset.id = savedEntry.id;
                            // Remove temp_id since we now have a real ID
                            delete timeBlock.dataset.tempId;
                        }
                    }
                });
            }
            this.app.components.toast.show('Timesheet saved successfully!', 'success');
        } else {
            this.app.components.toast.show('Error saving timesheet: ' + (response.message.message || 'Unknown error'), 'error');
        }
    }
    
    /**
     * Handle save error
     */
    handleSaveError(error) {
        console.error('Error saving timesheet:', error);
        this.app.components.toast.show('Error: Failed to save timesheet', 'error');
    }
    
    /**
     * Auto-save with debouncing
     */
    autoSave(delay = 500) {
        // Clear any existing timeout
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
        }
        
        // Set new timeout
        this.saveTimeout = setTimeout(() => {
            this.saveTimesheet();
        }, delay);
    }
    
    /**
     * Delete a timesheet entry
     */
    deleteEntry(entryId) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: 'erplite.projects.api.delete_timesheet_entry',
                args: { entry_id: entryId },
                callback: (r) => {
                    if (r.message && r.message.success) {
                        resolve(r.message);
                    } else {
                        reject(new Error(r.message.message || 'Failed to delete entry'));
                    }
                },
                error: (err) => {
                    reject(err);
                }
            });
        });
    }
    
    /**
     * Load timesheet data for a specific week
     */
    loadWeekData(weekStart) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: 'erplite.projects.api.get_week_timesheets',
                args: { week_start: weekStart },
                callback: (r) => {
                    if (r.message) {
                        resolve(r.message);
                    } else {
                        reject(new Error('Failed to load week data'));
                    }
                },
                error: (err) => {
                    reject(err);
                }
            });
        });
    }
    
    /**
     * Export timesheet data
     */
    exportData(format = 'csv', weekStart = null) {
        const args = { format: format };
        if (weekStart) {
            args.week_start = weekStart;
        }
        
        frappe.call({
            method: 'erplite.projects.api.export_timesheet_data',
            args: args,
            callback: (r) => {
                if (r.message && r.message.success) {
                    // Create download link
                    const blob = new Blob([r.message.data], { 
                        type: format === 'csv' ? 'text/csv' : 'application/json' 
                    });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `timesheet_${weekStart || 'all'}.${format}`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    
                    this.app.components.toast.show('Timesheet exported successfully!', 'success');
                } else {
                    this.app.components.toast.show('Error exporting timesheet: ' + (r.message.message || 'Unknown error'), 'error');
                }
            },
            error: (err) => {
                console.error('Error exporting timesheet:', err);
                this.app.components.toast.show('Error: Failed to export timesheet', 'error');
            }
        });
    }
    
    /**
     * Get project and activity data
     */
    loadProjectData() {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: 'erplite.projects.api.get_projects_and_activities',
                callback: (r) => {
                    if (r.message) {
                        resolve(r.message);
                    } else {
                        reject(new Error('Failed to load project data'));
                    }
                },
                error: (err) => {
                    reject(err);
                }
            });
        });
    }
    
    /**
     * Save user preferences
     */
    savePreferences(preferences) {
        frappe.call({
            method: 'erplite.projects.api.save_user_preferences',
            args: { preferences: preferences },
            callback: (r) => {
                if (r.message && r.message.success) {
                    this.app.components.toast.show('Preferences saved!', 'success');
                } else {
                    this.app.components.toast.show('Error saving preferences', 'error');
                }
            },
            error: (err) => {
                console.error('Error saving preferences:', err);
                this.app.components.toast.show('Error: Failed to save preferences', 'error');
            }
        });
    }
    
    /**
     * Load user preferences
     */
    loadPreferences() {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: 'erplite.projects.api.get_user_preferences',
                callback: (r) => {
                    if (r.message) {
                        resolve(r.message);
                    } else {
                        reject(new Error('Failed to load preferences'));
                    }
                },
                error: (err) => {
                    reject(err);
                }
            });
        });
    }
    
    /**
     * Check if there are unsaved changes
     */
    hasUnsavedChanges() {
        // Check if any time blocks have temp IDs (indicating unsaved changes)
        return this.app.state.timeBlocks.some(block => 
            block.dataset.tempId && !block.dataset.id
        );
    }
    
    /**
     * Warn user about unsaved changes before leaving
     */
    setupUnloadWarning() {
        // Only setup unload warning if we're actually on the timesheet calendar page
        if (!window.location.pathname.includes('timesheet-calendar')) {
            return;
        }
        
        // Store reference to the handler so we can remove it later
        this.unloadHandler = (e) => {
            if (this.hasUnsavedChanges()) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
                return e.returnValue;
            }
        };
        
        window.addEventListener('beforeunload', this.unloadHandler);
    }
    
    /**
     * Clean up event listeners when leaving the page
     */
    cleanup() {
        if (this.unloadHandler) {
            window.removeEventListener('beforeunload', this.unloadHandler);
            this.unloadHandler = null;
        }
    }
}

// Export to global scope
window.StorageManager = StorageManager;
