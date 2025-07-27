/**
 * Main Timesheet Calendar Application Controller
 * Coordinates all components and manages application state
 */
class TimesheetCalendar {
    constructor() {
        this.state = {
            currentWeekStart: null,
            existingTimesheets: [],
            projectColors: {},
            isFullDay: false,
            currentMobileDayIndex: 0,
            weekDates: [],
            timeBlocks: [],
            selectedTimeBlock: null,
            currentTargetUser: null // Track which user admin is viewing/impersonating
        };
        
        this.components = {};
        this.managers = {};
        
        this.init();
    }
    
    /**
     * Initialize the application
     */
    async init() {
        // Load data from window object (set by template)
        this.loadInitialData();
        
        // Check if user is timesheet admin
        await this.checkTimesheetAdmin();
        
        // Load projects and activities data from API
        await this.loadProjectsData();
        
        // Initialize managers
        this.initializeManagers();
        
        // Initialize components
        this.initializeComponents();
        
        // Setup global event listeners
        this.setupGlobalEvents();
        
        // Initialize existing time blocks
        this.initializeExistingTimeBlocks();
        
        console.log('Timesheet Calendar initialized successfully');
    }
    
    /**
     * Load initial data from window object
     */
    loadInitialData() {
        if (window.timesheetData) {
            this.state.currentWeekStart = window.timesheetData.currentWeekStart;
            this.state.existingTimesheets = window.timesheetData.existingTimesheets;
            this.state.projectColors = window.timesheetData.projectColors;
        }
    }
    
    /**
     * Load projects and activities data from API
     */
    async loadProjectsData(targetUser = null) {
        try {
            const response = await new Promise((resolve, reject) => {
                frappe.call({
                    method: 'erplite.projects.api.get_projects_and_activities',
                    args: { target_user: targetUser },
                    callback: (r) => {
                        if (r.message) {
                            resolve(r.message);
                        } else {
                            reject(new Error('No data received'));
                        }
                    },
                    error: (err) => {
                        reject(err);
                    }
                });
            });
            
            this.state.projectsData = response;
            console.log('Projects data loaded:', response);
            
        } catch (error) {
            console.error('Failed to load projects data:', error);
            this.state.projectsData = {};
            
            // Show error toast if components are available
            if (this.components && this.components.toast) {
                this.components.toast.error('Failed to load projects data');
            }
        }
    }
    
    /**
     * Load timesheet data for a specific user
     */
    async loadTimesheetData(targetUser = null) {
        try {
            const response = await new Promise((resolve, reject) => {
                frappe.call({
                    method: 'erplite.projects.api.get_week_timesheets',
                    args: { 
                        week_start: this.state.currentWeekStart,
                        target_user: targetUser 
                    },
                    callback: (r) => {
                        if (r.message) {
                            resolve(r.message);
                        } else {
                            resolve([]);
                        }
                    },
                    error: (err) => {
                        reject(err);
                    }
                });
            });
            
            this.state.existingTimesheets = response;
            console.log('Timesheet data loaded:', response);
            
        } catch (error) {
            console.error('Failed to load timesheet data:', error);
            this.state.existingTimesheets = [];
            
            // Show error toast if components are available
            if (this.components && this.components.toast) {
                this.components.toast.error('Failed to load timesheet data');
            }
        }
    }
    
    /**
     * Clear all time blocks from calendar
     */
    clearCalendar() {
        // Remove all existing time blocks from DOM
        this.state.timeBlocks.forEach(block => {
            if (block && block.parentNode) {
                block.parentNode.removeChild(block);
            }
        });
        
        // Clear the timeBlocks array
        this.state.timeBlocks = [];
        
        // Update day summaries to show 0 hours
        this.updateDaySummaries();
        
        console.log('Calendar cleared');
    }
    
    /**
     * Check if current user is timesheet admin
     */
    async checkTimesheetAdmin() {
        try {
            const response = await new Promise((resolve, reject) => {
                frappe.call({
                    method: 'erplite.projects.api.is_timesheet_admin',
                    callback: (r) => {
                        resolve(r.message);
                    },
                    error: (err) => {
                        reject(err);
                    }
                });
            });
            
            this.state.isTimesheetAdmin = response;
            
            if (response) {
                await this.loadTimesheetUsers();
                this.showUserSelector();
            }
            
        } catch (error) {
            console.error('Failed to check admin status:', error);
            this.state.isTimesheetAdmin = false;
        }
    }
    
    /**
     * Load list of users for admin
     */
    async loadTimesheetUsers() {
        try {
            const response = await new Promise((resolve, reject) => {
                frappe.call({
                    method: 'erplite.projects.api.get_timesheet_users',
                    callback: (r) => {
                        resolve(r.message || []);
                    },
                    error: (err) => {
                        reject(err);
                    }
                });
            });
            
            this.state.timesheetUsers = response;
            this.populateUserSelector();
            
        } catch (error) {
            console.error('Failed to load timesheet users:', error);
            this.state.timesheetUsers = [];
        }
    }
    
    /**
     * Show user selector for admins
     */
    showUserSelector() {
        const regularTitle = document.getElementById('regularTitle');
        const adminUserSelector = document.getElementById('adminUserSelector');
        const assignActivitiesBtn = document.getElementById('assignActivitiesBtn');
        
        if (regularTitle && adminUserSelector) {
            regularTitle.style.display = 'none';
            adminUserSelector.style.display = 'flex';
        }
        
        // Show assign activities button for admins (now in calendar actions)
        if (assignActivitiesBtn) {
            assignActivitiesBtn.style.display = 'flex';
        }
    }
    
    /**
     * Populate user selector dropdown
     */
    populateUserSelector() {
        const userSelect = document.getElementById('timesheetUserSelect');
        if (!userSelect || !this.state.timesheetUsers) return;
        
        // Check for previously selected user in localStorage
        const savedUser = localStorage.getItem('timesheet_admin_selected_user');
        
        // Clear existing options except the first one
        userSelect.innerHTML = '<option value="">Select User</option>';
        
        // Add current user as first option
        const currentUserOption = document.createElement('option');
        currentUserOption.value = frappe.session.user;
        currentUserOption.textContent = `${frappe.session.user} (You)`;
        currentUserOption.selected = !savedUser || savedUser === frappe.session.user;
        userSelect.appendChild(currentUserOption);
        
        // Add other users
        this.state.timesheetUsers.forEach(user => {
            if (user.name !== frappe.session.user) {
                const option = document.createElement('option');
                option.value = user.name;
                option.textContent = user.full_name || user.name;
                option.selected = savedUser === user.name;
                userSelect.appendChild(option);
            }
        });
        
        // If there was a saved user selection, restore it
        if (savedUser && savedUser !== frappe.session.user) {
            // Set the current target user
            this.state.currentTargetUser = savedUser;
            
            // Set the dropdown value to the saved user
            userSelect.value = savedUser;
            
            // Trigger the user switch to load their data
            setTimeout(() => {
                window.switchTimesheetUser();
            }, 100); // Small delay to ensure DOM is ready
        } else if (savedUser === frappe.session.user) {
            // If saved user is current user, make sure we load their data
            this.state.currentTargetUser = null; // Reset to null for current user
        }
    }
    
    /**
     * Initialize all managers
     */
    initializeManagers() {
        this.managers.dragDrop = new DragDropManager(this);
        this.managers.timeBlock = new TimeBlockManager(this);
        this.managers.calendar = new CalendarManager(this);
        this.managers.mobile = new MobileManager(this);
        this.managers.storage = new StorageManager(this);
    }
    
    /**
     * Initialize all components
     */
    initializeComponents() {
        this.components.sidebar = new SidebarComponent(this);
        this.components.calendar = new CalendarComponent(this);
        this.components.timeBlock = new TimeBlockComponent(this);
        this.components.modal = new ModalComponent(this);
        this.components.quickEntry = new QuickEntryComponent(this);
        this.components.contextMenu = new ContextMenuComponent(this);
        this.components.toast = new ToastComponent(this);
    }
    
    /**
     * Setup global event listeners
     */
    setupGlobalEvents() {
        // Only setup events if we're on the timesheet calendar page
        if (!window.location.pathname.includes('timesheet-calendar')) {
            return;
        }
        
        // Store event handlers for cleanup
        this.keydownHandler = (e) => {
            // Only handle keyboard shortcuts if the page is visible and focused
            if (document.hidden || !document.hasFocus()) {
                return;
            }
            this.handleKeyboardShortcuts(e);
        };
        
        this.clickHandler = (e) => {
            // Only handle clicks if the page is visible and focused
            if (document.hidden || !document.hasFocus()) {
                return;
            }
            this.handleGlobalClick(e);
        };
        
        this.resizeHandler = () => {
            this.handleWindowResize();
        };
        
        // Keyboard shortcuts (only when page is focused)
        document.addEventListener('keydown', this.keydownHandler);
        
        // Clear selection when clicking outside (only when page is focused)
        document.addEventListener('click', this.clickHandler);
        
        // Window resize for responsive behavior
        window.addEventListener('resize', this.resizeHandler);
    }
    
    /**
     * Clean up event listeners
     */
    cleanup() {
        if (this.keydownHandler) {
            document.removeEventListener('keydown', this.keydownHandler);
            this.keydownHandler = null;
        }
        
        if (this.clickHandler) {
            document.removeEventListener('click', this.clickHandler);
            this.clickHandler = null;
        }
        
        if (this.resizeHandler) {
            window.removeEventListener('resize', this.resizeHandler);
            this.resizeHandler = null;
        }
    }
    
    /**
     * Initialize existing time blocks from server data
     */
    initializeExistingTimeBlocks() {
        let hasEntriesOutsideWorkingHours = false;
        
        this.state.existingTimesheets.forEach(timesheet => {
            if (timesheet.check_in_time && timesheet.check_out_time) {
                const startTime = new Date(timesheet.check_in_time);
                const endTime = new Date(timesheet.check_out_time);
                const startHour = startTime.getHours();
                const endHour = endTime.getHours();
                
                // Check if any time entries are outside working hours (6-19)
                if (startHour < 6 || startHour >= 19 || endHour < 6 || endHour > 19) {
                    hasEntriesOutsideWorkingHours = true;
                }
                
                this.managers.timeBlock.createTimeBlock({
                    project: timesheet.project,
                    activity: timesheet.activity,
                    projectName: timesheet.project_name || timesheet.project,
                    activityName: timesheet.activity_name || timesheet.activity,
                    color: this.state.projectColors[timesheet.project] || '#6b7280',
                    date: timesheet.date,
                    startHour: startHour,
                    startMinute: startTime.getMinutes(),
                    duration: timesheet.duration_hours || 1,
                    description: timesheet.description || '',
                    id: timesheet.name
                });
            }
        });
        
        // If there are entries outside working hours, force full day view
        if (hasEntriesOutsideWorkingHours) {
            this.managers.calendar.forceFullDayView();
        }
        
        this.updateDaySummaries();
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(e) {
        // Ctrl/Cmd + S to save
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            this.managers.storage.saveTimesheet();
        }
        
        // Ctrl/Cmd + 1-4 for quick time entries
        if ((e.ctrlKey || e.metaKey) && ['1', '2', '3', '4'].includes(e.key)) {
            e.preventDefault();
            const hours = parseInt(e.key);
            this.addQuickTime(hours);
        }
        
        // Delete key to delete selected time block
        if (e.key === 'Delete' && this.state.selectedTimeBlock) {
            e.preventDefault();
            this.managers.timeBlock.deleteTimeBlock(this.state.selectedTimeBlock);
        }
        
        // Escape to clear selection
        if (e.key === 'Escape') {
            this.clearSelection();
        }
    }
    
    /**
     * Handle global clicks for selection management
     */
    handleGlobalClick(e) {
        // Don't clear selection if clicking on selected block or its controls
        if (this.state.selectedTimeBlock && (
            this.state.selectedTimeBlock.contains(e.target) ||
            e.target.classList.contains('control-btn') ||
            e.target.closest('.time-block-controls')
        )) {
            return;
        }
        
        this.clearSelection();
    }
    
    /**
     * Handle window resize
     */
    handleWindowResize() {
        if (this.managers.mobile) {
            this.managers.mobile.handleResize();
        }
    }
    
    /**
     * Select a time block
     */
    selectTimeBlock(timeBlock) {
        this.clearSelection();
        this.state.selectedTimeBlock = timeBlock;
        timeBlock.classList.add('selected');
        this.components.timeBlock.setupControlButtons(timeBlock);
    }
    
    /**
     * Clear current selection
     */
    clearSelection() {
        if (this.state.selectedTimeBlock) {
            this.state.selectedTimeBlock.classList.remove('selected');
            this.state.selectedTimeBlock = null;
        }
    }
    
    /**
     * Update day summaries
     */
    updateDaySummaries() {
        document.querySelectorAll('.day-column').forEach(dayColumn => {
            const blocks = dayColumn.querySelectorAll('.time-block');
            let totalHours = 0;
            
            blocks.forEach(block => {
                totalHours += parseFloat(block.dataset.duration || 0);
            });
            
            const summary = dayColumn.querySelector('.total-hours');
            if (summary) {
                summary.textContent = `${totalHours.toFixed(1)}h`;
            }
        });
    }
    
    /**
     * Add quick time entry
     */
    addQuickTime(hours) {
        const today = new Date().toISOString().split('T')[0];
        const currentHour = new Date().getHours();
        
        // Find first available project/activity
        const firstActivityBlock = document.querySelector('.activity-block');
        if (!firstActivityBlock) {
            this.components.toast.show('No activities available. Please create a project and activity first.', 'warning');
            return;
        }
        
        const activityData = {
            project: firstActivityBlock.dataset.project,
            activity: firstActivityBlock.dataset.activity,
            projectName: firstActivityBlock.dataset.projectName,
            activityName: firstActivityBlock.dataset.activityName,
            color: firstActivityBlock.dataset.color,
            date: today,
            startHour: Math.max(6, currentHour),
            startMinute: 0,
            duration: hours
        };
        
        this.managers.timeBlock.createTimeBlock(activityData);
        this.updateDaySummaries();
    }
    
    /**
     * Get current application state
     */
    getState() {
        return { ...this.state };
    }
    
    /**
     * Update application state
     */
    setState(updates) {
        Object.assign(this.state, updates);
    }
    
    /**
     * Get a specific manager
     */
    getManager(name) {
        return this.managers[name];
    }
    
    /**
     * Get a specific component
     */
    getComponent(name) {
        return this.components[name];
    }
}

// Export to global scope for HTML compatibility
window.TimesheetCalendar = TimesheetCalendar;

// Global function for switching timesheet user (for HTML compatibility)
window.switchTimesheetUser = async function() {
    if (window.app && window.app.state.isTimesheetAdmin) {
        const userSelect = document.getElementById('timesheetUserSelect');
        const selectedUser = userSelect.value;
        
        if (selectedUser) {
            try {
                // Show loading indicator
                if (window.app.components.toast) {
                    window.app.components.toast.show('Loading data for selected user...', 'info');
                }
                
                // Update current target user - set to null if viewing own timesheet
                if (selectedUser === frappe.session.user) {
                    window.app.state.currentTargetUser = null;
                } else {
                    window.app.state.currentTargetUser = selectedUser;
                }
                
                console.log('Current target user set to:', window.app.state.currentTargetUser);
                
                // Save selected user to localStorage for persistence
                localStorage.setItem('timesheet_admin_selected_user', selectedUser);
                
                // Clear the current calendar
                window.app.clearCalendar();
                
                // Load both projects and timesheet data for the selected user
                await Promise.all([
                    window.app.loadProjectsData(selectedUser === frappe.session.user ? null : selectedUser),
                    window.app.loadTimesheetData(selectedUser === frappe.session.user ? null : selectedUser)
                ]);
                
                // Refresh the sidebar with new project data
                if (window.app.components.sidebar) {
                    window.app.components.sidebar.refreshProjectsFromAPI();
                }
                
                // Reinitialize time blocks with the new timesheet data
                window.app.initializeExistingTimeBlocks();
                
                if (window.app.components.toast) {
                    const userName = userSelect.options[userSelect.selectedIndex].text;
                    window.app.components.toast.show(`Switched to viewing ${userName}'s timesheet`, 'success');
                }
                
            } catch (error) {
                console.error('Failed to switch user:', error);
                if (window.app.components.toast) {
                    window.app.components.toast.error('Failed to switch user');
                }
            }
        }
    }
};

// Global functions for assign activities dialog (for HTML compatibility)
window.showAssignActivitiesDialog = async function() {
    if (!window.app || !window.app.state.isTimesheetAdmin) {
        return;
    }
    
    try {
        // Load users and projects data
        await Promise.all([
            loadAssignmentUsers(),
            loadAssignmentProjects()
        ]);
        
        // Show the modal
        const modal = document.getElementById('assignActivitiesModal');
        if (modal) {
            modal.style.display = 'block';
        }
        
    } catch (error) {
        console.error('Failed to load assignment data:', error);
        if (window.app.components.toast) {
            window.app.components.toast.error('Failed to load assignment data');
        }
    }
};

window.closeAssignActivitiesDialog = function() {
    const modal = document.getElementById('assignActivitiesModal');
    if (modal) {
        modal.style.display = 'none';
    }
    
    // Reset form
    document.getElementById('assignUser').value = '';
    document.getElementById('assignProject').value = '';
    document.getElementById('activityAssignmentList').innerHTML = '<p class="no-activities">Select a project to see available activities</p>';
    document.getElementById('saveAssignmentsBtn').disabled = true;
};

window.loadProjectActivities = async function() {
    const projectSelect = document.getElementById('assignProject');
    const userSelect = document.getElementById('assignUser');
    const activityList = document.getElementById('activityAssignmentList');
    const saveBtn = document.getElementById('saveAssignmentsBtn');
    
    const selectedProject = projectSelect.value;
    const selectedUser = userSelect.value;
    
    if (!selectedProject) {
        activityList.innerHTML = '<p class="no-activities">Select a project to see available activities</p>';
        saveBtn.disabled = true;
        return;
    }
    
    try {
        // Get all projects and activities data
        const response = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'erplite.projects.api.get_all_projects_and_activities',
                callback: (r) => {
                    if (r.message && r.message.success) {
                        resolve(r.message.data);
                    } else {
                        reject(new Error(r.message?.message || 'Failed to load activities'));
                    }
                },
                error: (err) => {
                    reject(err);
                }
            });
        });
        
        const projectData = response[selectedProject];
        if (!projectData || !projectData.activities || projectData.activities.length === 0) {
            activityList.innerHTML = '<p class="no-activities">No activities found in this project</p>';
            saveBtn.disabled = true;
            return;
        }
        
        // Build activity list
        let html = '';
        projectData.activities.forEach(activity => {
            const isAssigned = activity.assigned_to === selectedUser;
            const statusClass = isAssigned ? 'status-assigned' : 'status-unassigned';
            const statusText = isAssigned ? 'Assigned' : 'Unassigned';
            
            html += `
                <div class="activity-assignment-item" onclick="toggleActivityAssignment(this)">
                    <input type="checkbox" class="activity-assignment-checkbox" 
                           data-activity-id="${activity.name}" 
                           ${isAssigned ? 'checked' : ''}>
                    <div class="activity-assignment-info">
                        <div class="activity-assignment-name">${activity.subject}</div>
                        ${activity.description ? `<div class="activity-assignment-description">${activity.description}</div>` : ''}
                    </div>
                    <div class="activity-assignment-status ${statusClass}">${statusText}</div>
                </div>
            `;
        });
        
        activityList.innerHTML = html;
        saveBtn.disabled = !selectedUser;
        
    } catch (error) {
        console.error('Failed to load project activities:', error);
        activityList.innerHTML = '<p class="no-activities">Error loading activities</p>';
        saveBtn.disabled = true;
        
        if (window.app.components.toast) {
            window.app.components.toast.error('Failed to load project activities');
        }
    }
};

window.toggleActivityAssignment = function(item) {
    const checkbox = item.querySelector('.activity-assignment-checkbox');
    const statusElement = item.querySelector('.activity-assignment-status');
    
    // Toggle checkbox
    checkbox.checked = !checkbox.checked;
    
    // Update status display
    if (checkbox.checked) {
        statusElement.textContent = 'Assigned';
        statusElement.className = 'activity-assignment-status status-assigned';
        item.classList.add('selected');
    } else {
        statusElement.textContent = 'Unassigned';
        statusElement.className = 'activity-assignment-status status-unassigned';
        item.classList.remove('selected');
    }
};

window.saveActivityAssignments = async function() {
    const userSelect = document.getElementById('assignUser');
    const selectedUser = userSelect.value;
    
    if (!selectedUser) {
        if (window.app.components.toast) {
            window.app.components.toast.error('Please select a user');
        }
        return;
    }
    
    // Get button reference and original text outside try block
    const saveBtn = document.getElementById('saveAssignmentsBtn');
    const originalText = saveBtn.textContent;
    
    try {
        // Collect all activity assignments
        const checkboxes = document.querySelectorAll('.activity-assignment-checkbox');
        const assignments = [];
        
        checkboxes.forEach(checkbox => {
            assignments.push({
                activity_id: checkbox.dataset.activityId,
                assign: checkbox.checked
            });
        });
        
        if (assignments.length === 0) {
            if (window.app.components.toast) {
                window.app.components.toast.error('No activities to assign');
            }
            return;
        }
        
        // Show loading
        saveBtn.textContent = 'Saving...';
        saveBtn.disabled = true;
        
        // Save assignments
        const response = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'erplite.projects.api.assign_activities_to_user',
                args: {
                    user: selectedUser,
                    activity_assignments: JSON.stringify(assignments)
                },
                callback: (r) => {
                    if (r.message && r.message.success) {
                        resolve(r.message);
                    } else {
                        reject(new Error(r.message?.message || 'Failed to save assignments'));
                    }
                },
                error: (err) => {
                    reject(err);
                }
            });
        });
        
        // Success
        if (window.app.components.toast) {
            window.app.components.toast.show(response.message, 'success');
        }
        
        // Close dialog
        closeAssignActivitiesDialog();
        
        // Refresh current view if viewing the same user
        const currentUserSelect = document.getElementById('timesheetUserSelect');
        if (currentUserSelect && currentUserSelect.value === selectedUser) {
            await switchTimesheetUser();
        }
        
    } catch (error) {
        console.error('Failed to save activity assignments:', error);
        if (window.app.components.toast) {
            window.app.components.toast.error('Failed to save activity assignments');
        }
    } finally {
        // Reset button
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
    }
};

// Helper functions
async function loadAssignmentUsers() {
    const userSelect = document.getElementById('assignUser');
    
    if (window.app.state.timesheetUsers) {
        // Clear and populate users
        userSelect.innerHTML = '<option value="">Select User</option>';
        
        window.app.state.timesheetUsers.forEach(user => {
            const option = document.createElement('option');
            option.value = user.name;
            option.textContent = user.full_name || user.name;
            userSelect.appendChild(option);
        });
    }
}

async function loadAssignmentProjects() {
    const projectSelect = document.getElementById('assignProject');
    
    try {
        const response = await new Promise((resolve, reject) => {
            frappe.call({
                method: 'erplite.projects.api.get_all_projects_and_activities',
                callback: (r) => {
                    if (r.message && r.message.success) {
                        resolve(r.message.data);
                    } else {
                        reject(new Error(r.message?.message || 'Failed to load projects'));
                    }
                },
                error: (err) => {
                    reject(err);
                }
            });
        });
        
        // Clear and populate projects
        projectSelect.innerHTML = '<option value="">Select Project</option>';
        
        Object.entries(response).forEach(([projectId, projectData]) => {
            const option = document.createElement('option');
            option.value = projectId;
            option.textContent = projectData.project_name;
            projectSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('Failed to load projects:', error);
        projectSelect.innerHTML = '<option value="">Error loading projects</option>';
    }
}
