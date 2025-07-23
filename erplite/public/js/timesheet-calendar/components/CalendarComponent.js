/**
 * Calendar component for managing calendar view and interactions
 */
class CalendarComponent {
    constructor(app) {
        this.app = app;
        this.init();
    }
    
    /**
     * Initialize calendar component
     */
    init() {
        this.setupCalendarEvents();
        this.setupHeaderButtons();
    }
    
    /**
     * Setup calendar event listeners
     */
    setupCalendarEvents() {
        // Calendar grid context menu
        const calendarGrid = document.querySelector('.calendar-grid');
        if (calendarGrid) {
            calendarGrid.addEventListener('contextmenu', (e) => {
                // Only show calendar context menu if not clicking on a time block
                if (!e.target.closest('.time-block') && !e.target.closest('.time-slot')) {
                    e.preventDefault();
                    this.app.components.contextMenu.showCalendarMenu(e.pageX, e.pageY);
                }
            });
        }
    }
    
    /**
     * Setup header button event listeners
     */
    setupHeaderButtons() {
        // Week navigation
        const prevWeekBtn = document.querySelector('.week-nav button:first-child');
        const nextWeekBtn = document.querySelector('.week-nav button:last-child');
        
        if (prevWeekBtn) {
            prevWeekBtn.addEventListener('click', () => {
                this.app.managers.calendar.changeWeek(-1);
            });
        }
        
        if (nextWeekBtn) {
            nextWeekBtn.addEventListener('click', () => {
                this.app.managers.calendar.changeWeek(1);
            });
        }
        
        // Calendar action buttons
        const clearWeekBtn = document.querySelector('button[onclick="clearWeek()"]');
        const saveBtn = document.querySelector('button[onclick="saveTimesheet()"]');
        
        if (clearWeekBtn) {
            clearWeekBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.app.managers.calendar.clearWeek();
            });
        }
        
        if (saveBtn) {
            saveBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.app.managers.storage.saveTimesheet();
            });
        }
    }
    
    /**
     * Update calendar display
     */
    updateDisplay() {
        this.updateWeekDisplay();
        this.updateDaySummaries();
        this.highlightToday();
    }
    
    /**
     * Update week display in header
     */
    updateWeekDisplay() {
        const weekDisplay = document.querySelector('.current-week');
        if (weekDisplay && this.app.state.currentWeekStart) {
            const startDate = new Date(this.app.state.currentWeekStart);
            const endDate = new Date(startDate);
            endDate.setDate(endDate.getDate() + 6);
            
            const startFormatted = TimeUtils.formatDate(startDate.toISOString().split('T')[0]);
            const endFormatted = TimeUtils.formatDate(endDate.toISOString().split('T')[0], 'full');
            
            weekDisplay.textContent = `${startFormatted} - ${endFormatted}`;
        }
    }
    
    /**
     * Update day summaries
     */
    updateDaySummaries() {
        this.app.updateDaySummaries();
    }
    
    /**
     * Highlight today's column
     */
    highlightToday() {
        // Remove existing today highlights
        document.querySelectorAll('.day-column.today').forEach(column => {
            column.classList.remove('today');
        });
        
        // Add today highlight
        const today = new Date().toISOString().split('T')[0];
        const todayColumn = document.querySelector(`[data-date="${today}"]`);
        if (todayColumn) {
            todayColumn.classList.add('today');
        }
    }
    
    /**
     * Scroll to current time
     */
    scrollToCurrentTime() {
        this.app.managers.calendar.scrollToCurrentTime();
    }
    
    /**
     * Get calendar statistics
     */
    getCalendarStats() {
        const stats = {
            totalTimeBlocks: this.app.state.timeBlocks.length,
            totalHours: 0,
            daysWithEntries: new Set(),
            projectsUsed: new Set(),
            activitiesUsed: new Set(),
            averageBlockDuration: 0,
            longestBlock: 0,
            shortestBlock: Infinity
        };
        
        this.app.state.timeBlocks.forEach(block => {
            const data = this.app.components.timeBlock.getTimeBlockData(block);
            const duration = parseFloat(data.duration);
            
            stats.totalHours += duration;
            stats.daysWithEntries.add(data.date);
            stats.projectsUsed.add(data.project);
            stats.activitiesUsed.add(data.activity);
            
            stats.longestBlock = Math.max(stats.longestBlock, duration);
            stats.shortestBlock = Math.min(stats.shortestBlock, duration);
        });
        
        // Calculate averages
        if (stats.totalTimeBlocks > 0) {
            stats.averageBlockDuration = Math.round(stats.totalHours / stats.totalTimeBlocks * 10) / 10;
        }
        
        if (stats.shortestBlock === Infinity) {
            stats.shortestBlock = 0;
        }
        
        // Convert sets to counts
        stats.daysWithEntries = stats.daysWithEntries.size;
        stats.projectsUsed = stats.projectsUsed.size;
        stats.activitiesUsed = stats.activitiesUsed.size;
        
        // Round total hours
        stats.totalHours = Math.round(stats.totalHours * 10) / 10;
        
        return stats;
    }
    
    /**
     * Export calendar view as image
     */
    exportAsImage() {
        const calendarGrid = document.querySelector('.calendar-grid');
        if (!calendarGrid) {
            this.app.components.toast.error('Calendar not found');
            return;
        }
        
        // Use html2canvas if available, otherwise show message
        if (typeof html2canvas !== 'undefined') {
            html2canvas(calendarGrid, {
                backgroundColor: '#ffffff',
                scale: 2,
                useCORS: true
            }).then(canvas => {
                // Create download link
                const link = document.createElement('a');
                link.download = `timesheet-${this.app.state.currentWeekStart}.png`;
                link.href = canvas.toDataURL();
                link.click();
                
                this.app.components.toast.success('Calendar exported as image');
            }).catch(error => {
                console.error('Export failed:', error);
                this.app.components.toast.error('Failed to export calendar as image');
            });
        } else {
            this.app.components.toast.info('Image export requires html2canvas library');
        }
    }
    
    /**
     * Print calendar
     */
    printCalendar() {
        // Create print-friendly version
        const printWindow = window.open('', '_blank');
        const calendarHTML = this.generatePrintHTML();
        
        printWindow.document.write(calendarHTML);
        printWindow.document.close();
        
        // Wait for content to load then print
        printWindow.onload = () => {
            printWindow.print();
            printWindow.close();
        };
    }
    
    /**
     * Generate HTML for printing
     */
    generatePrintHTML() {
        const weekStart = new Date(this.app.state.currentWeekStart);
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 6);
        
        const stats = this.getCalendarStats();
        
        let html = `
            <!DOCTYPE html>
            <html>
            <head>
                <title>Timesheet - ${TimeUtils.formatDate(weekStart.toISOString().split('T')[0])} to ${TimeUtils.formatDate(weekEnd.toISOString().split('T')[0])}</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .header { text-align: center; margin-bottom: 20px; }
                    .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
                    .stat { padding: 10px; background: #f5f5f5; border-radius: 5px; text-align: center; }
                    .calendar { width: 100%; border-collapse: collapse; }
                    .calendar th, .calendar td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }
                    .calendar th { background: #f5f5f5; font-weight: bold; }
                    .time-entry { background: #e3f2fd; margin: 2px 0; padding: 4px; border-radius: 3px; font-size: 12px; }
                    .project-name { font-weight: bold; }
                    .activity-name { color: #666; }
                    .duration { float: right; font-weight: bold; }
                    @media print { body { margin: 0; } }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Weekly Timesheet</h1>
                    <h2>${TimeUtils.formatDate(weekStart.toISOString().split('T')[0], 'full')} - ${TimeUtils.formatDate(weekEnd.toISOString().split('T')[0], 'full')}</h2>
                </div>
                
                <div class="stats">
                    <div class="stat">
                        <strong>Total Hours</strong><br>
                        ${stats.totalHours}h
                    </div>
                    <div class="stat">
                        <strong>Total Entries</strong><br>
                        ${stats.totalTimeBlocks}
                    </div>
                    <div class="stat">
                        <strong>Projects Used</strong><br>
                        ${stats.projectsUsed}
                    </div>
                </div>
                
                <table class="calendar">
                    <thead>
                        <tr>
                            <th>Time</th>
        `;
        
        // Add day headers
        for (let i = 0; i < 7; i++) {
            const date = new Date(weekStart);
            date.setDate(date.getDate() + i);
            const dayName = TimeUtils.getDayName(date.toISOString().split('T')[0]);
            const dayDate = TimeUtils.formatDate(date.toISOString().split('T')[0]);
            html += `<th>${dayName}<br><small>${dayDate}</small></th>`;
        }
        
        html += `
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        // Add time rows
        const startHour = this.app.state.isFullDay ? 0 : 8;
        const endHour = this.app.state.isFullDay ? 24 : 18;
        
        for (let hour = startHour; hour < endHour; hour++) {
            html += `<tr><td>${TimeUtils.formatTime(hour, 0)}</td>`;
            
            // Add day columns
            for (let i = 0; i < 7; i++) {
                const date = new Date(weekStart);
                date.setDate(date.getDate() + i);
                const dateStr = date.toISOString().split('T')[0];
                
                html += '<td>';
                
                // Find time blocks for this hour and day
                const dayBlocks = this.app.state.timeBlocks.filter(block => {
                    const data = this.app.components.timeBlock.getTimeBlockData(block);
                    return data.date === dateStr && 
                           data.startHour <= hour && 
                           (data.startHour + data.duration) > hour;
                });
                
                dayBlocks.forEach(block => {
                    const data = this.app.components.timeBlock.getTimeBlockData(block);
                    if (data.startHour === hour) { // Only show at start hour
                        html += `
                            <div class="time-entry">
                                <div class="project-name">${data.projectName}</div>
                                <div class="activity-name">${data.activityName}</div>
                                <div class="duration">${data.duration}h</div>
                            </div>
                        `;
                    }
                });
                
                html += '</td>';
            }
            
            html += '</tr>';
        }
        
        html += `
                    </tbody>
                </table>
            </body>
            </html>
        `;
        
        return html;
    }
    
    /**
     * Show calendar help
     */
    showHelp() {
        const helpContent = `
            <div style="padding: 1rem; max-height: 400px; overflow-y: auto;">
                <h4 style="margin: 0 0 1rem 0;">Keyboard Shortcuts</h4>
                <div style="display: grid; gap: 0.5rem; margin-bottom: 1.5rem;">
                    <div><kbd>Ctrl+S</kbd> - Save timesheet</div>
                    <div><kbd>Ctrl+1-4</kbd> - Quick add 1-4 hour entry</div>
                    <div><kbd>Delete</kbd> - Delete selected entry</div>
                    <div><kbd>Escape</kbd> - Clear selection</div>
                    <div><kbd>Double-click</kbd> - Edit time entry</div>
                </div>
                
                <h4 style="margin: 0 0 1rem 0;">Mouse Actions</h4>
                <div style="display: grid; gap: 0.5rem; margin-bottom: 1.5rem;">
                    <div><strong>Left-click drag</strong> - Move time entry</div>
                    <div><strong>Right-click drag</strong> - Duplicate time entry</div>
                    <div><strong>Click time slot</strong> - Quick entry popup</div>
                    <div><strong>Right-click entry</strong> - Context menu</div>
                    <div><strong>Drag resize handles</strong> - Resize entry</div>
                </div>
                
                <h4 style="margin: 0 0 1rem 0;">Mobile Gestures</h4>
                <div style="display: grid; gap: 0.5rem;">
                    <div><strong>Swipe left/right</strong> - Navigate days</div>
                    <div><strong>Tap time slot</strong> - Quick entry</div>
                    <div><strong>Long press entry</strong> - Context menu</div>
                </div>
            </div>
        `;
        
        this.app.components.modal.showCustomModal('Calendar Help', helpContent, [
            {
                text: 'Close',
                class: 'btn-secondary',
                handler: () => this.app.components.modal.hideCustomModal()
            }
        ]);
    }
    
    /**
     * Toggle calendar view mode
     */
    toggleViewMode() {
        this.app.managers.calendar.toggleHourRange();
    }
    
    /**
     * Refresh calendar data
     */
    refresh() {
        window.location.reload();
    }
    
    /**
     * Get calendar element
     */
    getCalendarElement() {
        return document.querySelector('.calendar-grid');
    }
    
    /**
     * Get day columns
     */
    getDayColumns() {
        return document.querySelectorAll('.day-column');
    }
    
    /**
     * Get time slots
     */
    getTimeSlots() {
        return document.querySelectorAll('.time-slot');
    }
    
    /**
     * Add custom CSS for enhanced calendar features
     */
    addCustomStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .day-column.today {
                background-color: rgba(59, 130, 246, 0.05);
            }
            
            
            .time-block.project-highlighted {
                animation: highlight-pulse 2s ease-in-out;
            }
            
            @keyframes highlight-pulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.05); box-shadow: 0 0 20px rgba(59, 130, 246, 0.5); }
            }
            
            .time-block.highlight-success {
                animation: highlight-success 1s ease-in-out;
            }
            
            @keyframes highlight-success {
                0%, 100% { background-color: inherit; }
                50% { background-color: rgba(16, 185, 129, 0.3); }
            }
            
            .highlighted {
                outline: 2px solid #3b82f6;
                outline-offset: 2px;
            }
        `;
        
        document.head.appendChild(style);
    }
}

// Export to global scope
window.CalendarComponent = CalendarComponent;

// Setup global functions for HTML compatibility
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
