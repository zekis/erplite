/**
 * Scheduler Application Initialization
 * This file initializes the scheduler when the page loads
 */
console.log('Initializing scheduler application...');
// Load JavaScript files dynamically in correct order
async function loadSchedulerScripts() {
    
    const scripts = [
        `/assets/erplite/js/scheduler/utils/SchedulerUtils.js`,
        `/assets/erplite/js/scheduler/utils/ResourceUtils.js`,
        `/assets/erplite/js/scheduler/data/DataManager.js`,
        `/assets/erplite/js/scheduler/rendering/RowRenderer.js`,
        `/assets/erplite/js/scheduler/timeblocks/TimeBlockManager.js`,
        `/assets/erplite/js/scheduler/toolbar/ToolbarManager.js`,
        `/assets/erplite/js/scheduler/DropdownManager.js`,
        `/assets/erplite/js/scheduler/ScheduleRowManager.js`,
        `/assets/erplite/js/scheduler/Scheduler.js`
    ];
    
    for (const scriptSrc of scripts) {
        await loadScript(scriptSrc);
    }
}

// Helper function to load a script and wait for it to complete
function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = () => {
            console.log(`Loaded: ${src}`);
            resolve();
        };
        script.onerror = () => {
            console.error(`Failed to load: ${src}`);
            reject(new Error(`Failed to load script: ${src}`));
        };
        document.head.appendChild(script);
    });
}

// Initialize scheduler when page is ready - try multiple methods
function startSchedulerInitialization() {
    console.log('Starting scheduler initialization...');
    
    // Method 1: Try frappe.ready if available
    if (typeof frappe !== 'undefined' && frappe.ready) {
        console.log('Using frappe.ready()');
        frappe.ready(async function() {
            console.log('frappe.ready called, starting script loading...');
            await initializeSchedulerScripts();
        });
    } 
    // Method 2: Use document ready as fallback
    else if (document.readyState === 'loading') {
        console.log('Using document.addEventListener(DOMContentLoaded)');
        document.addEventListener('DOMContentLoaded', async function() {
            console.log('DOMContentLoaded fired, starting script loading...');
            await initializeSchedulerScripts();
        });
    } 
    // Method 3: Document is already ready
    else {
        console.log('Document already ready, starting immediately');
        setTimeout(async () => {
            await initializeSchedulerScripts();
        }, 100);
    }
}

async function initializeSchedulerScripts() {
    try {
        console.log('Loading scheduler scripts...');
        await loadSchedulerScripts();
        console.log('All scheduler scripts loaded, initializing...');
        initializeScheduler();
    } catch (error) {
        console.error('Failed to load scheduler scripts:', error);
        showToast('Failed to load scheduler components: ' + error.message, 'error');
    }
}

// Start initialization immediately
startSchedulerInitialization();

function initializeScheduler() {
    // Show loading overlay
    showLoading();
    
    try {
        // Debug: Check if SchedulerApp class is available
        console.log('Checking SchedulerApp class availability...');
        console.log('window.SchedulerApp:', window.SchedulerApp);
        console.log('typeof SchedulerApp:', typeof SchedulerApp);
        
        if (typeof SchedulerApp === 'undefined') {
            throw new Error('SchedulerApp class is not defined. Check if Scheduler.js is loaded properly.');
        }
        
        // Initialize the main scheduler application
        console.log('Creating new SchedulerApp instance...');
        window.scheduler = new SchedulerApp();
        
        // Hide loading overlay after initialization
        setTimeout(() => {
            hideLoading();
        }, 500);
        
        console.log('Scheduler application initialized successfully');
    } catch (error) {
        console.error('Failed to initialize scheduler:', error);
        console.error('Error stack:', error.stack);
        hideLoading();
        showToast('Failed to initialize scheduler: ' + error.message, 'error');
    }
}

// Global functions for HTML template compatibility
window.navigateDate = function(days) {
    if (window.scheduler) {
        window.scheduler.navigateDate(days);
    }
};

window.onProjectChange = function() {
    if (window.scheduler) {
        window.scheduler.onProjectChange();
    }
};

window.onTaskChange = function() {
    if (window.scheduler) {
        window.scheduler.onTaskChange();
    }
};

window.onResourceChange = function() {
    if (window.scheduler) {
        window.scheduler.onResourceChange();
    }
};

window.clearProjectFilter = function() {
    if (window.scheduler) {
        window.scheduler.clearProjectFilter();
    }
};

window.clearTaskFilter = function() {
    if (window.scheduler) {
        window.scheduler.clearTaskFilter();
    }
};

window.clearResourceFilter = function() {
    if (window.scheduler) {
        window.scheduler.clearResourceFilter();
    }
};

window.createNewEntry = function() {
    if (window.scheduler) {
        window.scheduler.createNewEntry();
    }
};

window.showUnassignedEntries = function() {
    if (window.scheduler) {
        window.scheduler.showUnassignedEntries();
    }
};

window.hideUnassignedSection = function() {
    if (window.scheduler) {
        window.scheduler.hideUnassignedSection();
    }
};

window.refreshData = function() {
    if (window.scheduler) {
        window.scheduler.refreshData();
    }
};

window.exportSchedule = function() {
    if (window.scheduler) {
        window.scheduler.exportSchedule();
    }
};

window.addNewRow = function() {
    if (window.scheduler) {
        window.scheduler.addNewRow();
    }
};

// Shift creation global functions
window.openCreateShiftDialog = function() {
    if (window.scheduler) {
        window.scheduler.openCreateShiftDialog();
    }
};

window.closeShiftModal = function() {
    if (window.scheduler) {
        window.scheduler.closeShiftModal();
    }
};

window.saveShift = function() {
    if (window.scheduler) {
        window.scheduler.saveShift();
    }
};

// Drag and drop global functions
window.allowDrop = function(event) {
    event.preventDefault();
};

window.dragEnter = function(event) {
    event.preventDefault();
    event.target.classList.add('drop-zone');
};

window.dragLeave = function(event) {
    event.target.classList.remove('drop-zone');
};

window.dropEntry = function(event) {
    event.preventDefault();
    event.target.classList.remove('drop-zone');
    
    if (window.scheduler) {
        window.scheduler.handleDrop(event);
    }
};

// Modal functions
window.closeEntryModal = function() {
    if (window.scheduler) {
        window.scheduler.closeEntryModal();
    }
};

window.updateEntryTaskOptions = function() {
    if (window.scheduler) {
        window.scheduler.updateEntryTaskOptions();
    }
};

window.saveEntry = function() {
    if (window.scheduler) {
        window.scheduler.saveEntry();
    }
};

// Utility functions
window.showLoading = function() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = 'flex';
    }
};

window.hideLoading = function() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
};

window.showToast = function(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    // Show toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Hide and remove toast after 5 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 5000);
};

// Error handling
window.addEventListener('error', function(event) {
    console.error('Scheduler error:', event.error);
    showToast('An error occurred: ' + event.error.message, 'error');
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    showToast('An error occurred: ' + event.reason, 'error');
    event.preventDefault();
});

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Only handle shortcuts if scheduler is initialized
    if (!window.scheduler) return;
    
    // Ctrl/Cmd + N: New entry
    if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
        event.preventDefault();
        createNewEntry();
    }
    
    // Ctrl/Cmd + R: Refresh
    if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
        event.preventDefault();
        refreshData();
    }
    
    // Escape: Close modals
    if (event.key === 'Escape') {
        closeEntryModal();
    }
    
    // Arrow keys for date navigation
    if (event.ctrlKey || event.metaKey) {
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            navigateDate(-7);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            navigateDate(7);
        }
    }
});

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (!document.hidden && window.scheduler) {
        // Refresh data when page becomes visible again
        setTimeout(() => {
            refreshData();
        }, 1000);
    }
});

// Handle window resize
window.addEventListener('resize', function() {
    if (window.scheduler && window.scheduler.handleResize) {
        window.scheduler.handleResize();
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.scheduler && window.scheduler.cleanup) {
        window.scheduler.cleanup();
    }
});

console.log('Scheduler initialization script loaded');
