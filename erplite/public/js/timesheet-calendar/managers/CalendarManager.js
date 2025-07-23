/**
 * Manages calendar view, hour ranges, and week navigation
 */
class CalendarManager {
    constructor(app) {
        this.app = app;
        this.init();
    }
    
    /**
     * Initialize calendar management
     */
    init() {
        this.setupTimeSlotClicks();
        this.setupHourToggle();
    }
    
    /**
     * Setup click handlers for time slots (quick entry)
     */
    setupTimeSlotClicks() {
        document.querySelectorAll('.time-slot').forEach(timeSlot => {
            timeSlot.addEventListener('click', (e) => {
                // Only show quick entry if the time slot is empty
                if (!timeSlot.querySelector('.time-block')) {
                    this.app.components.quickEntry.show(timeSlot);
                }
            });
        });
    }
    
    /**
     * Setup hour range toggle functionality
     */
    setupHourToggle() {
        const toggle = document.getElementById('hourToggle');
        if (toggle) {
            toggle.addEventListener('change', () => {
                this.toggleHourRange();
            });
        }
    }
    
    /**
     * Toggle between working hours and full day view
     */
    toggleHourRange() {
        this.app.state.isFullDay = !this.app.state.isFullDay;
        
        if (this.app.state.isFullDay) {
            this.rebuildCalendar(0, 24); // Full day: 0-24 hours
        } else {
            this.rebuildCalendar(6, 18); // Working hours: 6am-6pm
        }
        
        // Update toggle state
        const toggle = document.getElementById('hourToggle');
        if (toggle) {
            toggle.checked = this.app.state.isFullDay;
        }
    }
    
    /**
     * Show current time line across calendar
     */
    highlightCurrentTime() {
        // Remove existing time line
        const existingLine = document.querySelector('.current-time-line');
        if (existingLine) {
            existingLine.remove();
        }
        
        const now = new Date();
        const currentHour = now.getHours();
        const currentMinute = now.getMinutes();
        
        // Only show line if within calendar hours
        const startHour = this.app.state.isFullDay ? 0 : 6;
        const endHour = this.app.state.isFullDay ? 24 : 18;
        
        if (currentHour >= startHour && currentHour < endHour) {
            // Calculate exact position based on current time
            const minutesFromStart = (currentHour - startHour) * 60 + currentMinute;
            const pixelsFromTop = minutesFromStart; // 1px per minute
            
            // Create the time line element
            const timeLine = document.createElement('div');
            timeLine.className = 'current-time-line';
            timeLine.style.cssText = `
                position: absolute;
                top: ${pixelsFromTop}px;
                left: 0;
                right: 0;
                height: 2px;
                background: #3b82f6;
                z-index: 100;
                pointer-events: none;
                box-shadow: 0 0 4px rgba(59, 130, 246, 0.5);
            `;
            
            // Add time indicator circle
            const timeIndicator = document.createElement('div');
            timeIndicator.style.cssText = `
                position: absolute;
                left: -6px;
                top: -4px;
                width: 10px;
                height: 10px;
                background: #3b82f6;
                border-radius: 50%;
                border: 2px solid white;
                box-shadow: 0 0 4px rgba(59, 130, 246, 0.5);
            `;
            
            timeLine.appendChild(timeIndicator);
            
            // Add to calendar body
            const calendarBody = document.querySelector('.calendar-body');
            if (calendarBody) {
                calendarBody.appendChild(timeLine);
            }
        }
    }
    
    /**
     * Force full day view (when entries exist outside working hours)
     */
    forceFullDayView() {
        this.app.state.isFullDay = true;
        const toggle = document.getElementById('hourToggle');
        const container = toggle.closest('.hour-toggle-container');
        
        // Update toggle state and disable it
        toggle.checked = true;
        toggle.disabled = true;
        
        // Update container styling for disabled state
        if (container) {
            container.style.opacity = '0.6';
            container.style.cursor = 'not-allowed';
            container.title = 'Full day view is required because there are time entries outside working hours (6 AM - 6 PM)';
        }
        
        // Rebuild calendar to show full day
        this.rebuildCalendar(0, 24); // 0-24 hours
        
        // Show notification to user
        this.app.components.toast.show('Switched to full day view - time entries exist outside working hours', 'info');
    }
    
    /**
     * Rebuild calendar with new hour range
     */
    rebuildCalendar(startHour, endHour) {
        // Store existing time blocks data
        const existingBlocks = [];
        this.app.state.timeBlocks.forEach(block => {
            const dayColumn = block.closest('.day-column');
            if (dayColumn) {
                existingBlocks.push({
                    project: block.dataset.project,
                    activity: block.dataset.activity,
                    projectName: block.querySelector('.time-block-header').textContent,
                    activityName: block.querySelector('.time-block-activity').textContent,
                    color: block.style.getPropertyValue('--project-color'),
                    date: dayColumn.dataset.date,
                    startHour: parseInt(block.dataset.startHour),
                    startMinute: parseInt(block.dataset.startMinute || 0),
                    duration: parseFloat(block.dataset.duration),
                    description: block.dataset.description || '',
                    id: block.dataset.id
                });
            }
        });
        
        // Clear existing calendar
        document.querySelectorAll('.day-column').forEach(dayColumn => {
            // Remove all time slots and time blocks
            dayColumn.querySelectorAll('.time-slot, .time-block').forEach(el => el.remove());
            
            // Rebuild time labels
            const timeLabels = dayColumn.querySelector('.time-labels');
            if (timeLabels) {
                timeLabels.innerHTML = '';
                for (let hour = startHour; hour < endHour; hour++) {
                    const timeLabel = document.createElement('div');
                    timeLabel.className = 'time-label';
                    timeLabel.textContent = `${hour}:00`;
                    timeLabels.appendChild(timeLabel);
                }
            }
            
            // Rebuild time slots with 30-minute granularity
            const daySummary = dayColumn.querySelector('.day-summary');
            let slotIndex = 0; // Track slot index for proper styling
            
            for (let hour = startHour; hour < endHour; hour++) {
                // Create two 30-minute slots per hour
                for (let halfHour = 0; halfHour < 2; halfHour++) {
                    const timeSlot = document.createElement('div');
                    timeSlot.className = 'time-slot';
                    timeSlot.dataset.hour = hour;
                    timeSlot.dataset.minute = halfHour * 30;
                    timeSlot.style.height = '30px';
                    
                    // Apply the same styling logic as the original CSS
                    // Every second slot (even index) gets the thicker border
                    if (slotIndex % 2 === 1) {
                        timeSlot.style.borderBottom = '2px solid #e2e8f0';
                    } else {
                        timeSlot.style.borderBottom = '1px solid #f1f5f9';
                    }
                    
                    // Add event listeners
                    timeSlot.addEventListener('dragover', (e) => this.app.managers.dragDrop.allowDrop(e));
                    timeSlot.addEventListener('dragenter', (e) => this.app.managers.dragDrop.dragEnter(e));
                    timeSlot.addEventListener('dragleave', (e) => this.app.managers.dragDrop.dragLeave(e));
                    timeSlot.addEventListener('drop', (e) => this.app.managers.dragDrop.dropTimeBlock(e));
                    timeSlot.addEventListener('click', (e) => {
                        if (!timeSlot.querySelector('.time-block')) {
                            this.app.components.quickEntry.show(timeSlot);
                        }
                    });
                    
                    dayColumn.insertBefore(timeSlot, daySummary);
                    slotIndex++;
                }
            }
        });
        
        // Clear timeBlocks array
        this.app.state.timeBlocks = [];
        
        // Recreate time blocks that are within the new hour range
        existingBlocks.forEach(blockData => {
            if (blockData.startHour >= startHour && blockData.startHour < endHour) {
                this.app.managers.timeBlock.createTimeBlock(blockData);
            }
        });
        
        this.app.updateDaySummaries();
    }
    
    /**
     * Navigate to different week
     */
    changeWeek(direction) {
        // Ensure we have a valid currentWeekStart
        if (!this.app.state.currentWeekStart) {
            console.error('currentWeekStart not initialized');
            return;
        }
        
        const currentDate = new Date(this.app.state.currentWeekStart);
        currentDate.setDate(currentDate.getDate() + (direction * 7));
        
        const newWeekStart = currentDate.toISOString().split('T')[0];
        
        window.location.href = `/timesheet-calendar?week=${newWeekStart}`;
    }
    
    /**
     * Clear all time entries for the week
     */
    clearWeek() {
        if (!confirm('Clear all time entries for this week?')) {
            return;
        }
        
        this.app.state.timeBlocks.forEach(block => {
            this.app.managers.timeBlock.removeTimeBlockFromDOM(block);
        });
        
        this.app.state.timeBlocks = [];
        this.app.updateDaySummaries();
        
        this.app.components.toast.show('Week cleared successfully!', 'success');
    }
    
    /**
     * Get current week dates
     */
    getWeekDates() {
        const weekDates = [];
        document.querySelectorAll('.day-column').forEach(dayColumn => {
            weekDates.push(dayColumn.dataset.date);
        });
        return weekDates;
    }
    
    /**
     * Get day column by date
     */
    getDayColumn(date) {
        return document.querySelector(`[data-date="${date}"]`);
    }
    
    /**
     * Get all day columns
     */
    getAllDayColumns() {
        return Array.from(document.querySelectorAll('.day-column'));
    }
    
    /**
     * Check if date is today
     */
    isToday(date) {
        const today = new Date().toISOString().split('T')[0];
        return date === today;
    }
    
    /**
     * Check if date is in current week
     */
    isCurrentWeek(date) {
        const weekDates = this.getWeekDates();
        return weekDates.includes(date);
    }
    
    /**
     * Get time slot at specific hour and minute
     */
    getTimeSlot(dayColumn, hour, minute = 0) {
        return dayColumn.querySelector(`[data-hour="${hour}"][data-minute="${minute}"]`);
    }
    
    /**
     * Get all time slots for a day
     */
    getTimeSlots(dayColumn) {
        return Array.from(dayColumn.querySelectorAll('.time-slot'));
    }
    
    /**
     * Scroll to specific time
     */
    scrollToTime(hour, minute = 0) {
        const firstDayColumn = document.querySelector('.day-column');
        if (!firstDayColumn) return;
        
        const timeSlot = this.getTimeSlot(firstDayColumn, hour, minute);
        if (timeSlot) {
            DOMUtils.scrollIntoView(timeSlot, { block: 'center' });
        }
    }
    
    /**
     * Scroll to current time
     */
    scrollToCurrentTime() {
        const now = TimeUtils.getCurrentTime();
        this.scrollToTime(now.hour, now.minute);
    }
    
    
    /**
     * Update current time highlight periodically
     */
    startTimeHighlighting() {
        this.highlightCurrentTime();
        
        // Update every minute
        setInterval(() => {
            this.highlightCurrentTime();
        }, 60000);
    }
}

// Export to global scope
window.CalendarManager = CalendarManager;
