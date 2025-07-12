/**
 * DateUtils - Date manipulation utilities for the scheduler
 * Handles all date-related operations and formatting
 */
class DateUtils {
    /**
     * Get today's date as string
     * @returns {string} Today's date in YYYY-MM-DD format
     */
    static getTodayString() {
        return new Date().toISOString().split('T')[0];
    }

    /**
     * Add days to a date string
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @param {number} days - Number of days to add (can be negative)
     * @returns {string} New date in YYYY-MM-DD format
     */
    static addDays(dateString, days) {
        const date = new Date(dateString);
        date.setDate(date.getDate() + days);
        return date.toISOString().split('T')[0];
    }

    /**
     * Calculate days between two dates (inclusive)
     * @param {string} startDate - Start date in YYYY-MM-DD format
     * @param {string} endDate - End date in YYYY-MM-DD format
     * @returns {number} Number of days between dates
     */
    static calculateDaysBetween(startDate, endDate) {
        try {
            // Validate that inputs are actually date strings
            if (!startDate || !endDate || typeof startDate !== 'string' || typeof endDate !== 'string') {
                console.warn('[DateUtils] Invalid date inputs in calculateDaysBetween:', startDate, endDate);
                return 0;
            }
            
            // Check if inputs look like dates (YYYY-MM-DD format)
            const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
            if (!dateRegex.test(startDate) || !dateRegex.test(endDate)) {
                console.warn('[DateUtils] Date format invalid in calculateDaysBetween:', startDate, endDate);
                return 0;
            }
            
            const start = new Date(startDate);
            const end = new Date(endDate);
            
            // Check for invalid dates
            if (isNaN(start.getTime()) || isNaN(end.getTime())) {
                console.warn('[DateUtils] Invalid date objects in calculateDaysBetween:', startDate, endDate);
                return 0;
            }
            
            return Math.floor((end - start) / (1000 * 60 * 60 * 24));
        } catch (error) {
            console.error('[DateUtils] Error calculating days between dates:', error);
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
        const d1 = new Date(date1);
        const d2 = new Date(date2);
        const diffTime = d2.getTime() - d1.getTime();
        const diffDays = diffTime / (1000 * 60 * 60 * 24);
        return diffDays === 1;
    }

    /**
     * Check if a date is a weekend (Saturday or Sunday)
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @returns {boolean} True if date is weekend
     */
    static isWeekend(dateString) {
        const date = new Date(dateString);
        const dayOfWeek = date.getDay();
        return dayOfWeek === 0 || dayOfWeek === 6; // Sunday = 0, Saturday = 6
    }

    /**
     * Check if a date is today
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @returns {boolean} True if date is today
     */
    static isToday(dateString) {
        return dateString === this.getTodayString();
    }

    /**
     * Format date for display
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @param {Object} options - Formatting options
     * @returns {string} Formatted date string
     */
    static formatDate(dateString, options = {}) {
        const defaultOptions = {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        };

        const formatOptions = { ...defaultOptions, ...options };
        const date = new Date(dateString);
        
        return date.toLocaleDateString('en-US', formatOptions);
    }

    /**
     * Get day of week name
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @param {boolean} short - Whether to return short name (Mon vs Monday)
     * @returns {string} Day of week name
     */
    static getDayOfWeek(dateString, short = true) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            weekday: short ? 'short' : 'long' 
        });
    }

    /**
     * Get month name
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @param {boolean} short - Whether to return short name (Jan vs January)
     * @returns {string} Month name
     */
    static getMonthName(dateString, short = true) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            month: short ? 'short' : 'long' 
        });
    }

    /**
     * Generate date range array
     * @param {string} startDate - Start date in YYYY-MM-DD format
     * @param {number} days - Number of days to include
     * @returns {Array} Array of date strings
     */
    static generateDateRange(startDate, days) {
        const dates = [];
        for (let i = 0; i < days; i++) {
            dates.push(this.addDays(startDate, i));
        }
        return dates;
    }

    /**
     * Get date range between two dates
     * @param {string} startDate - Start date in YYYY-MM-DD format
     * @param {string} endDate - End date in YYYY-MM-DD format
     * @returns {Array} Array of date strings between start and end (inclusive)
     */
    static getDateRangeBetween(startDate, endDate) {
        const dates = [];
        const start = new Date(startDate);
        const end = new Date(endDate);
        const current = new Date(start);

        while (current <= end) {
            dates.push(current.toISOString().split('T')[0]);
            current.setDate(current.getDate() + 1);
        }

        return dates;
    }

    /**
     * Validate date string format
     * @param {string} dateString - Date string to validate
     * @returns {boolean} True if valid YYYY-MM-DD format
     */
    static isValidDateString(dateString) {
        if (!dateString || typeof dateString !== 'string') {
            return false;
        }

        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(dateString)) {
            return false;
        }

        const date = new Date(dateString);
        return !isNaN(date.getTime()) && date.toISOString().split('T')[0] === dateString;
    }

    /**
     * Get start of week for a given date
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @param {number} startOfWeek - Day of week to start (0 = Sunday, 1 = Monday)
     * @returns {string} Start of week date in YYYY-MM-DD format
     */
    static getStartOfWeek(dateString, startOfWeek = 1) {
        const date = new Date(dateString);
        const dayOfWeek = date.getDay();
        const diff = (dayOfWeek - startOfWeek + 7) % 7;
        
        date.setDate(date.getDate() - diff);
        return date.toISOString().split('T')[0];
    }

    /**
     * Get end of week for a given date
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @param {number} startOfWeek - Day of week to start (0 = Sunday, 1 = Monday)
     * @returns {string} End of week date in YYYY-MM-DD format
     */
    static getEndOfWeek(dateString, startOfWeek = 1) {
        const startOfWeekDate = this.getStartOfWeek(dateString, startOfWeek);
        return this.addDays(startOfWeekDate, 6);
    }

    /**
     * Get start of month for a given date
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @returns {string} Start of month date in YYYY-MM-DD format
     */
    static getStartOfMonth(dateString) {
        const date = new Date(dateString);
        date.setDate(1);
        return date.toISOString().split('T')[0];
    }

    /**
     * Get end of month for a given date
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @returns {string} End of month date in YYYY-MM-DD format
     */
    static getEndOfMonth(dateString) {
        const date = new Date(dateString);
        date.setMonth(date.getMonth() + 1, 0); // Set to last day of current month
        return date.toISOString().split('T')[0];
    }

    /**
     * Compare two dates
     * @param {string} date1 - First date in YYYY-MM-DD format
     * @param {string} date2 - Second date in YYYY-MM-DD format
     * @returns {number} -1 if date1 < date2, 0 if equal, 1 if date1 > date2
     */
    static compareDates(date1, date2) {
        const d1 = new Date(date1);
        const d2 = new Date(date2);
        
        if (d1 < d2) return -1;
        if (d1 > d2) return 1;
        return 0;
    }

    /**
     * Get relative date description
     * @param {string} dateString - Date in YYYY-MM-DD format
     * @returns {string} Relative description (Today, Yesterday, Tomorrow, etc.)
     */
    static getRelativeDate(dateString) {
        const today = this.getTodayString();
        const yesterday = this.addDays(today, -1);
        const tomorrow = this.addDays(today, 1);

        if (dateString === today) return 'Today';
        if (dateString === yesterday) return 'Yesterday';
        if (dateString === tomorrow) return 'Tomorrow';

        const daysDiff = this.calculateDaysBetween(today, dateString);
        
        if (daysDiff > 0 && daysDiff <= 7) {
            return `In ${daysDiff} day${daysDiff > 1 ? 's' : ''}`;
        } else if (daysDiff < 0 && daysDiff >= -7) {
            return `${Math.abs(daysDiff)} day${Math.abs(daysDiff) > 1 ? 's' : ''} ago`;
        }

        return this.formatDate(dateString, { month: 'short', day: 'numeric' });
    }
}

// Export for use in other modules
window.SchedulerDateUtils = DateUtils;
