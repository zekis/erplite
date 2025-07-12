/**
 * Time block component for managing time block UI and interactions
 */
class TimeBlockComponent {
    constructor(app) {
        this.app = app;
    }
    
    /**
     * Setup control buttons for a time block
     */
    setupControlButtons(timeBlock) {
        const editBtn = timeBlock.querySelector('.edit-btn');
        const cloneBtn = timeBlock.querySelector('.clone-btn');
        const expandBtn = timeBlock.querySelector('.expand-btn');
        const shrinkBtn = timeBlock.querySelector('.shrink-btn');
        const deleteBtn = timeBlock.querySelector('.delete-btn');
        
        // Remove existing listeners by replacing elements
        if (editBtn) editBtn.replaceWith(editBtn.cloneNode(true));
        if (cloneBtn) cloneBtn.replaceWith(cloneBtn.cloneNode(true));
        if (expandBtn) expandBtn.replaceWith(expandBtn.cloneNode(true));
        if (shrinkBtn) shrinkBtn.replaceWith(shrinkBtn.cloneNode(true));
        if (deleteBtn) deleteBtn.replaceWith(deleteBtn.cloneNode(true));
        
        // Get fresh references
        const newEditBtn = timeBlock.querySelector('.edit-btn');
        const newCloneBtn = timeBlock.querySelector('.clone-btn');
        const newExpandBtn = timeBlock.querySelector('.expand-btn');
        const newShrinkBtn = timeBlock.querySelector('.shrink-btn');
        const newDeleteBtn = timeBlock.querySelector('.delete-btn');
        
        // Setup event listeners
        if (newEditBtn) {
            newEditBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.app.components.modal.openEditModal(timeBlock);
            });
        }
        
        if (newCloneBtn) {
            this.setupCloneDragging(newCloneBtn, timeBlock);
        }
        
        if (newExpandBtn) {
            newExpandBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.app.managers.timeBlock.adjustDuration(timeBlock, 0.5); // Expand by 30 minutes
            });
        }
        
        if (newShrinkBtn) {
            newShrinkBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.app.managers.timeBlock.adjustDuration(timeBlock, -0.5); // Shrink by 30 minutes
            });
        }
        
        if (newDeleteBtn) {
            newDeleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.app.managers.timeBlock.deleteTimeBlock(timeBlock);
            });
        }
    }
    
    /**
     * Setup clone button dragging functionality
     */
    setupCloneDragging(cloneBtn, sourceTimeBlock) {
        // Make clone button draggable
        cloneBtn.draggable = true;
        
        cloneBtn.addEventListener('dragstart', (e) => {
            e.stopPropagation(); // Prevent the time block's drag from triggering
            
            cloneBtn.classList.add('dragging');
            
            // Store the source time block data for cloning
            const timeBlockData = {
                project: sourceTimeBlock.dataset.project,
                task: sourceTimeBlock.dataset.task,
                projectName: sourceTimeBlock.querySelector('.time-block-header').textContent,
                taskName: sourceTimeBlock.querySelector('.time-block-task').textContent,
                color: sourceTimeBlock.style.getPropertyValue('--project-color'),
                duration: parseFloat(sourceTimeBlock.dataset.duration),
                startHour: parseInt(sourceTimeBlock.dataset.startHour),
                startMinute: parseInt(sourceTimeBlock.dataset.startMinute || 0),
                description: sourceTimeBlock.dataset.description || '',
                isExistingBlock: true,
                isDuplicate: true, // This is a clone operation
                sourceBlock: sourceTimeBlock
            };
            
            e.dataTransfer.setData('text/plain', JSON.stringify(timeBlockData));
            e.dataTransfer.effectAllowed = 'copy';
        });
        
        cloneBtn.addEventListener('dragend', () => {
            cloneBtn.classList.remove('dragging');
        });
    }
    
    /**
     * Update time block visual appearance
     */
    updateTimeBlockAppearance(timeBlock, data) {
        // Update content
        if (data.projectName) {
            const headerElement = timeBlock.querySelector('.time-block-header');
            if (headerElement) headerElement.textContent = data.projectName;
        }
        
        if (data.taskName) {
            const taskElement = timeBlock.querySelector('.time-block-task');
            if (taskElement) taskElement.textContent = data.taskName;
        }
        
        if (data.duration) {
            const durationElement = timeBlock.querySelector('.time-block-duration');
            if (durationElement) durationElement.textContent = `${data.duration}h`;
        }
        
        // Update description visibility
        if (data.description !== undefined || data.duration) {
            this.updateDescriptionVisibility(timeBlock, data.description, data.duration);
        }
        
        // Update color
        if (data.color) {
            timeBlock.style.setProperty('--project-color', data.color);
        }
        
        // Update position and size
        if (data.startHour !== undefined || data.startMinute !== undefined || data.duration) {
            this.updateTimeBlockPosition(timeBlock, data);
        }
    }
    
    /**
     * Update description visibility based on duration and content
     */
    updateDescriptionVisibility(timeBlock, description, duration) {
        const descriptionElement = timeBlock.querySelector('.time-block-description');
        if (!descriptionElement) return;
        
        const finalDescription = description || timeBlock.dataset.description || '';
        const finalDuration = duration || parseFloat(timeBlock.dataset.duration);
        
        if (finalDuration >= 1.5 && finalDescription.trim()) {
            descriptionElement.textContent = finalDescription;
            descriptionElement.style.display = 'block';
        } else {
            descriptionElement.style.display = 'none';
        }
    }
    
    /**
     * Update time block position and size
     */
    updateTimeBlockPosition(timeBlock, data) {
        const startHour = data.startHour || parseInt(timeBlock.dataset.startHour);
        const startMinute = data.startMinute || parseInt(timeBlock.dataset.startMinute || 0);
        const duration = data.duration || parseFloat(timeBlock.dataset.duration);
        
        const startHourOffset = this.app.state.isFullDay ? 0 : 8;
        timeBlock.style.top = `${(startHour - startHourOffset) * 60 + startMinute}px`;
        timeBlock.style.height = `${duration * 60}px`;
    }
    
    /**
     * Highlight time block
     */
    highlightTimeBlock(timeBlock, type = 'selected') {
        timeBlock.classList.add(`highlight-${type}`);
        
        // Auto-remove highlight after delay
        setTimeout(() => {
            timeBlock.classList.remove(`highlight-${type}`);
        }, 2000);
    }
    
    /**
     * Get time block data
     */
    getTimeBlockData(timeBlock) {
        const dayColumn = timeBlock.closest('.day-column');
        
        return {
            id: timeBlock.dataset.id,
            project: timeBlock.dataset.project,
            task: timeBlock.dataset.task,
            projectName: timeBlock.querySelector('.time-block-header').textContent,
            taskName: timeBlock.querySelector('.time-block-task').textContent,
            color: timeBlock.style.getPropertyValue('--project-color'),
            date: dayColumn ? dayColumn.dataset.date : null,
            startHour: parseInt(timeBlock.dataset.startHour),
            startMinute: parseInt(timeBlock.dataset.startMinute || 0),
            duration: parseFloat(timeBlock.dataset.duration),
            description: timeBlock.dataset.description || ''
        };
    }
    
    /**
     * Validate time block data
     */
    validateTimeBlockData(data) {
        const errors = [];
        
        if (!data.project) errors.push('Project is required');
        if (!data.task) errors.push('Task is required');
        if (!data.date) errors.push('Date is required');
        if (data.duration <= 0) errors.push('Duration must be greater than 0');
        if (data.startHour < 0 || data.startHour > 23) errors.push('Start hour must be between 0 and 23');
        if (data.startMinute < 0 || data.startMinute > 59) errors.push('Start minute must be between 0 and 59');
        
        return {
            isValid: errors.length === 0,
            errors: errors
        };
    }
    
    /**
     * Get time block conflicts
     */
    getTimeBlockConflicts(timeBlock, newData = null) {
        const dayColumn = timeBlock.closest('.day-column');
        if (!dayColumn) return [];
        
        const data = newData || this.getTimeBlockData(timeBlock);
        const conflicts = [];
        
        // Check for overlaps with other time blocks
        const otherBlocks = dayColumn.querySelectorAll('.time-block');
        otherBlocks.forEach(otherBlock => {
            if (otherBlock === timeBlock) return;
            
            const otherData = this.getTimeBlockData(otherBlock);
            
            // Check for time overlap
            const startTime = data.startHour + data.startMinute / 60;
            const endTime = startTime + data.duration;
            const otherStartTime = otherData.startHour + otherData.startMinute / 60;
            const otherEndTime = otherStartTime + otherData.duration;
            
            if (startTime < otherEndTime && endTime > otherStartTime) {
                conflicts.push({
                    type: 'overlap',
                    block: otherBlock,
                    data: otherData,
                    message: `Overlaps with ${otherData.projectName} - ${otherData.taskName}`
                });
            }
        });
        
        return conflicts;
    }
    
    /**
     * Show time block tooltip
     */
    showTooltip(timeBlock, content, position = 'top') {
        // Remove existing tooltip
        this.hideTooltip();
        
        const tooltip = DOMUtils.createElement('div', {
            className: 'time-block-tooltip',
            style: {
                position: 'absolute',
                background: '#333',
                color: 'white',
                padding: '0.5rem',
                borderRadius: '0.25rem',
                fontSize: '0.75rem',
                zIndex: '1000',
                pointerEvents: 'none',
                maxWidth: '200px',
                wordWrap: 'break-word'
            }
        }, content);
        
        document.body.appendChild(tooltip);
        
        // Position tooltip
        const rect = timeBlock.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        
        let top, left;
        
        switch (position) {
            case 'top':
                top = rect.top - tooltipRect.height - 5;
                left = rect.left + (rect.width - tooltipRect.width) / 2;
                break;
            case 'bottom':
                top = rect.bottom + 5;
                left = rect.left + (rect.width - tooltipRect.width) / 2;
                break;
            case 'left':
                top = rect.top + (rect.height - tooltipRect.height) / 2;
                left = rect.left - tooltipRect.width - 5;
                break;
            case 'right':
                top = rect.top + (rect.height - tooltipRect.height) / 2;
                left = rect.right + 5;
                break;
        }
        
        // Ensure tooltip stays within viewport
        top = Math.max(5, Math.min(top, window.innerHeight - tooltipRect.height - 5));
        left = Math.max(5, Math.min(left, window.innerWidth - tooltipRect.width - 5));
        
        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
        
        // Store reference for cleanup
        this.currentTooltip = tooltip;
        
        // Auto-hide after delay
        setTimeout(() => {
            this.hideTooltip();
        }, 3000);
    }
    
    /**
     * Hide time block tooltip
     */
    hideTooltip() {
        if (this.currentTooltip) {
            this.currentTooltip.remove();
            this.currentTooltip = null;
        }
    }
    
    /**
     * Get time block summary
     */
    getTimeBlockSummary(timeBlock) {
        const data = this.getTimeBlockData(timeBlock);
        const startTime = TimeUtils.formatTime(data.startHour, data.startMinute);
        
        // Calculate end time properly
        const totalStartMinutes = data.startHour * 60 + data.startMinute;
        const totalDurationMinutes = data.duration * 60;
        const totalEndMinutes = totalStartMinutes + totalDurationMinutes;
        
        const endHour = Math.floor(totalEndMinutes / 60);
        const endMinute = totalEndMinutes % 60;
        const endTime = TimeUtils.formatTime(endHour, endMinute);
        
        return {
            project: data.projectName,
            task: data.taskName,
            timeRange: `${startTime} - ${endTime}`,
            duration: `${data.duration}h`,
            description: data.description,
            date: TimeUtils.formatDate(data.date)
        };
    }
}

// Export to global scope
window.TimeBlockComponent = TimeBlockComponent;
