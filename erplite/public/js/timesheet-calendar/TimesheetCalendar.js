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
            selectedTimeBlock: null
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
    async loadProjectsData() {
        try {
            const response = await new Promise((resolve, reject) => {
                frappe.call({
                    method: 'erplite.projects.api.get_projects_and_activities',
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
                
                // Check if any time entries are outside working hours (6-18)
                if (startHour < 6 || startHour >= 18 || endHour < 6 || endHour > 18) {
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
