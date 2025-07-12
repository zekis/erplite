/**
 * Timesheet Calendar - Main Entry Point
 * This file is automatically loaded by Frappe and initializes the modular timesheet calendar
 */

// Module loading order is important for dependencies
const MODULES = [
    // Utilities first
    '/assets/erplite/js/timesheet-calendar/utils/TimeUtils.js',
    '/assets/erplite/js/timesheet-calendar/utils/DOMUtils.js',
    
    // Managers
    '/assets/erplite/js/timesheet-calendar/managers/StorageManager.js',
    '/assets/erplite/js/timesheet-calendar/managers/TimeBlockManager.js',
    '/assets/erplite/js/timesheet-calendar/managers/DragDropManager.js',
    '/assets/erplite/js/timesheet-calendar/managers/CalendarManager.js',
    '/assets/erplite/js/timesheet-calendar/managers/MobileManager.js',
    
    // Components
    '/assets/erplite/js/timesheet-calendar/components/ToastComponent.js',
    '/assets/erplite/js/timesheet-calendar/components/TimeBlockComponent.js',
    '/assets/erplite/js/timesheet-calendar/components/ModalComponent.js',
    '/assets/erplite/js/timesheet-calendar/components/QuickEntryComponent.js',
    '/assets/erplite/js/timesheet-calendar/components/SidebarComponent.js',
    '/assets/erplite/js/timesheet-calendar/components/ContextMenuComponent.js',
    '/assets/erplite/js/timesheet-calendar/components/CalendarComponent.js',
    
    // Main application controller
    '/assets/erplite/js/timesheet-calendar/TimesheetCalendar.js'
];

/**
 * Load a JavaScript module
 */
function loadModule(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

/**
 * Load all modules in sequence
 */
async function loadModules() {
    try {
        for (const module of MODULES) {
            await loadModule(module);
            console.log(`Loaded: ${module}`);
        }
        console.log('All timesheet calendar modules loaded successfully');
        return true;
    } catch (error) {
        console.error('Failed to load timesheet calendar module:', error);
        return false;
    }
}

/**
 * Initialize the timesheet calendar application
 */
async function initializeTimesheetCalendar() {
    console.log('Initializing Timesheet Calendar...');
    
    // Show loading indicator
    const loadingIndicator = document.createElement('div');
    loadingIndicator.id = 'timesheet-loading';
    loadingIndicator.innerHTML = `
        <div style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        ">
            <div style="text-align: center;">
                <div style="
                    width: 40px;
                    height: 40px;
                    border: 4px solid #e2e8f0;
                    border-top: 4px solid #3b82f6;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 1rem auto;
                "></div>
                <div style="color: #64748b; font-size: 0.875rem;">Loading Timesheet Calendar...</div>
            </div>
        </div>
        <style>
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    `;
    
    // Only show loading if we're on the timesheet calendar page
    if (window.location.pathname.includes('timesheet-calendar')) {
        document.body.appendChild(loadingIndicator);
    }
    
    try {
        // Load all modules
        const modulesLoaded = await loadModules();
        
        if (!modulesLoaded) {
            throw new Error('Failed to load required modules');
        }
        
        // Wait a bit for modules to initialize
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Initialize the main application
        if (typeof TimesheetCalendar !== 'undefined') {
            window.app = new TimesheetCalendar();
            console.log('Timesheet Calendar application initialized successfully');
            
            // Setup post-initialization features
            setupPostInitialization();
        } else {
            throw new Error('TimesheetCalendar class not found');
        }
        
        // Remove loading indicator
        if (loadingIndicator.parentNode) {
            loadingIndicator.remove();
        }
        
    } catch (error) {
        console.error('Failed to initialize Timesheet Calendar:', error);
        
        // Show error message only if we're on the timesheet calendar page
        if (window.location.pathname.includes('timesheet-calendar')) {
            if (loadingIndicator.parentNode) {
                loadingIndicator.innerHTML = `
                    <div style="
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background: rgba(255, 255, 255, 0.9);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        z-index: 10000;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    ">
                        <div style="text-align: center; max-width: 400px; padding: 2rem;">
                            <div style="color: #dc2626; font-size: 1.125rem; font-weight: 600; margin-bottom: 1rem;">
                                Failed to Load Timesheet Calendar
                            </div>
                            <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 1.5rem;">
                                There was an error loading the timesheet calendar. Please refresh the page to try again.
                            </div>
                            <button onclick="window.location.reload()" style="
                                background: #3b82f6;
                                color: white;
                                border: none;
                                padding: 0.5rem 1rem;
                                border-radius: 0.375rem;
                                cursor: pointer;
                                font-size: 0.875rem;
                            ">
                                Refresh Page
                            </button>
                        </div>
                    </div>
                `;
            }
        }
    }
}

/**
 * Setup post-initialization features
 */
function setupPostInitialization() {
    // Only setup if we're on the timesheet calendar page
    if (!window.location.pathname.includes('timesheet-calendar')) {
        return;
    }
    
    // Add custom styles for enhanced features
    if (window.app && window.app.components.calendar) {
        window.app.components.calendar.addCustomStyles();
    }
    
    // Setup unload warning for unsaved changes
    if (window.app && window.app.managers.storage) {
        window.app.managers.storage.setupUnloadWarning();
    }
    
    // Initialize sidebar after full load
    if (window.app && window.app.components.sidebar) {
        window.app.components.sidebar.initializeAfterLoad();
    }
    
    // Start time highlighting if calendar manager supports it
    if (window.app && window.app.managers.calendar && window.app.managers.calendar.startTimeHighlighting) {
        window.app.managers.calendar.startTimeHighlighting();
    }
    
    // Store error handlers so we can clean them up later
    window.timesheetErrorHandler = (event) => {
        console.error('Timesheet Calendar error:', event.error);
        if (window.app && window.app.components.toast) {
            window.app.components.toast.error('An unexpected error occurred');
        }
    };
    
    window.timesheetRejectionHandler = (event) => {
        console.error('Timesheet Calendar unhandled promise rejection:', event.reason);
        if (window.app && window.app.components.toast) {
            window.app.components.toast.error('An unexpected error occurred');
        }
    };
    
    // Add global error handlers
    window.addEventListener('error', window.timesheetErrorHandler);
    window.addEventListener('unhandledrejection', window.timesheetRejectionHandler);
    
    // Setup cleanup when leaving the page
    setupPageCleanup();
    
    // Expose app to global scope for debugging
    if (typeof window !== 'undefined') {
        window.TimesheetApp = window.app;
    }
    
    console.log('Timesheet Calendar post-initialization setup complete');
}

/**
 * Setup cleanup when leaving the timesheet calendar page
 */
function setupPageCleanup() {
    // Clean up when navigating away from the page
    window.addEventListener('beforeunload', () => {
        cleanupTimesheetCalendar();
    });
    
    // Also clean up on page hide (for single-page apps like Frappe)
    window.addEventListener('pagehide', () => {
        cleanupTimesheetCalendar();
    });
}

/**
 * Clean up timesheet calendar resources
 */
function cleanupTimesheetCalendar() {
    // Clean up main application
    if (window.app && window.app.cleanup) {
        window.app.cleanup();
    }
    
    // Clean up storage manager
    if (window.app && window.app.managers.storage) {
        window.app.managers.storage.cleanup();
    }
    
    // Remove error handlers
    if (window.timesheetErrorHandler) {
        window.removeEventListener('error', window.timesheetErrorHandler);
        window.timesheetErrorHandler = null;
    }
    
    if (window.timesheetRejectionHandler) {
        window.removeEventListener('unhandledrejection', window.timesheetRejectionHandler);
        window.timesheetRejectionHandler = null;
    }
    
    console.log('Timesheet Calendar cleanup complete');
}

/**
 * Check if we're on the timesheet calendar page and dependencies are available
 */
function shouldInitialize() {
    // Check if we're on the timesheet calendar page
    if (!window.location.pathname.includes('timesheet-calendar')) {
        return false;
    }
    
    // Check if required dependencies are available
    const required = ['frappe'];
    const missing = required.filter(dep => typeof window[dep] === 'undefined');
    
    if (missing.length > 0) {
        console.warn('Timesheet Calendar: Missing dependencies:', missing);
        return false;
    }
    
    return true;
}

/**
 * Start the application when DOM is ready (only on timesheet calendar page)
 */
function startTimesheetCalendar() {
    if (!shouldInitialize()) {
        return;
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeTimesheetCalendar);
    } else {
        // DOM is already ready
        initializeTimesheetCalendar();
    }
}

// Auto-start when this script loads
startTimesheetCalendar();

// Also expose the initialization function for manual triggering if needed
window.initializeTimesheetCalendar = initializeTimesheetCalendar;

// Global functions for HTML compatibility (drag and drop)
window.allowDrop = function(event) {
    if (window.app && window.app.managers.dragDrop) {
        window.app.managers.dragDrop.allowDrop(event);
    }
};

window.dragEnter = function(event) {
    if (window.app && window.app.managers.dragDrop) {
        window.app.managers.dragDrop.dragEnter(event);
    }
};

window.dragLeave = function(event) {
    if (window.app && window.app.managers.dragDrop) {
        window.app.managers.dragDrop.dragLeave(event);
    }
};

window.dropTimeBlock = function(event) {
    if (window.app && window.app.managers.dragDrop) {
        window.app.managers.dragDrop.dropTimeBlock(event);
    }
};

// Global functions for HTML compatibility (calendar actions)
window.changeWeek = function(direction) {
    if (window.app && window.app.managers.calendar) {
        window.app.managers.calendar.changeWeek(direction);
    }
};

window.clearWeek = function() {
    if (window.app && window.app.managers.calendar) {
        window.app.managers.calendar.clearWeek();
    }
};

window.saveTimesheet = function() {
    if (window.app && window.app.managers.storage) {
        window.app.managers.storage.saveTimesheet();
    }
};

window.toggleHourRange = function() {
    if (window.app && window.app.managers.calendar) {
        window.app.managers.calendar.toggleHourRange();
    }
};

window.changeMobileDay = function(direction) {
    if (window.app && window.app.managers.mobile) {
        window.app.managers.mobile.changeMobileDay(direction);
    }
};

// Global functions for HTML compatibility (sidebar)
window.toggleProject = function(projectName) {
    if (window.app && window.app.components.sidebar) {
        window.app.components.sidebar.toggleProjectByName(projectName);
    }
};

// Global functions for HTML compatibility (modal)
window.closeEditModal = function() {
    if (window.app && window.app.components.modal) {
        window.app.components.modal.closeEditModal();
    }
};

window.updateTaskOptions = function() {
    if (window.app && window.app.components.modal) {
        window.app.components.modal.updateTaskOptions();
    }
};

window.saveTimeBlockEdit = function() {
    if (window.app && window.app.components.modal) {
        window.app.components.modal.saveTimeBlockEdit();
    }
};

window.deleteTimeBlock = function() {
    if (window.app && window.app.components.modal) {
        window.app.components.modal.deleteTimeBlock();
    }
};

// Global functions for HTML compatibility (quick entry)
window.closeQuickEntry = function() {
    if (window.app && window.app.components.quickEntry) {
        window.app.components.quickEntry.close();
    }
};

window.createQuickEntry = function() {
    if (window.app && window.app.components.quickEntry) {
        window.app.components.quickEntry.createEntry();
    }
};

// Global functions for HTML compatibility (context menu)
window.editFromContext = function() {
    if (window.app && window.app.components.contextMenu && window.app.components.contextMenu.targetElement) {
        window.app.components.modal.openEditModal(window.app.components.contextMenu.targetElement);
        window.app.components.contextMenu.hide();
    }
};

window.deleteFromContext = function() {
    if (window.app && window.app.components.contextMenu && window.app.components.contextMenu.targetElement) {
        window.app.managers.timeBlock.deleteTimeBlock(window.app.components.contextMenu.targetElement);
        window.app.components.contextMenu.hide();
    }
};

// Export for potential use in other contexts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initializeTimesheetCalendar, loadModules };
}
