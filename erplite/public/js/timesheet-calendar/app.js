/**
 * Main application entry point
 * Loads all modules and initializes the timesheet calendar
 */

// Module loading order is important for dependencies
const MODULES = [
    // Utilities first
    'utils/TimeUtils.js',
    'utils/DOMUtils.js',
    
    // Managers
    'managers/StorageManager.js',
    'managers/TimeBlockManager.js',
    'managers/DragDropManager.js',
    'managers/CalendarManager.js',
    'managers/MobileManager.js',
    
    // Components
    'components/ToastComponent.js',
    'components/TimeBlockComponent.js',
    'components/ModalComponent.js',
    'components/QuickEntryComponent.js',
    'components/SidebarComponent.js',
    'components/ContextMenuComponent.js',
    'components/CalendarComponent.js',
    
    // Main application controller
    'TimesheetCalendar.js'
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
    const basePath = 'js/';
    
    try {
        for (const module of MODULES) {
            await loadModule(basePath + module);
            console.log(`Loaded: ${module}`);
        }
        console.log('All modules loaded successfully');
        return true;
    } catch (error) {
        console.error('Failed to load module:', error);
        return false;
    }
}

/**
 * Initialize the application
 */
async function initializeApp() {
    console.log('Starting Timesheet Calendar application...');
    
    // Show loading indicator
    const loadingIndicator = document.createElement('div');
    loadingIndicator.id = 'app-loading';
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
    document.body.appendChild(loadingIndicator);
    
    try {
        // Load all modules
        const modulesLoaded = await loadModules();
        
        if (!modulesLoaded) {
            throw new Error('Failed to load required modules');
        }
        
        // Wait a bit for modules to initialize
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Initialize the main application
        window.app = new TimesheetCalendar();
        
        // Remove loading indicator
        loadingIndicator.remove();
        
        console.log('Timesheet Calendar application initialized successfully');
        
        // Add any post-initialization setup
        setupPostInitialization();
        
    } catch (error) {
        console.error('Failed to initialize application:', error);
        
        // Show error message
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
                        Failed to Load Application
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

/**
 * Setup post-initialization features
 */
function setupPostInitialization() {
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
    
    // Add global error handler
    window.addEventListener('error', (event) => {
        console.error('Global error:', event.error);
        if (window.app && window.app.components.toast) {
            window.app.components.toast.error('An unexpected error occurred');
        }
    });
    
    // Add unhandled promise rejection handler
    window.addEventListener('unhandledrejection', (event) => {
        console.error('Unhandled promise rejection:', event.reason);
        if (window.app && window.app.components.toast) {
            window.app.components.toast.error('An unexpected error occurred');
        }
    });
    
    // Expose app to global scope for debugging
    if (typeof window !== 'undefined') {
        window.TimesheetApp = window.app;
    }
    
    console.log('Post-initialization setup complete');
}

/**
 * Check if all required dependencies are available
 */
function checkDependencies() {
    const required = ['frappe']; // Add other required globals here
    const missing = required.filter(dep => typeof window[dep] === 'undefined');
    
    if (missing.length > 0) {
        console.warn('Missing dependencies:', missing);
        return false;
    }
    
    return true;
}

/**
 * Start the application when DOM is ready
 */
function startApp() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeApp);
    } else {
        // DOM is already ready
        initializeApp();
    }
}

// Check dependencies and start the app
if (checkDependencies()) {
    startApp();
} else {
    console.error('Cannot start application: missing required dependencies');
    
    // Show dependency error
    document.addEventListener('DOMContentLoaded', () => {
        const errorDiv = document.createElement('div');
        errorDiv.innerHTML = `
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(255, 255, 255, 0.95);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            ">
                <div style="text-align: center; max-width: 400px; padding: 2rem;">
                    <div style="color: #dc2626; font-size: 1.125rem; font-weight: 600; margin-bottom: 1rem;">
                        Missing Dependencies
                    </div>
                    <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 1.5rem;">
                        The timesheet calendar requires Frappe framework to be loaded. Please ensure you're accessing this page through the Frappe application.
                    </div>
                    <button onclick="window.location.href='/'" style="
                        background: #3b82f6;
                        color: white;
                        border: none;
                        padding: 0.5rem 1rem;
                        border-radius: 0.375rem;
                        cursor: pointer;
                        font-size: 0.875rem;
                    ">
                        Go to Home
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(errorDiv);
    });
}

// Export for potential use in other contexts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initializeApp, loadModules };
}
