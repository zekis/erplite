/**
 * Time-related utility functions
 */
class TimeUtils {
    /**
     * Check if two time blocks overlap
     */
    static checkTimeOverlap(dayColumn, startHour, startMinute, duration, excludeBlock = null) {
        const existingBlocks = dayColumn.querySelectorAll('.time-block');
        const newStartTime = startHour + (startMinute || 0) / 60;
        const newEndTime = newStartTime + duration;
        
        for (let block of existingBlocks) {
            if (block === excludeBlock) continue; // Skip the block we're moving
            
            const blockStartHour = parseInt(block.dataset.startHour);
            const blockStartMinute = parseInt(block.dataset.startMinute || 0);
            const blockDuration = parseFloat(block.dataset.duration);
            
            const blockStartTime = blockStartHour + blockStartMinute / 60;
            const blockEndTime = blockStartTime + blockDuration;
            
            // Check for overlap
            if (newStartTime < blockEndTime && newEndTime > blockStartTime) {
                return true; // Overlap detected
            }
        }
        
        return false; // No overlap
    }
    
    /**
     * Format time for display
     */
    static formatTime(hour, minute = 0) {
        return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
    }
    
    /**
     * Parse time string to hour and minute
     */
    static parseTime(timeString) {
        const [hour, minute] = timeString.split(':').map(Number);
        return { hour, minute };
    }
    
    /**
     * Calculate duration between two times
     */
    static calculateDuration(startHour, startMinute, endHour, endMinute) {
        const startTime = startHour + startMinute / 60;
        const endTime = endHour + endMinute / 60;
        return endTime - startTime;
    }
    
    /**
     * Snap time to 30-minute intervals
     */
    static snapToThirtyMinutes(minutes) {
        return Math.round(minutes / 30) * 30;
    }
    
    /**
     * Convert pixels to time offset (30px = 30 minutes)
     */
    static pixelsToMinutes(pixels) {
        return pixels; // 1px = 1 minute in our scale
    }
    
    /**
     * Convert time offset to pixels
     */
    static minutesToPixels(minutes) {
        return minutes; // 1 minute = 1px in our scale
    }
    
    /**
     * Get current time as hour and minute
     */
    static getCurrentTime() {
        const now = new Date();
        return {
            hour: now.getHours(),
            minute: now.getMinutes()
        };
    }
    
    /**
     * Check if time is within working hours (8-18)
     */
    static isWorkingHours(hour) {
        return hour >= 8 && hour < 18;
    }
    
    /**
     * Get day name from date
     */
    static getDayName(date) {
        const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        return dayNames[new Date(date).getDay()];
    }
    
    /**
     * Get month name from date
     */
    static getMonthName(date, short = true) {
        const monthNames = short 
            ? ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            : ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
        return monthNames[new Date(date).getMonth()];
    }
    
    /**
     * Format date for display
     */
    static formatDate(date, format = 'short') {
        const dateObj = new Date(date);
        const dayName = this.getDayName(date);
        const monthName = this.getMonthName(date, true);
        const dayNumber = dateObj.getDate();
        
        switch (format) {
            case 'short':
                return `${monthName} ${dayNumber}`;
            case 'long':
                return `${dayName}, ${monthName} ${dayNumber}`;
            case 'full':
                return `${dayName}, ${this.getMonthName(date, false)} ${dayNumber}, ${dateObj.getFullYear()}`;
            default:
                return `${monthName} ${dayNumber}`;
        }
    }
}

// Export to global scope
window.TimeUtils = TimeUtils;
