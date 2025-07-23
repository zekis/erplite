/**
 * Manages time block creation, editing, and lifecycle
 */
class TimeBlockManager {
    constructor(app) {
        this.app = app;
        this.dragStartTime = 0;
        this.lastClickTime = 0;
        this.lastClickedBlock = null;
    }
    
    /**
     * Create a new time block
     */
    createTimeBlock(data) {
        const dayColumn = document.querySelector(`[data-date="${data.date}"]`);
        if (!dayColumn) return null;
        
        const template = document.getElementById('time-block-template');
        const timeBlock = template.content.cloneNode(true).querySelector('.time-block');
        
        // Set content
        timeBlock.querySelector('.time-block-header').textContent = data.projectName;
        timeBlock.querySelector('.time-block-activity').textContent = data.activityName;
        timeBlock.querySelector('.time-block-duration').textContent = `${data.duration}h`;
        
        // Show description if duration is 1.5+ hours and description exists
        const descriptionElement = timeBlock.querySelector('.time-block-description');
        if (data.duration >= 1.5 && data.description && data.description.trim()) {
            descriptionElement.textContent = data.description;
            descriptionElement.style.display = 'block';
        } else {
            descriptionElement.style.display = 'none';
        }
        
        // Hide activityvity name for very shactivityactivities (0.5h) and duration for activityvitys under 1.5h
        const durationElement = timeBlock.querySelector('.time-block-duration');
        const activityElement = timeBlock.querySelector('.time-block-activity');
        
        // Activity name visibility (hide for 0.5h activities)
        if (data.duration <= 0.5) {
            activityElement.style.display = 'none';
        } else {
            activityElement.style.display = 'block';
        }
        
        // Duration visibility (only show for activities > 0.5h)
        if (data.duration > 0.5) {
            durationElement.style.display = 'block';
        } else {
            durationElement.style.display = 'none';
        }
        
        // Set style - adjust for current hour range
        const startHour = this.app.state.isFullDay ? 0 : 8;
        timeBlock.style.setProperty('--project-color', data.color);
        timeBlock.style.top = `${(data.startHour - startHour) * 60 + (data.startMinute || 0)}px`;
        timeBlock.style.height = `${data.duration * 60}px`;
        
        // Add data attributes
        timeBlock.dataset.project = data.project;
        timeBlock.dataset.activity = data.activity;
        timeBlock.dataset.duration = data.duration;
        timeBlock.dataset.startHour = data.startHour;
        timeBlock.dataset.startMinute = data.startMinute || 0;
        timeBlock.dataset.description = data.description || '';
        if (data.id) timeBlock.dataset.id = data.id;
        
        // Add event listeners
        this.setupTimeBlockEvents(timeBlock);
        
        dayColumn.appendChild(timeBlock);
        this.app.state.timeBlocks.push(timeBlock);
        
        return timeBlock;
    }
    
    /**
     * Setup event listeners for a time block
     */
    setupTimeBlockEvents(timeBlock) {
        // Click handling for selection and double-click editing
        timeBlock.addEventListener('click', (e) => this.handleTimeBlockClick(e, timeBlock));
        
        // Make time block draggable
        this.app.managers.dragDrop.setupTimeBlockDragging(timeBlock);
        
        // Setup resize handles
        this.setupResizeHandles(timeBlock);
    }
    
    /**
     * Handle time block click events
     */
    handleTimeBlockClick(event, timeBlock) {
        event.stopPropagation();
        
        // Check if this was a drag operation
        if (this.app.managers.dragDrop.isDragging) {
            this.app.managers.dragDrop.isDragging = false;
            return;
        }
        
        const clickTime = Date.now();
        
        // Check for double-click (within 400ms of previous click on same block)
        if (this.lastClickedBlock === timeBlock && clickTime - this.lastClickTime < 400) {
            // Double-click detected - open edit modal
            this.app.components.modal.openEditModal(timeBlock);
            
            // Reset double-click tracking
            this.lastClickTime = 0;
            this.lastClickedBlock = null;
            return;
        }
        
        // Single click - handle selection if it's a quick click (not a drag)
        if (clickTime - this.dragStartTime < 200) {
            this.app.selectTimeBlock(timeBlock);
            
            // Track for potential double-click
            this.lastClickTime = clickTime;
            this.lastClickedBlock = timeBlock;
            return;
        }
        
        // Reset double-click tracking for long clicks
        this.lastClickTime = 0;
        this.lastClickedBlock = null;
    }
    
    /**
     * Setup resize handles for a time block
     */
    setupResizeHandles(timeBlock) {
        const topHandle = timeBlock.querySelector('.resize-handle.top');
        const bottomHandle = timeBlock.querySelector('.resize-handle.bottom');
        
        let isResizing = false;
        let startY = 0;
        let startHeight = 0;
        let startTop = 0;
        let activeHandle = null;
        
        const startResize = (e, handle) => {
            isResizing = true;
            activeHandle = handle;
            startY = e.clientY;
            startHeight = timeBlock.offsetHeight;
            startTop = timeBlock.offsetTop;
            
            document.addEventListener('mousemove', resize);
            document.addEventListener('mouseup', stopResize);
            e.preventDefault();
            e.stopPropagation();
        };
        
        const resize = (e) => {
            if (!isResizing) return;
            
            const deltaY = e.clientY - startY;
            let newHeight = startHeight;
            let newTop = startTop;
            
            if (activeHandle === bottomHandle) {
                newHeight = Math.max(30, startHeight + deltaY);
            } else if (activeHandle === topHandle) {
                newHeight = Math.max(30, startHeight - deltaY);
                newTop = startTop + deltaY;
            }
            
            // Snap to 30-minute intervals
            newHeight = Math.round(newHeight / 30) * 30;
            newTop = Math.round(newTop / 30) * 30;
            
            timeBlock.style.height = `${newHeight}px`;
            timeBlock.style.top = `${newTop}px`;
            
            // Update duration
            const duration = newHeight / 60;
            timeBlock.dataset.duration = duration;
            timeBlock.querySelector('.time-block-duration').textContent = `${duration}h`;
            
            // Update visibility based on new duration
            const descriptionElement = timeBlock.querySelector('.time-block-description');
            const durationElement = timeBlock.querySelector('.time-block-duration');
            const activityElement = timeBlock.querySelector('.time-block-activity');
            const description = timeBlock.dataset.description || '';
            
            // Description visibility (1.5+ hours AND has description)
            if (duration >= 1.5 && description.trim()) {
                descriptionElement.textContent = description;
                descriptionElement.style.display = 'block';
            } else {
                descriptionElement.style.display = 'none';
            }
            
            // Activity name visibility (hide for 0.5h activities)
            if (duration <= 0.5) {
                activityElement.style.display = 'none';
            } else {
                activityElement.style.display = 'block';
            }
            
            // Duration visibility (only show for activities > 0.5h)
            if (duration > 0.5) {
                durationElement.style.display = 'block';
            } else {
                durationElement.style.display = 'none';
            }
        };
        
        const stopResize = () => {
            isResizing = false;
            activeHandle = null;
            document.removeEventListener('mousemove', resize);
            document.removeEventListener('mouseup', stopResize);
            this.app.updateDaySummaries();
            
            // Auto-save after resizing
            setTimeout(() => this.app.managers.storage.saveTimesheet(), 500);
        };
        
        topHandle.addEventListener('mousedown', (e) => startResize(e, topHandle));
        bottomHandle.addEventListener('mousedown', (e) => startResize(e, bottomHandle));
    }
    
    /**
     * Adjust time block duration
     */
    adjustDuration(timeBlock, change) {
        const currentDuration = parseFloat(timeBlock.dataset.duration);
        const newDuration = Math.max(0.5, currentDuration + change); // Minimum 30 minutes
        
        // Check for overlaps with the new duration, excluding the current block
        const dayColumn = timeBlock.closest('.day-column');
        const startHour = parseInt(timeBlock.dataset.startHour);
        const startMinute = parseInt(timeBlock.dataset.startMinute || 0);
        
        const hasOverlap = TimeUtils.checkTimeOverlap(dayColumn, startHour, startMinute, newDuration, timeBlock);
        
        if (hasOverlap) {
            const action = change > 0 ? 'expand' : 'shrink';
            this.app.components.toast.show(`Cannot ${action} - would overlap with another entry`, 'warning');
            return;
        }
        
        // Update the time block
        timeBlock.dataset.duration = newDuration;
        timeBlock.style.height = `${newDuration * 60}px`;
        timeBlock.querySelector('.time-block-duration').textContent = `${newDuration}h`;
        
        // Update description visibility based on new duration
        const descriptionElement = timeBlock.querySelector('.time-block-description');
        const description = timeBlock.dataset.description || '';
        if (newDuration >= 1.5 && description.trim()) {
            descriptionElement.textContent = description;
            descriptionElement.style.display = 'block';
        } else {
            descriptionElement.style.display = 'none';
        }
        
        // Update duration and activity name visibility based on new duration
        const durationElement = timeBlock.querySelector('.time-block-duration');
        const activityElement = timeBlock.querySelector('.time-block-activity');
        
        // Activity name visibility (hide for 0.5h activities)
        if (newDuration <= 0.5) {
            activityElement.style.display = 'none';
        } else {
            activityElement.style.display = 'block';
        }
        
        // Duration visibility (only show for activities > 0.5h)
        if (newDuration > 0.5) {
            durationElement.style.display = 'block';
        } else {
            durationElement.style.display = 'none';
        }
        
        this.app.updateDaySummaries();
        
        // Auto-save after adjusting
        setTimeout(() => this.app.managers.storage.saveTimesheet(), 500);
        
        const action = change > 0 ? 'expanded' : 'shrunk';
        this.app.components.toast.show(`Duration ${action} to ${newDuration}h`, 'success');
    }
    
    /**
     * Delete a time block
     */
    deleteTimeBlock(timeBlock) {
        if (!confirm('Are you sure you want to delete this time entry?')) {
            return;
        }
        
        const entryId = timeBlock.dataset.id;
        
        if (entryId && entryId !== 'null') {
            // Delete from database if it has an ID
            frappe.call({
                method: 'erplite.projects.api.delete_timesheet_entry',
                args: { entry_id: entryId },
                callback: (r) => {
                    if (r.message && r.message.success) {
                        // Remove from frontend after successful deletion
                        this.removeTimeBlockFromDOM(timeBlock);
                        this.app.components.toast.show('Time entry deleted successfully!', 'success');
                    } else {
                        this.app.components.toast.show('Error: ' + (r.message.message || 'Failed to delete time entry'), 'error');
                    }
                },
                error: (err) => {
                    console.error('Error deleting time entry:', err);
                    this.app.components.toast.show('Error: Failed to delete time entry', 'error');
                }
            });
        } else {
            // Just remove from frontend if it's a new entry without ID
            this.removeTimeBlockFromDOM(timeBlock);
            this.app.components.toast.show('Time entry deleted', 'success');
        }
    }
    
    /**
     * Remove time block from DOM and state
     */
    removeTimeBlockFromDOM(timeBlock) {
        // Remove from state array
        this.app.state.timeBlocks = this.app.state.timeBlocks.filter(block => block !== timeBlock);
        
        // Clear selection if this block was selected
        if (this.app.state.selectedTimeBlock === timeBlock) {
            this.app.clearSelection();
        }
        
        // Remove from DOM
        timeBlock.remove();
        
        // Update summaries
        this.app.updateDaySummaries();
    }
    
    /**
     * Update time block data and appearance
     */
    updateTimeBlock(timeBlock, data) {
        // Update data attributes
        Object.entries(data).forEach(([key, value]) => {
            if (value !== undefined) {
                timeBlock.dataset[key] = value;
            }
        });
        
        // Update visual content
        if (data.projectName) {
            timeBlock.querySelector('.time-block-header').textContent = data.projectName;
        }
        if (data.activityName) {
            timeBlock.querySelector('.time-block-activity').textContent = data.activityName;
        }
        if (data.duration) {
            timeBlock.querySelector('.time-block-duration').textContent = `${data.duration}h`;
        }
        
        // Update description, duration, and activity name visibility
        if (data.description !== undefined || data.duration) {
            const descriptionElement = timeBlock.querySelector('.time-block-description');
            const durationElement = timeBlock.querySelector('.time-block-duration');
            const activityElement = timeBlock.querySelector('.time-block-activity');
            const description = data.description || timeBlock.dataset.description || '';
            const duration = data.duration || parseFloat(timeBlock.dataset.duration);
            
            // Description visibility (1.5+ hours AND has description)
            if (duration >= 1.5 && description.trim()) {
                descriptionElement.textContent = description;
                descriptionElement.style.display = 'block';
            } else {
                descriptionElement.style.display = 'none';
            }
            
            // Activity name visibility (hide for 0.5h activities)
            if (duration <= 0.5) {
                activityElement.style.display = 'none';
            } else {
                activityElement.style.display = 'block';
            }
            
            // Duration visibility (only show for activities > 0.5h)
            if (duration > 0.5) {
                durationElement.style.display = 'block';
            } else {
                durationElement.style.display = 'none';
            }
        }
        
        // Update visual style
        if (data.color) {
            timeBlock.style.setProperty('--project-color', data.color);
        }
        
        if (data.startHour !== undefined || data.startMinute !== undefined || data.duration) {
            const startHour = data.startHour || parseInt(timeBlock.dataset.startHour);
            const startMinute = data.startMinute || parseInt(timeBlock.dataset.startMinute || 0);
            const duration = data.duration || parseFloat(timeBlock.dataset.duration);
            
            const startHourOffset = this.app.state.isFullDay ? 0 : 8;
            timeBlock.style.top = `${(startHour - startHourOffset) * 60 + startMinute}px`;
            timeBlock.style.height = `${duration * 60}px`;
        }
    }
    
    /**
     * Clone a time block to adjacent day
     */
    cloneTimeBlock(sourceBlock, direction) {
        const currentDayColumn = sourceBlock.closest('.day-column');
        const allDayColumns = Array.from(document.querySelectorAll('.day-column'));
        const currentIndex = allDayColumns.indexOf(currentDayColumn);
        const targetIndex = currentIndex + direction;
        
        if (targetIndex < 0 || targetIndex >= allDayColumns.length) {
            this.app.components.toast.show('Cannot clone beyond week boundaries', 'warning');
            return;
        }
        
        const targetDayColumn = allDayColumns[targetIndex];
        const targetDate = targetDayColumn.dataset.date;
        
        const startHour = parseInt(sourceBlock.dataset.startHour);
        const startMinute = parseInt(sourceBlock.dataset.startMinute || 0);
        const duration = parseFloat(sourceBlock.dataset.duration);
        
        // Check for overlaps in target day
        const hasOverlap = TimeUtils.checkTimeOverlap(targetDayColumn, startHour, startMinute, duration);
        
        if (hasOverlap) {
            const direction_text = direction === -1 ? 'previous' : 'next';
            this.app.components.toast.show(`Cannot clone to ${direction_text} day - time slot is already occupied`, 'warning');
            return;
        }
        
        // Create clone with same data
        const cloneData = {
            project: sourceBlock.dataset.project,
            activity: sourceBlock.dataset.activity,
            projectName: sourceBlock.querySelector('.time-block-header').textContent,
            activityName: sourceBlock.querySelector('.time-block-activity').textContent,
            color: sourceBlock.style.getPropertyValue('--project-color'),
            date: targetDate,
            startHour: startHour,
            startMinute: startMinute,
            duration: duration,
            description: sourceBlock.dataset.description || ''
        };
        
        const newTimeBlock = this.createTimeBlock(cloneData);
        if (newTimeBlock) {
            this.app.selectTimeBlock(newTimeBlock);
        }
        
        this.app.updateDaySummaries();
        
        const direction_text = direction === -1 ? 'previous' : 'next';
        this.app.components.toast.show(`Time entry cloned to ${direction_text} day!`, 'success');
        
        // Auto-save after cloning
        setTimeout(() => this.app.managers.storage.saveTimesheet(), 500);
    }
}

// Export to global scope
window.TimeBlockManager = TimeBlockManager;
