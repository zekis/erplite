/**
 * Time Block Manager
 * Handles rendering, resizing, and interaction with time block cards
 */
class TimeBlockManager {
    constructor(app) {
        this.app = app;
        this.resizeState = null;
        this.boundHandleResize = null;
        this.boundEndResize = null;
    }

    /**
     * Render time block cards for all schedule rows
     */
    renderTimeBlockCards() {
        // Remove existing time block cards
        document.querySelectorAll('.time-block-card').forEach(card => card.remove());
        
        this.app.state.scheduleRows.forEach((row, rowIndex) => {
            if (row.type !== 'activity-row' || !row.dailyEntries) return;
            
            // Parse entries
            let entries = {};
            try {
                if (typeof row.dailyEntries === 'string') {
                    entries = JSON.parse(row.dailyEntries);
                } else {
                    entries = row.dailyEntries;
                }
            } catch (e) {
                console.warn('Failed to parse entries for row:', rowIndex);
                return;
            }
            
            // Check if it's optimized format or simple daily entries
            if (entries.blocks || entries.individual_days) {
                // Handle optimized format
                if (entries.blocks) {
                    entries.blocks.forEach(block => {
                        this.renderTimeBlockCard(rowIndex, block, 'block', row);
                    });
                }
                
                if (entries.individual_days) {
                    Object.keys(entries.individual_days).forEach(date => {
                        const entry = entries.individual_days[date];
                        this.renderTimeBlockCard(rowIndex, {
                            start_date: date,
                            end_date: date,
                            ...entry
                        }, 'individual', row);
                    });
                }
            } else {
                // Handle simple daily entries format (from templates)
                const sortedDates = Object.keys(entries).sort();
                
                if (sortedDates.length === 0) return;
                
                // Group consecutive dates with identical entries into blocks
                const blocks = this.groupConsecutiveEntries(entries);
                
                blocks.forEach(block => {
                    this.renderTimeBlockCard(rowIndex, block, block.start_date === block.end_date ? 'individual' : 'block', row);
                });
            }
        });
    }

    /**
     * Render a single time block card
     */
    renderTimeBlockCard(rowIndex, blockData, type, row) {
        const startDate = blockData.start_date;
        const endDate = blockData.end_date;
        
        // Find the row element
        const rowElement = document.querySelector(`[data-row-index="${rowIndex}"]`);
        if (!rowElement) return;
        
        const daysContainer = rowElement.querySelector('.schedule-days');
        if (!daysContainer) return;
        
        // Calculate position and width
        const startCell = daysContainer.querySelector(`[data-date="${startDate}"]`);
        const endCell = daysContainer.querySelector(`[data-date="${endDate}"]`);
        
        if (!startCell || !endCell) return;
        
        // Create the time block card
        const card = document.createElement('div');
        card.className = 'time-block-card';
        card.dataset.rowIndex = rowIndex;
        card.dataset.startDate = startDate;
        card.dataset.endDate = endDate;
        card.dataset.type = type;
        
        // Set project color
        const projectColor = this.app.state.projectColors[row.project] || '#3b82f6';
        card.style.setProperty('--project-color', projectColor);
        card.style.background = projectColor;
        card.style.borderColor = projectColor;
        
        // Calculate position
        const startRect = startCell.getBoundingClientRect();
        const endRect = endCell.getBoundingClientRect();
        const containerRect = daysContainer.getBoundingClientRect();
        
        const left = startRect.left - containerRect.left;
        const width = endRect.right - startRect.left;
        
        card.style.left = `${left}px`;
        card.style.width = `${width}px`;
        
        // Add styling based on span
        if (startDate === endDate) {
            card.classList.add('single-day');
        } else {
            card.classList.add('start-day');
            // We'll handle middle and end styling if needed
        }
        
        // Create card content
        const content = document.createElement('div');
        content.className = 'card-content';
        
        const hours = blockData.hours || 8;
        const startTime = blockData.start_time || '09:00';
        const endTime = blockData.end_time || '17:00';
        
        if (type === 'block') {
            const daysCount = SchedulerUtils.calculateDaysBetween(startDate, endDate) + 1;
            content.innerHTML = `
                <div class="card-hours">${hours}h × ${daysCount}</div>
                <div class="card-time">${startTime}-${endTime}</div>
                ${row.resourceName ? `<div class="card-resource">${row.resourceName}</div>` : ''}
            `;
        } else {
            content.innerHTML = `
                <div class="card-hours">${hours}h</div>
                <div class="card-time">${startTime}-${endTime}</div>
                ${row.resourceName ? `<div class="card-resource">${row.resourceName}</div>` : ''}
            `;
        }
        
        card.appendChild(content);
        
        // Add resize handles
        const leftHandle = document.createElement('div');
        leftHandle.className = 'resize-handle left';
        leftHandle.addEventListener('mousedown', (e) => this.startResize(e, card, 'left', rowIndex, blockData));
        
        const rightHandle = document.createElement('div');
        rightHandle.className = 'resize-handle right';
        rightHandle.addEventListener('mousedown', (e) => this.startResize(e, card, 'right', rowIndex, blockData));
        
        card.appendChild(leftHandle);
        card.appendChild(rightHandle);
        
        // Add click handler (only on content area, not handles)
        content.addEventListener('click', (e) => {
            e.stopPropagation();
            this.editTimeBlock(rowIndex, blockData, type);
        });
        
        // Position the card
        daysContainer.style.position = 'relative';
        daysContainer.appendChild(card);
    }

    /**
     * Edit a time block
     */
    editTimeBlock(rowIndex, blockData, type) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        if (type === 'block') {
            const daysCount = SchedulerUtils.calculateDaysBetween(blockData.start_date, blockData.end_date) + 1;
            const newHours = prompt(`Edit hours for ${daysCount}-day block (${blockData.start_date} to ${blockData.end_date}):`, blockData.hours);
            
            if (newHours !== null && !isNaN(newHours) && newHours > 0) {
                this.updateTimeBlock(rowIndex, blockData, { hours: parseFloat(newHours) });
            }
        } else {
            const newHours = prompt(`Edit hours for ${blockData.start_date}:`, blockData.hours);
            
            if (newHours !== null && !isNaN(newHours) && newHours > 0) {
                this.updateTimeBlock(rowIndex, blockData, { hours: parseFloat(newHours) });
            }
        }
    }

    /**
     * Update a time block
     */
    async updateTimeBlock(rowIndex, blockData, updates) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        if (!row.scheduleRowId) {
            this.app.showToast('Schedule row not found', 'error');
            return;
        }
        
        try {
            // Get current entries in daily format for editing
            const response = await this.app.apiCall('erplite.scheduler.api.get_schedule_row_expanded', {
                schedule_row: row.scheduleRowId
            });
            
            if (response && response.success) {
                const dailyEntries = response.daily_entries;
                
                // Update the affected dates
                const startDate = new Date(blockData.start_date);
                const endDate = new Date(blockData.end_date);
                const currentDate = new Date(startDate);
                
                while (currentDate <= endDate) {
                    const dateStr = currentDate.toISOString().split('T')[0];
                    if (dailyEntries[dateStr]) {
                        Object.assign(dailyEntries[dateStr], updates);
                    }
                    currentDate.setDate(currentDate.getDate() + 1);
                }
                
                // Save the updated entries
                const updateResponse = await this.app.apiCall('erplite.scheduler.api.update_schedule_row_entries', {
                    schedule_row: row.scheduleRowId,
                    entries_json: JSON.stringify(dailyEntries)
                });
                
                if (updateResponse && updateResponse.success) {
                    // Update local state with optimized entries
                    row.dailyEntries = updateResponse.optimized_entries;
                    
                    this.app.showToast('Time block updated successfully!', 'success');
                    this.renderTimeBlockCards(); // Re-render cards
                } else {
                    this.app.showToast('Failed to update time block', 'error');
                }
            }
            
        } catch (error) {
            console.error('Error updating time block:', error);
            this.app.showToast('Error updating time block: ' + error.message, 'error');
        }
    }

    /**
     * Start resizing a time block card
     */
    startResize(event, card, direction, rowIndex, blockData) {
        event.preventDefault();
        event.stopPropagation();
        
        // Store resize state
        this.resizeState = {
            active: true,
            card: card,
            direction: direction,
            rowIndex: rowIndex,
            blockData: blockData,
            originalStartDate: blockData.start_date,
            originalEndDate: blockData.end_date,
            startX: event.clientX
        };
        
        // Add resizing class
        card.classList.add('resizing');
        
        // Bind event handlers
        this.boundHandleResize = this.handleResize.bind(this);
        this.boundEndResize = this.endResize.bind(this);
        
        document.addEventListener('mousemove', this.boundHandleResize);
        document.addEventListener('mouseup', this.boundEndResize);
        
        // Prevent text selection
        document.body.style.userSelect = 'none';
        
        console.log(`Started resizing ${direction} for block:`, blockData);
    }

    /**
     * Handle resize movement
     */
    handleResize(event) {
        if (!this.resizeState || !this.resizeState.active) return;
        
        const { card, direction, rowIndex } = this.resizeState;
        const row = this.app.state.scheduleRows[rowIndex];
        
        // Find the row element and days container
        const rowElement = document.querySelector(`[data-row-index="${rowIndex}"]`);
        if (!rowElement) return;
        
        const daysContainer = rowElement.querySelector('.schedule-days');
        if (!daysContainer) return;
        
        // Find the day cell under the mouse
        const elementUnderMouse = document.elementFromPoint(event.clientX, event.clientY);
        const targetCell = elementUnderMouse ? elementUnderMouse.closest('.day-cell') : null;
        
        if (!targetCell || !targetCell.dataset.date) return;
        
        const targetDate = targetCell.dataset.date;
        
        // Clear previous resize targets
        document.querySelectorAll('.day-cell.resize-target').forEach(cell => {
            cell.classList.remove('resize-target');
        });
        
        // Calculate new date range based on resize direction
        let newStartDate, newEndDate;
        
        if (direction === 'left') {
            // Resizing from the left - change start date
            newStartDate = targetDate;
            newEndDate = this.resizeState.originalEndDate;
            
            // Ensure start is not after end
            if (new Date(newStartDate) > new Date(newEndDate)) {
                newStartDate = newEndDate;
            }
        } else {
            // Resizing from the right - change end date
            newStartDate = this.resizeState.originalStartDate;
            newEndDate = targetDate;
            
            // Ensure end is not before start
            if (new Date(newEndDate) < new Date(newStartDate)) {
                newEndDate = newStartDate;
            }
        }
        
        // Highlight the new range
        this.highlightDateRange(rowIndex, newStartDate, newEndDate);
        
        // Update the card visually
        this.updateCardVisualDuringResize(card, daysContainer, newStartDate, newEndDate);
        
        // Store the new dates for when resize ends
        this.resizeState.newStartDate = newStartDate;
        this.resizeState.newEndDate = newEndDate;
    }

    /**
     * End resize operation
     */
    endResize(event) {
        if (!this.resizeState || !this.resizeState.active) return;
        
        const { card, rowIndex, blockData, newStartDate, newEndDate } = this.resizeState;
        
        // Clean up event listeners
        document.removeEventListener('mousemove', this.boundHandleResize);
        document.removeEventListener('mouseup', this.boundEndResize);
        
        // Restore text selection
        document.body.style.userSelect = '';
        
        // Remove resizing class
        card.classList.remove('resizing');
        
        // Clear resize targets
        document.querySelectorAll('.day-cell.resize-target').forEach(cell => {
            cell.classList.remove('resize-target');
        });
        
        // Apply the resize if dates changed
        if (newStartDate && newEndDate && 
            (newStartDate !== blockData.start_date || newEndDate !== blockData.end_date)) {
            
            this.applyResize(rowIndex, blockData, newStartDate, newEndDate);
        }
        
        // Reset resize state
        this.resizeState = null;
        
        console.log('Resize ended');
    }

    /**
     * Highlight date range during resize
     */
    highlightDateRange(rowIndex, startDate, endDate) {
        // Clear previous highlights
        document.querySelectorAll('.day-cell.resize-target').forEach(cell => {
            cell.classList.remove('resize-target');
        });
        
        // Highlight the new range
        const start = new Date(startDate);
        const end = new Date(endDate);
        const currentDate = new Date(start);
        
        while (currentDate <= end) {
            const dateStr = currentDate.toISOString().split('T')[0];
            const cell = document.querySelector(`[data-date="${dateStr}"][data-row-index="${rowIndex}"]`);
            if (cell) {
                cell.classList.add('resize-target');
            }
            currentDate.setDate(currentDate.getDate() + 1);
        }
    }

    /**
     * Update card visual appearance during resize
     */
    updateCardVisualDuringResize(card, daysContainer, startDate, endDate) {
        const startCell = daysContainer.querySelector(`[data-date="${startDate}"]`);
        const endCell = daysContainer.querySelector(`[data-date="${endDate}"]`);
        
        if (!startCell || !endCell) return;
        
        // Calculate new position and width
        const startRect = startCell.getBoundingClientRect();
        const endRect = endCell.getBoundingClientRect();
        const containerRect = daysContainer.getBoundingClientRect();
        
        const left = startRect.left - containerRect.left;
        const width = endRect.right - startRect.left;
        
        // Update card position and width
        card.style.left = `${left}px`;
        card.style.width = `${width}px`;
        
        // Update content to show new day count
        const content = card.querySelector('.card-content');
        if (content) {
            const daysCount = SchedulerUtils.calculateDaysBetween(startDate, endDate) + 1;
            const hours = this.resizeState.blockData.hours || 8;
            const startTime = this.resizeState.blockData.start_time || '09:00';
            const endTime = this.resizeState.blockData.end_time || '17:00';
            
            if (daysCount > 1) {
                content.innerHTML = `
                    <div class="card-hours">${hours}h × ${daysCount}</div>
                    <div class="card-time">${startTime}-${endTime}</div>
                `;
            } else {
                content.innerHTML = `
                    <div class="card-hours">${hours}h</div>
                    <div class="card-time">${startTime}-${endTime}</div>
                `;
            }
        }
    }

    /**
     * Apply the resize to the data model
     */
    applyResize(rowIndex, originalBlockData, newStartDate, newEndDate) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        if (!row.dailyEntries) {
            row.dailyEntries = {};
        }
        
        // Remove entries from the original date range
        const originalStart = new Date(originalBlockData.start_date);
        const originalEnd = new Date(originalBlockData.end_date);
        const currentDate = new Date(originalStart);
        
        while (currentDate <= originalEnd) {
            const dateStr = currentDate.toISOString().split('T')[0];
            delete row.dailyEntries[dateStr];
            currentDate.setDate(currentDate.getDate() + 1);
        }
        
        // Add entries for the new date range
        const newStart = new Date(newStartDate);
        const newEnd = new Date(newEndDate);
        const newCurrentDate = new Date(newStart);
        
        while (newCurrentDate <= newEnd) {
            const dateStr = newCurrentDate.toISOString().split('T')[0];
            row.dailyEntries[dateStr] = {
                hours: originalBlockData.hours || 8,
                start_time: originalBlockData.start_time || '09:00',
                end_time: originalBlockData.end_time || '17:00',
                description: originalBlockData.description || '',
                status: originalBlockData.status || 'planned',
                id: SchedulerUtils.generateUniqueId()
            };
            newCurrentDate.setDate(newCurrentDate.getDate() + 1);
        }
        
        // Re-render to show the changes
        this.app.renderScheduleRows();
        this.renderTimeBlockCards();
        
        const daysCount = SchedulerUtils.calculateDaysBetween(newStartDate, newEndDate) + 1;
        this.app.showToast(`Time block resized to ${daysCount} day${daysCount > 1 ? 's' : ''}!`, 'success');
    }

    /**
     * Group consecutive entries - delegates to SchedulerUtils
     */
    groupConsecutiveEntries(entries) {
        return SchedulerUtils.groupConsecutiveEntries(entries);
    }

    /**
     * Check if entries can be grouped - delegates to SchedulerUtils
     */
    canEntriesBeGrouped(block, entry) {
        return SchedulerUtils.canEntriesBeGrouped(block, entry);
    }

    /**
     * Add time entries for multiple dates
     */
    async addMultipleTimeEntries(rowIndex, dates) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        if (!row.scheduleRowId) {
            this.app.showToast('Schedule row not created yet', 'error');
            return;
        }
        
        try {
            // Create time entries for all dates
            if (!row.dailyEntries) {
                row.dailyEntries = {};
            }
            
            dates.forEach(date => {
                row.dailyEntries[date] = {
                    hours: 8,
                    start_time: "09:00",
                    end_time: "17:00",
                    description: "",
                    status: "planned"
                };
            });
            
            // Update the Schedule Row in database
            const response = await this.app.apiCall('erplite.scheduler.api.update_schedule_row_entries', {
                schedule_row: row.scheduleRowId,
                entries_json: JSON.stringify(row.dailyEntries)
            });
            
            if (response && response.success) {
                this.app.showToast(`Time entries added for ${dates.length} days!`, 'success');
                this.app.renderScheduleRows();
            } else {
                this.app.showToast('Failed to add time entries', 'error');
            }
            
        } catch (error) {
            console.error('Error adding time entries:', error);
            this.app.showToast('Error adding time entries: ' + error.message, 'error');
        }
    }

    /**
     * Add a single time entry (8 hours, 9-5)
     */
    async addSingleTimeEntry(rowIndex, date) {
        const row = this.app.state.scheduleRows[rowIndex];
        
        if (!row.scheduleRowId) {
            this.app.showToast('Schedule row not created yet', 'error');
            return;
        }
        
        try {
            // Create time entry in Schedule Row
            const timeEntry = {
                hours: 8,
                start_time: "09:00",
                end_time: "17:00",
                description: "",
                status: "planned"
            };
            
            // Update the row's daily entries
            if (!row.dailyEntries) {
                row.dailyEntries = {};
            }
            row.dailyEntries[date] = timeEntry;
            
            // Update the Schedule Row in database
            const response = await this.app.apiCall('erplite.scheduler.api.update_schedule_row_entries', {
                schedule_row: row.scheduleRowId,
                entries_json: JSON.stringify(row.dailyEntries)
            });
            
            if (response && response.success) {
                this.app.showToast('Time entry added successfully!', 'success');
                this.app.renderScheduleRows();
            } else {
                this.app.showToast('Failed to add time entry', 'error');
            }
            
        } catch (error) {
            console.error('Error adding time entry:', error);
            this.app.showToast('Error adding time entry: ' + error.message, 'error');
        }
    }

    /**
     * Update a time entry
     */
    async updateTimeEntry(scheduleRowId, date, hours) {
        try {
            // Find the row
            const row = this.app.state.scheduleRows.find(r => r.scheduleRowId === scheduleRowId);
            if (!row) return;
            
            // Update the entry
            if (!row.dailyEntries) {
                row.dailyEntries = {};
            }
            
            row.dailyEntries[date] = {
                hours: hours,
                start_time: "09:00",
                end_time: "17:00",
                description: "",
                status: "planned"
            };
            
            // Update in database
            const response = await this.app.apiCall('erplite.scheduler.api.update_schedule_row_entries', {
                schedule_row: scheduleRowId,
                entries_json: JSON.stringify(row.dailyEntries)
            });
            
            if (response && response.success) {
                this.app.showToast('Time entry updated successfully!', 'success');
                this.app.renderScheduleRows();
            } else {
                this.app.showToast('Failed to update time entry', 'error');
            }
            
        } catch (error) {
            console.error('Error updating time entry:', error);
            this.app.showToast('Error updating time entry: ' + error.message, 'error');
        }
    }

    /**
     * Edit a time entry
     */
    editTimeEntry(scheduleRowId, date, entry) {
        // For now, just show a simple prompt - can be enhanced with a modal later
        const hours = typeof entry === 'object' ? entry.hours : entry;
        const newHours = prompt(`Edit hours for ${date}:`, hours);
        
        if (newHours !== null && !isNaN(newHours) && newHours > 0) {
            this.updateTimeEntry(scheduleRowId, date, parseFloat(newHours));
        }
    }

    /**
     * Cleanup method
     */
    cleanup() {
        // Clean up any active resize operations
        if (this.resizeState && this.resizeState.active) {
            document.removeEventListener('mousemove', this.boundHandleResize);
            document.removeEventListener('mouseup', this.boundEndResize);
            document.body.style.userSelect = '';
            this.resizeState = null;
        }
        
        // Remove all time block cards
        document.querySelectorAll('.time-block-card').forEach(card => card.remove());
        
        console.log('TimeBlockManager cleanup completed');
    }
}

// Export to global scope for HTML compatibility
window.TimeBlockManager = TimeBlockManager;
