/**
 * StateManager - Centralized state management for the scheduler
 * Handles all application state with change notifications
 */
class StateManager {
    constructor(eventBus) {
        this.eventBus = eventBus;
        this.state = this.getInitialState();
        this.debugMode = false;
    }

    /**
     * Get initial state structure
     * @returns {Object} Initial state
     */
    getInitialState() {
        return {
            // Date and view settings
            currentStartDate: this.getTodayString(),
            dateRange: 30,
            
            // Data
            projects: [],
            resources: [],
            scheduleEntries: [],
            scheduleRows: [],
            projectColors: {},
            
            // UI state
            isLoading: false,
            selectedRows: [],
            dragSelection: null,
            resizeState: null,
            
            // Modal state
            activeModal: null,
            modalData: null,
            
            // Dropdown state
            activeDropdown: null,
            dropdownData: null
        };
    }

    /**
     * Get current state or specific property
     * @param {string} path - Optional dot-notation path to specific property
     * @returns {*} State value
     */
    get(path = null) {
        if (!path) {
            return { ...this.state };
        }

        return this.getNestedProperty(this.state, path);
    }

    /**
     * Set state property with change notification
     * @param {string|Object} pathOrObject - Dot-notation path or object to merge
     * @param {*} value - Value to set (if path is string)
     */
    set(pathOrObject, value = undefined) {
        const oldState = { ...this.state };

        if (typeof pathOrObject === 'object') {
            // Merge object into state
            this.state = { ...this.state, ...pathOrObject };
        } else {
            // Set specific property
            this.setNestedProperty(this.state, pathOrObject, value);
        }

        if (this.debugMode) {
            console.log('[StateManager] State updated:', {
                path: pathOrObject,
                value: value,
                newState: this.state
            });
        }

        // Emit change event
        this.eventBus.emit('state:changed', {
            oldState,
            newState: { ...this.state },
            path: pathOrObject,
            value
        });

        // Emit specific property change events
        if (typeof pathOrObject === 'string') {
            this.eventBus.emit(`state:${pathOrObject}:changed`, {
                oldValue: this.getNestedProperty(oldState, pathOrObject),
                newValue: value,
                path: pathOrObject
            });
        }
    }

    /**
     * Update array in state (add, remove, update items)
     * @param {string} arrayPath - Path to array property
     * @param {string} operation - 'add', 'remove', 'update', 'replace'
     * @param {*} data - Data for operation
     */
    updateArray(arrayPath, operation, data) {
        const array = this.getNestedProperty(this.state, arrayPath);
        
        if (!Array.isArray(array)) {
            console.error(`[StateManager] Property at ${arrayPath} is not an array`);
            return;
        }

        let newArray = [...array];

        switch (operation) {
            case 'add':
                newArray.push(data);
                break;
            
            case 'remove':
                if (typeof data === 'number') {
                    // Remove by index
                    newArray.splice(data, 1);
                } else if (typeof data === 'function') {
                    // Remove by predicate
                    newArray = newArray.filter(item => !data(item));
                } else {
                    // Remove by value
                    const index = newArray.indexOf(data);
                    if (index !== -1) {
                        newArray.splice(index, 1);
                    }
                }
                break;
            
            case 'update':
                if (data.index !== undefined) {
                    // Update by index
                    newArray[data.index] = { ...newArray[data.index], ...data.updates };
                } else if (data.predicate && typeof data.predicate === 'function') {
                    // Update by predicate
                    const index = newArray.findIndex(data.predicate);
                    if (index !== -1) {
                        newArray[index] = { ...newArray[index], ...data.updates };
                    }
                }
                break;
            
            case 'replace':
                newArray = Array.isArray(data) ? [...data] : [data];
                break;
            
            default:
                console.error(`[StateManager] Unknown array operation: ${operation}`);
                return;
        }

        this.set(arrayPath, newArray);
    }

    /**
     * Reset state to initial values
     */
    reset() {
        const oldState = { ...this.state };
        this.state = this.getInitialState();
        
        if (this.debugMode) {
            console.log('[StateManager] State reset to initial values');
        }

        this.eventBus.emit('state:reset', {
            oldState,
            newState: { ...this.state }
        });
    }

    /**
     * Subscribe to state changes
     * @param {string} path - Optional path to watch specific property
     * @param {Function} callback - Callback function
     * @returns {Function} Unsubscribe function
     */
    subscribe(path, callback) {
        if (typeof path === 'function') {
            // Subscribe to all state changes
            callback = path;
            return this.eventBus.on('state:changed', callback);
        } else {
            // Subscribe to specific property changes
            return this.eventBus.on(`state:${path}:changed`, callback);
        }
    }

    /**
     * Get nested property using dot notation
     * @param {Object} obj - Object to search
     * @param {string} path - Dot-notation path
     * @returns {*} Property value
     */
    getNestedProperty(obj, path) {
        return path.split('.').reduce((current, key) => {
            return current && current[key] !== undefined ? current[key] : undefined;
        }, obj);
    }

    /**
     * Set nested property using dot notation
     * @param {Object} obj - Object to modify
     * @param {string} path - Dot-notation path
     * @param {*} value - Value to set
     */
    setNestedProperty(obj, path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        
        const target = keys.reduce((current, key) => {
            if (!current[key] || typeof current[key] !== 'object') {
                current[key] = {};
            }
            return current[key];
        }, obj);
        
        target[lastKey] = value;
    }

    /**
     * Validate state structure
     * @returns {Object} Validation result
     */
    validate() {
        const errors = [];
        const warnings = [];

        // Check required properties
        const required = ['currentStartDate', 'dateRange', 'projects', 'resources', 'scheduleRows'];
        required.forEach(prop => {
            if (this.state[prop] === undefined) {
                errors.push(`Missing required property: ${prop}`);
            }
        });

        // Check data types
        if (typeof this.state.dateRange !== 'number' || this.state.dateRange <= 0) {
            errors.push('dateRange must be a positive number');
        }

        if (!Array.isArray(this.state.projects)) {
            errors.push('projects must be an array');
        }

        if (!Array.isArray(this.state.resources)) {
            errors.push('resources must be an array');
        }

        if (!Array.isArray(this.state.scheduleRows)) {
            errors.push('scheduleRows must be an array');
        }

        // Check date format
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(this.state.currentStartDate)) {
            errors.push('currentStartDate must be in YYYY-MM-DD format');
        }

        return {
            isValid: errors.length === 0,
            errors,
            warnings
        };
    }

    /**
     * Get today's date as string
     * @returns {string} Today's date in YYYY-MM-DD format
     */
    getTodayString() {
        return new Date().toISOString().split('T')[0];
    }

    /**
     * Enable or disable debug mode
     * @param {boolean} enabled - Whether to enable debug mode
     */
    setDebugMode(enabled) {
        this.debugMode = enabled;
        console.log(`[StateManager] Debug mode ${enabled ? 'enabled' : 'disabled'}`);
    }

    /**
     * Get debug information about the state
     * @returns {Object} Debug information
     */
    getDebugInfo() {
        const validation = this.validate();
        
        return {
            stateSize: JSON.stringify(this.state).length,
            validation,
            properties: Object.keys(this.state),
            arrayLengths: {
                projects: this.state.projects?.length || 0,
                resources: this.state.resources?.length || 0,
                scheduleRows: this.state.scheduleRows?.length || 0,
                scheduleEntries: this.state.scheduleEntries?.length || 0
            }
        };
    }
}

// Export for use in other modules
window.SchedulerStateManager = StateManager;
