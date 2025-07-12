/**
 * EventBus - Simple event communication system for scheduler modules
 * Enables loose coupling between modules through event-driven architecture
 */
class EventBus {
    constructor() {
        this.events = new Map();
        this.debugMode = false;
    }

    /**
     * Subscribe to an event
     * @param {string} eventName - Name of the event
     * @param {Function} callback - Function to call when event is triggered
     * @param {Object} context - Context to bind the callback to
     * @returns {Function} Unsubscribe function
     */
    on(eventName, callback, context = null) {
        if (!this.events.has(eventName)) {
            this.events.set(eventName, []);
        }

        const listener = {
            callback: context ? callback.bind(context) : callback,
            context: context
        };

        this.events.get(eventName).push(listener);

        if (this.debugMode) {
            console.log(`[EventBus] Subscribed to '${eventName}'`);
        }

        // Return unsubscribe function
        return () => this.off(eventName, callback, context);
    }

    /**
     * Unsubscribe from an event
     * @param {string} eventName - Name of the event
     * @param {Function} callback - Function to remove
     * @param {Object} context - Context that was bound
     */
    off(eventName, callback, context = null) {
        if (!this.events.has(eventName)) return;

        const listeners = this.events.get(eventName);
        const index = listeners.findIndex(listener => 
            listener.callback === callback || 
            (context && listener.context === context)
        );

        if (index !== -1) {
            listeners.splice(index, 1);
            
            if (this.debugMode) {
                console.log(`[EventBus] Unsubscribed from '${eventName}'`);
            }

            // Clean up empty event arrays
            if (listeners.length === 0) {
                this.events.delete(eventName);
            }
        }
    }

    /**
     * Emit an event to all subscribers
     * @param {string} eventName - Name of the event
     * @param {*} data - Data to pass to subscribers
     */
    emit(eventName, data = null) {
        if (!this.events.has(eventName)) {
            if (this.debugMode) {
                console.log(`[EventBus] No listeners for '${eventName}'`);
            }
            return;
        }

        const listeners = this.events.get(eventName);
        
        if (this.debugMode) {
            console.log(`[EventBus] Emitting '${eventName}' to ${listeners.length} listeners`, data);
        }

        // Call all listeners
        listeners.forEach(listener => {
            try {
                listener.callback(data);
            } catch (error) {
                console.error(`[EventBus] Error in listener for '${eventName}':`, error);
            }
        });
    }

    /**
     * Subscribe to an event only once
     * @param {string} eventName - Name of the event
     * @param {Function} callback - Function to call when event is triggered
     * @param {Object} context - Context to bind the callback to
     */
    once(eventName, callback, context = null) {
        const onceCallback = (data) => {
            callback.call(context, data);
            this.off(eventName, onceCallback);
        };

        this.on(eventName, onceCallback);
    }

    /**
     * Remove all listeners for an event or all events
     * @param {string} eventName - Optional event name to clear
     */
    clear(eventName = null) {
        if (eventName) {
            this.events.delete(eventName);
            if (this.debugMode) {
                console.log(`[EventBus] Cleared all listeners for '${eventName}'`);
            }
        } else {
            this.events.clear();
            if (this.debugMode) {
                console.log('[EventBus] Cleared all listeners');
            }
        }
    }

    /**
     * Get list of all event names
     * @returns {Array} Array of event names
     */
    getEventNames() {
        return Array.from(this.events.keys());
    }

    /**
     * Get number of listeners for an event
     * @param {string} eventName - Name of the event
     * @returns {number} Number of listeners
     */
    getListenerCount(eventName) {
        return this.events.has(eventName) ? this.events.get(eventName).length : 0;
    }

    /**
     * Enable or disable debug mode
     * @param {boolean} enabled - Whether to enable debug mode
     */
    setDebugMode(enabled) {
        this.debugMode = enabled;
        console.log(`[EventBus] Debug mode ${enabled ? 'enabled' : 'disabled'}`);
    }

    /**
     * Get debug information about the event bus
     * @returns {Object} Debug information
     */
    getDebugInfo() {
        const info = {
            totalEvents: this.events.size,
            events: {}
        };

        this.events.forEach((listeners, eventName) => {
            info.events[eventName] = {
                listenerCount: listeners.length,
                listeners: listeners.map(l => ({
                    hasContext: !!l.context,
                    contextName: l.context ? l.context.constructor.name : null
                }))
            };
        });

        return info;
    }
}

// Export for use in other modules
window.SchedulerEventBus = EventBus;
