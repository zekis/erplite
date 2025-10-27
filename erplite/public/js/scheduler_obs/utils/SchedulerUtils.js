/**
 * Scheduler Utilities
 * General utility functions for the scheduler application
 */
class SchedulerUtils {
    /**
     * Date format regex for validation
     */
    static DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;

    /**
     * Template configurations for drag and drop
     */
    static TEMPLATE_CONFIGS = {
        '8h': {
            name: '8 Hour Shift',
            hours: 8,
            start_time: '09:00',
            end_time: '17:00',
            description: 'Standard 8-hour work day',
            status: 'planned'
        },
        '12h': {
            name: '12 Hour Shift',
            hours: 12,
            start_time: '07:00',
            end_time: '19:00',
            description: 'Extended 12-hour shift',
            status: 'planned'
        },
        'leave': {
            name: 'Leave',
            hours: 8,
            start_time: '00:00',
            end_time: '23:59',
            description: 'Time off / Leave',
            status: 'leave'
        }
    };

    /**
     * Get today's date as YYYY-MM-DD string
     * @returns {string} Today's date string
     */
    static getTodayString() {
        return new Date().toISOString().split('T')[0];
    }

    /**
     * Add days to a date string
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @param {number} days - Number of days to add (can be negative)
     * @returns {string} New date string in YYYY-MM-DD format
     */
    static addDays(dateString, days) {
        if (!SchedulerUtils.isValidDateString(dateString)) {
            console.warn('Invalid date string provided to addDays:', dateString);
            return SchedulerUtils.getTodayString();
        }

        const date = new Date(dateString);
        date.setDate(date.getDate() + days);
        return date.toISOString().split('T')[0];
    }

    /**
     * Calculate days between two dates (inclusive)
     * @param {string} startDate - Start date in YYYY-MM-DD format
     * @param {string} endDate - End date in YYYY-MM-DD format
     * @returns {number} Number of days between dates (0 if invalid)
     */
    static calculateDaysBetween(startDate, endDate) {
        try {
            if (!SchedulerUtils.isValidDateString(startDate) || !SchedulerUtils.isValidDateString(endDate)) {
                console.warn('Invalid date inputs in calculateDaysBetween:', startDate, endDate);
                return 0;
            }
            
            const start = new Date(startDate);
            const end = new Date(endDate);
            
            if (isNaN(start.getTime()) || isNaN(end.getTime())) {
                console.warn('Invalid date objects in calculateDaysBetween:', startDate, endDate);
                return 0;
            }
            
            return Math.floor((end - start) / (1000 * 60 * 60 * 24));
        } catch (error) {
            console.error('Error calculating days between dates:', error);
            return 0;
        }
    }

    /**
     * Check if two dates are consecutive
     * @param {string} date1 - First date in YYYY-MM-DD format
     * @param {string} date2 - Second date in YYYY-MM-DD format
     * @returns {boolean} True if dates are consecutive
     */
    static isConsecutiveDate(date1, date2) {
        return SchedulerUtils.calculateDaysBetween(date1, date2) === 1;
    }

    /**
     * Validate date string format
     * @param {string} dateString - Date string to validate
     * @returns {boolean} True if valid YYYY-MM-DD format
     */
    static isValidDateString(dateString) {
        return dateString && 
               typeof dateString === 'string' && 
               SchedulerUtils.DATE_REGEX.test(dateString);
    }

    /**
     * Check if date is weekend (Saturday or Sunday)
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @returns {boolean} True if weekend
     */
    static isWeekend(dateString) {
        if (!SchedulerUtils.isValidDateString(dateString)) {
            return false;
        }

        const date = new Date(dateString);
        const dayOfWeek = date.getDay();
        return dayOfWeek === 0 || dayOfWeek === 6; // Sunday = 0, Saturday = 6
    }

    /**
     * Check if date is today
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @returns {boolean} True if date is today
     */
    static isToday(dateString) {
        return dateString === SchedulerUtils.getTodayString();
    }

    /**
     * Format date for display
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @param {Object} options - Intl.DateTimeFormat options
     * @returns {string} Formatted date string
     */
    static formatDate(dateString, options = { month: 'short', day: 'numeric', year: 'numeric' }) {
        if (!SchedulerUtils.isValidDateString(dateString)) {
            return 'Invalid Date';
        }

        try {
            return new Date(dateString).toLocaleDateString('en-US', options);
        } catch (error) {
            console.error('Error formatting date:', error);
            return dateString;
        }
    }

    /**
     * Convert hex color to rgba with alpha
     * @param {string} hex - Hex color code
     * @param {number} alpha - Alpha value (0-1)
     * @returns {string} RGBA color string
     */
    static hexToRgba(hex, alpha = 1) {
        if (!hex || typeof hex !== 'string') {
            return `rgba(0, 0, 0, ${alpha})`;
        }

        let c = hex.replace('#', '');
        if (c.length === 3) {
            c = c.split('').map(x => x + x).join('');
        }
        
        if (c.length !== 6) {
            console.warn('Invalid hex color:', hex);
            return `rgba(0, 0, 0, ${alpha})`;
        }

        const num = parseInt(c, 16);
        const r = (num >> 16) & 255;
        const g = (num >> 8) & 255;
        const b = num & 255;
        return `rgba(${r},${g},${b},${alpha})`;
    }

    /**
     * Generate unique ID for entries
     * @param {string} prefix - Optional prefix for ID
     * @returns {string} Unique ID
     */
    static generateUniqueId(prefix = 'id') {
        return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    /**
     * Get template configuration
     * @param {string} template - Template key
     * @returns {Object} Template configuration
     */
    static getTemplateConfig(template) {
        return SchedulerUtils.TEMPLATE_CONFIGS[template] || SchedulerUtils.TEMPLATE_CONFIGS['8h'];
    }

    /**
     * Debounce function calls
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Throttle function calls
     * @param {Function} func - Function to throttle
     * @param {number} limit - Time limit in milliseconds
     * @returns {Function} Throttled function
     */
    static throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    /**
     * Deep clone an object
     * @param {Object} obj - Object to clone
     * @returns {Object} Cloned object
     */
    static deepClone(obj) {
        if (obj === null || typeof obj !== 'object') {
            return obj;
        }

        if (obj instanceof Date) {
            return new Date(obj.getTime());
        }

        if (obj instanceof Array) {
            return obj.map(item => SchedulerUtils.deepClone(item));
        }

        if (typeof obj === 'object') {
            const cloned = {};
            for (const key in obj) {
                if (obj.hasOwnProperty(key)) {
                    cloned[key] = SchedulerUtils.deepClone(obj[key]);
                }
            }
            return cloned;
        }

        return obj;
    }

    /**
     * Sanitize HTML string to prevent XSS
     * @param {string} str - String to sanitize
     * @returns {string} Sanitized string
     */
    static sanitizeHtml(str) {
        if (!str || typeof str !== 'string') {
            return '';
        }

        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Check if two entries can be grouped together
     * @param {Object} entry1 - First entry
     * @param {Object} entry2 - Second entry
     * @returns {boolean} True if entries can be grouped
     */
    static canEntriesBeGrouped(entry1, entry2) {
        if (!entry1 || !entry2) return false;

        return (
            (entry1.hours || 8) === (entry2.hours || 8) &&
            (entry1.start_time || '09:00') === (entry2.start_time || '09:00') &&
            (entry1.end_time || '17:00') === (entry2.end_time || '17:00') &&
            (entry1.status || 'planned') === (entry2.status || 'planned')
        );
    }

    /**
     * Group consecutive entries with identical properties into blocks
     * @param {Object} entries - Object with date keys and entry values
     * @returns {Array} Array of grouped blocks
     */
    static groupConsecutiveEntries(entries) {
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
                const canExtend = SchedulerUtils.canEntriesBeGrouped(currentBlock, entry) &&
                                SchedulerUtils.isConsecutiveDate(currentBlock.end_date, date);
                
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
     * Create date range array
     * @param {string} startDate - Start date in YYYY-MM-DD format
     * @param {number} days - Number of days
     * @returns {Array} Array of date strings
     */
    static createDateRange(startDate, days) {
        const dates = [];
        for (let i = 0; i < days; i++) {
            dates.push(SchedulerUtils.addDays(startDate, i));
        }
        return dates;
    }

    /**
     * Get date range display string
     * @param {string} startDate - Start date
     * @param {number} days - Number of days
     * @returns {string} Formatted date range string
     */
    static getDateRangeDisplay(startDate, days) {
        const endDate = SchedulerUtils.addDays(startDate, days - 1);
        return `${SchedulerUtils.formatDate(startDate)} - ${SchedulerUtils.formatDate(endDate)}`;
    }

    /**
     * Validate time string format (HH:MM)
     * @param {string} timeString - Time string to validate
     * @returns {boolean} True if valid time format
     */
    static isValidTimeString(timeString) {
        if (!timeString || typeof timeString !== 'string') {
            return false;
        }
        
        const timeRegex = /^([01]?[0-9]|2[0-3]):[0-5][0-9]$/;
        return timeRegex.test(timeString);
    }

    /**
     * Format time for display
     * @param {string} timeString - Time in HH:MM format
     * @returns {string} Formatted time string
     */
    static formatTime(timeString) {
        if (!SchedulerUtils.isValidTimeString(timeString)) {
            return timeString || '00:00';
        }
        
        try {
            const [hours, minutes] = timeString.split(':');
            const hour = parseInt(hours, 10);
            const ampm = hour >= 12 ? 'PM' : 'AM';
            const displayHour = hour % 12 || 12;
            return `${displayHour}:${minutes} ${ampm}`;
        } catch (error) {
            console.error('Error formatting time:', error);
            return timeString;
        }
    }

    /**
     * Calculate duration between two times
     * @param {string} startTime - Start time in HH:MM format
     * @param {string} endTime - End time in HH:MM format
     * @returns {number} Duration in hours
     */
    static calculateDuration(startTime, endTime) {
        if (!SchedulerUtils.isValidTimeString(startTime) || !SchedulerUtils.isValidTimeString(endTime)) {
            return 0;
        }
        
        try {
            const [startHours, startMinutes] = startTime.split(':').map(Number);
            const [endHours, endMinutes] = endTime.split(':').map(Number);
            
            const startTotalMinutes = startHours * 60 + startMinutes;
            const endTotalMinutes = endHours * 60 + endMinutes;
            
            let durationMinutes = endTotalMinutes - startTotalMinutes;
            
            // Handle overnight shifts
            if (durationMinutes < 0) {
                durationMinutes += 24 * 60;
            }
            
            return durationMinutes / 60;
        } catch (error) {
            console.error('Error calculating duration:', error);
            return 0;
        }
    }
}

// Export to global scope for HTML compatibility
window.SchedulerUtils = SchedulerUtils;
