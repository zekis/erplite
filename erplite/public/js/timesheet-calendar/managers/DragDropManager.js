/**
 * Manages drag and drop functionality for time blocks and activities
 */
class DragDropManager {
    constructor(app) {
        this.app = app;
        this.isDragging = false;
        this.dragState = {
            isDragging: false,
            draggedData: null,
            dragOffset: { x: 0, y: 0 },
            currentPreview: null
        };
        
        this.init();
    }
    
    /**
     * Initialize drag and drop functionality
     */
    init() {
        this.setupSidebarDragAndDrop();
        this.setupTimeSlotDropZones();
    }
    
    /**
     * Setup drag and drop for sidebar activity blocks
     */
    setupSidebarDragAndDrop() {
        document.querySelectorAll('.activity-block').forEach(block => {
            block.addEventListener('dragstart', (e) => {
                this.handleSidebarDragStart(e, block);
            });
            
            block.addEventListener('dragend', (e) => {
                this.handleSidebarDragEnd(e, block);
            });
        });
    }
    
    /**
     * Handle drag start from sidebar
     */
    handleSidebarDragStart(e, block) {
        block.classList.add('dragging');
        
        const activityData = {
            project: block.dataset.project,
            activity: block.dataset.activity,
            projectName: block.dataset.projectName,
            activityName: block.dataset.activityName,
            color: block.dataset.color,
            isExistingBlock: false
        };
        
        e.dataTransfer.setData('text/plain', JSON.stringify(activityData));
        e.dataTransfer.effectAllowed = 'copy';
    }
    
    /**
     * Handle drag end from sidebar
     */
    handleSidebarDragEnd(e, block) {
        block.classList.remove('dragging');
    }
    
    /**
     * Setup time block dragging
     */
    setupTimeBlockDragging(timeBlock) {
        let dragStartX = 0;
        let dragStartY = 0;
        let isDuplicateMode = false;
        let touchStartTime = 0;
        let touchDragData = null;
        
        // Make the time block draggable (but not the resize handles)
        timeBlock.draggable = true;
        
        // Track mouse down for drag detection
        timeBlock.addEventListener('mousedown', (e) => {
            // Don't handle if clicking on resize handles or control buttons
            if (e.target.classList.contains('resize-handle') || 
                e.target.classList.contains('control-btn') ||
                e.target.closest('.time-block-controls')) {
                return;
            }
            
            isDuplicateMode = e.button === 2; // Right mouse button
            this.app.managers.timeBlock.dragStartTime = Date.now();
            dragStartX = e.clientX;
            dragStartY = e.clientY;
            
            // Calculate drag offset relative to the time block
            const rect = timeBlock.getBoundingClientRect();
            this.dragState.dragOffset.x = e.clientX - rect.left;
            this.dragState.dragOffset.y = e.clientY - rect.top;
        });
        
        // Touch events for mobile support
        timeBlock.addEventListener('touchstart', (e) => {
            // Don't handle if touching resize handles or control buttons
            if (e.target.classList.contains('resize-handle') || 
                e.target.classList.contains('control-btn') ||
                e.target.closest('.time-block-controls')) {
                return;
            }
            
            touchStartTime = Date.now();
            const touch = e.touches[0];
            dragStartX = touch.clientX;
            dragStartY = touch.clientY;
            
            // Calculate drag offset relative to the time block
            const rect = timeBlock.getBoundingClientRect();
            this.dragState.dragOffset.x = touch.clientX - rect.left;
            this.dragState.dragOffset.y = touch.clientY - rect.top;
            
            // Prepare drag data for touch
            let projectColor = this.app.state.projectColors[timeBlock.dataset.project] || '#6b7280';
            
            touchDragData = {
                project: timeBlock.dataset.project,
                activity: timeBlock.dataset.activity,
                projectName: timeBlock.querySelector('.time-block-header').textContent,
                activityName: timeBlock.querySelector('.time-block-activity').textContent,
                color: projectColor,
                duration: parseFloat(timeBlock.dataset.duration),
                startHour: parseInt(timeBlock.dataset.startHour),
                startMinute: parseInt(timeBlock.dataset.startMinute || 0),
                description: timeBlock.dataset.description || '',
                id: timeBlock.dataset.id,
                isExistingBlock: true,
                isDuplicate: false, // Touch doesn't support right-click, so always move
                height: timeBlock.offsetHeight,
                dragOffset: this.dragState.dragOffset
            };
            
            // Prevent default to avoid scrolling
            e.preventDefault();
        }, { passive: false });
        
        timeBlock.addEventListener('touchmove', (e) => {
            if (!touchDragData) return;
            
            const touch = e.touches[0];
            const deltaX = Math.abs(touch.clientX - dragStartX);
            const deltaY = Math.abs(touch.clientY - dragStartY);
            
            // Start drag if moved enough (10px threshold)
            if (deltaX > 10 || deltaY > 10) {
                if (!this.isDragging) {
                    this.startTouchDrag(timeBlock, touchDragData);
                }
                
                this.handleTouchMove(touch);
            }
            
            e.preventDefault();
        }, { passive: false });
        
        timeBlock.addEventListener('touchend', (e) => {
            if (this.isDragging && touchDragData) {
                this.handleTouchDrop(e.changedTouches[0]);
            }
            
            this.endTouchDrag(timeBlock);
            touchDragData = null;
            e.preventDefault();
        }, { passive: false });
        
        timeBlock.addEventListener('dragstart', (e) => {
            // Don't drag if we're clicking on resize handles or control buttons
            if (e.target.classList.contains('resize-handle') || 
                e.target.classList.contains('control-btn') ||
                e.target.closest('.time-block-controls')) {
                e.preventDefault();
                return;
            }
            
            this.isDragging = true;
            this.dragState.isDragging = true;
            
            // Get the correct project color
            let projectColor = this.app.state.projectColors[timeBlock.dataset.project] || '#6b7280';
            
            const timeBlockData = {
                project: timeBlock.dataset.project,
                activity: timeBlock.dataset.activity,
                projectName: timeBlock.querySelector('.time-block-header').textContent,
                activityName: timeBlock.querySelector('.time-block-activity').textContent,
                color: projectColor,
                duration: parseFloat(timeBlock.dataset.duration),
                startHour: parseInt(timeBlock.dataset.startHour),
                startMinute: parseInt(timeBlock.dataset.startMinute || 0),
                description: timeBlock.dataset.description || '',
                id: timeBlock.dataset.id,
                isExistingBlock: true,
                isDuplicate: isDuplicateMode,
                height: timeBlock.offsetHeight,
                dragOffset: this.dragState.dragOffset
            };
            
            this.dragState.draggedData = timeBlockData;
            
            // For duplicates, keep original visible but faded
            if (isDuplicateMode) {
                timeBlock.classList.add('duplicating');
                timeBlock.style.opacity = '0.7';
            } else {
                // For moves, completely hide the original during drag to avoid interference
                timeBlock.classList.add('dragging');
                timeBlock.style.visibility = 'hidden';
            }
            
            // Store drag data globally as well as in dataTransfer (backup)
            window.currentDragData = timeBlockData;
            
            e.dataTransfer.setData('text/plain', JSON.stringify(timeBlockData));
            e.dataTransfer.effectAllowed = isDuplicateMode ? 'copy' : 'move';
        });
        
        timeBlock.addEventListener('dragend', (e) => {
            timeBlock.classList.remove('dragging', 'duplicating');
            timeBlock.style.opacity = '';
            timeBlock.style.pointerEvents = ''; // Reset pointer events
            timeBlock.style.visibility = ''; // Reset visibility
            
            // Reset mode flag
            isDuplicateMode = false;
            
            // Clear drag state and preview
            this.dragState.isDragging = false;
            this.dragState.draggedData = null;
            this.clearDragPreview();
            
            // Clear all drop zones
            this.clearDropZones();
            
            // Reset drag state after a short delay
            setTimeout(() => {
                this.isDragging = false;
            }, 100);
        });
        
        // Add drag event handlers to time blocks so they can receive drops
        timeBlock.addEventListener('dragover', (e) => this.allowDrop(e));
        timeBlock.addEventListener('dragenter', (e) => this.dragEnter(e));
        timeBlock.addEventListener('dragleave', (e) => this.dragLeave(e));
    }
    
    /**
     * Setup drop zones for time slots
     */
    setupTimeSlotDropZones() {
        document.querySelectorAll('.time-slot').forEach(timeSlot => {
            timeSlot.addEventListener('dragover', (e) => this.allowDrop(e));
            timeSlot.addEventListener('dragenter', (e) => this.dragEnter(e));
            timeSlot.addEventListener('dragleave', (e) => this.dragLeave(e));
            // NOTE: Don't add drop event listener here - it's handled by HTML ondrop attribute
            // to avoid duplicate event handling
        });
    }
    
    /**
     * Allow drop on time slots and time blocks
     */
    allowDrop(event) {
        event.preventDefault();
        
        // If we're dragging a time block, check for overlaps to provide proper cursor feedback
        if (this.dragState.isDragging && this.dragState.draggedData && this.dragState.draggedData.isExistingBlock) {
            const target = event.currentTarget;
            const dayColumn = target.closest('.day-column');
            
            let hour, minute;
            
            // Handle both time slots and time blocks
            if (target.classList.contains('time-block')) {
                // If hovering over a time block, use its position
                hour = parseInt(target.dataset.startHour);
                minute = parseInt(target.dataset.startMinute || 0);
            } else {
                // If hovering over a time slot, use its hour/minute
                hour = parseInt(target.dataset.hour);
                minute = parseInt(target.dataset.minute || 0);
            }
            
            const dragOffset = this.dragState.draggedData.dragOffset || { x: 0, y: 0 };
            
            // Calculate final position using same logic as drop
            const offsetInMinutes = Math.round(dragOffset.y / 30) * 30;
            const targetTotalMinutes = (hour * 60 + minute) - offsetInMinutes;
            
            // Ensure we don't get negative values
            const clampedTotalMinutes = Math.max(0, targetTotalMinutes);
            const finalStartHour = Math.floor(clampedTotalMinutes / 60);
            const finalStartMinute = clampedTotalMinutes % 60;
            
            // Get the original block being dragged
            const originalBlock = document.querySelector('.time-block.dragging');
            
            // Only exclude the original block if it's in the same day column as the drop target
            const excludeBlock = (originalBlock && originalBlock.closest('.day-column') === dayColumn) ? originalBlock : null;
            
            // Check for overlaps, excluding the original block only if it's in the same day
            const hasOverlap = TimeUtils.checkTimeOverlap(
                dayColumn, 
                finalStartHour, 
                finalStartMinute, 
                this.dragState.draggedData.duration, 
                excludeBlock
            );
            
            
            // Set the drop effect based on overlap detection
            if (hasOverlap) {
                event.dataTransfer.dropEffect = 'none';
            } else {
                event.dataTransfer.dropEffect = this.dragState.draggedData.isDuplicate ? 'copy' : 'move';
            }
        }
    }
    
    /**
     * Handle drag enter on time slots
     */
    dragEnter(event) {
        event.preventDefault();
        
        const target = event.currentTarget;
        
        // Show drag preview if we're dragging a time block
        if (this.dragState.isDragging && this.dragState.draggedData) {
            this.showDragPreview(target);
            
            // For time block drags, don't show drop zones - only show the drag preview
            // The drag preview is sufficient visual feedback
        } else {
            // For sidebar drags, show drop zones on all empty slots
            if (!target.classList.contains('time-block')) {
                target.classList.add('drop-zone');
            }
        }
    }
    
    /**
     * Handle drag leave on time slots
     */
    dragLeave(event) {
        // Clear drop zones for all drags
        event.currentTarget.classList.remove('drop-zone');
        
        // Don't clear preview here - let dragEnter handle it
        // The preview should persist as we move between time slots
    }
    
    /**
     * Show drag preview
     */
    showDragPreview(target) {
        // Clear any existing preview
        this.clearDragPreview();
        
        if (!this.dragState.draggedData) return;
        
        const dayColumn = target.closest('.day-column');
        
        let targetHour, targetMinute;
        
        // Handle both time slots and time blocks
        if (target.classList.contains('time-block')) {
            // If hovering over a time block, use its position
            targetHour = parseInt(target.dataset.startHour);
            targetMinute = parseInt(target.dataset.startMinute || 0);
        } else {
            // If hovering over a time slot, use its hour/minute
            targetHour = parseInt(target.dataset.hour);
            targetMinute = parseInt(target.dataset.minute || 0);
        }
        
        const duration = this.dragState.draggedData.duration;
        const dragOffset = this.dragState.draggedData.dragOffset || { x: 0, y: 0 };
        
        // Calculate the offset using different pixel ratios for mobile vs desktop
        const pixelsPerMinute = this.isMobileLayout() ? 2 : 1; // Mobile: 60px/30min = 2px/min, Desktop: 30px/30min = 1px/min
        const offsetInMinutes = Math.round(dragOffset.y / (30 * pixelsPerMinute)) * 30; // Snap to 30-minute intervals
        const targetTotalMinutes = (targetHour * 60 + targetMinute) - offsetInMinutes;
        const adjustedStartHour = Math.max(0, Math.floor(targetTotalMinutes / 60));
        const adjustedStartMinute = Math.max(0, targetTotalMinutes % 60);
        
        // Calculate position and height (accounting for different time slot heights)
        const startHourOffset = this.app.state.isFullDay ? 0 : 8;
        const timeSlotHeight = this.isMobileLayout() ? 60 : 30; // Mobile: 60px per 30min, Desktop: 30px per 30min
        const previewTop = (adjustedStartHour - startHourOffset) * timeSlotHeight * 2 + (adjustedStartMinute / 30) * timeSlotHeight;
        const previewHeight = duration * timeSlotHeight * 2; // 2 slots per hour
        
        // Ensure preview doesn't go outside the calendar bounds
        const maxTop = (24 - startHourOffset) * 60 - previewHeight; // Maximum valid top position
        const finalTop = Math.max(0, Math.min(previewTop, maxTop));
        
        // Create preview element
        const preview = document.createElement('div');
        preview.className = 'drag-preview';
        preview.style.top = `${finalTop}px`;
        preview.style.height = `${previewHeight}px`;
        
        // Adjust positioning for mobile layout
        if (this.isMobileLayout()) {
            preview.style.left = '52px';
            preview.style.right = '8px';
        } else {
            preview.style.left = '4px';
            preview.style.right = '4px';
        }
        
        // Add preview content
        preview.innerHTML = `
            <div style="padding: 0.5rem; font-size: 0.75rem; color: #3b82f6; font-weight: 500;">
                ${this.dragState.draggedData.projectName}<br>
                ${this.dragState.draggedData.activityName}<br>
                <span style="font-size: 0.625rem;">${duration}h</span>
            </div>
        `;
        
        dayColumn.appendChild(preview);
        this.dragState.currentPreview = preview;
    }
    
    /**
     * Clear drag preview
     */
    clearDragPreview() {
        if (this.dragState.currentPreview) {
            this.dragState.currentPreview.remove();
            this.dragState.currentPreview = null;
        }
    }
    
    /**
     * Clear all drop zones
     */
    clearDropZones() {
        document.querySelectorAll('.time-slot.drop-zone').forEach(slot => {
            slot.classList.remove('drop-zone');
        });
    }
    
    /**
     * Handle drop on time slots
     */
    dropTimeBlock(event) {
        console.log('🎯 DROP: Starting drop operation');
        
        // Prevent multiple drops for the same drag operation
        if (this.dragState.isProcessingDrop) {
            console.log('  - ⚠️ Already processing drop, ignoring duplicate');
            return;
        }
        this.dragState.isProcessingDrop = true;
        
        event.preventDefault();
        event.currentTarget.classList.remove('drop-zone');
        this.clearDragPreview();
        
        const timeSlot = event.currentTarget;
        const dayColumn = timeSlot.closest('.day-column');
        const date = dayColumn.dataset.date;
        const hour = parseInt(timeSlot.dataset.hour);
        const minute = parseInt(timeSlot.dataset.minute || 0);
        
        console.log('  - Drop target:', { date, hour, minute });
        console.log('  - Current timeBlocks array length:', this.app.state.timeBlocks.length);
        
        let activityData;
        try {
            activityData = JSON.parse(event.dataTransfer.getData('text/plain'));
            console.log('  - Got activityData from dataTransfer');
        } catch (e) {
            // Fallback to global data if dataTransfer fails
            activityData = window.currentDragData;
            console.log('  - Fallback to global currentDragData');
        }
        
        // Use global data as backup if dataTransfer data is incomplete
        if (!activityData || !activityData.dragOffset) {
            activityData = window.currentDragData || activityData;
            console.log('  - Using backup global data');
        }
        
        console.log('  - Final activityData:', activityData);
        
        // Calculate the actual placement position based on drag offset with 30-minute precision
        let finalStartHour = hour;
        let finalStartMinute = minute;
        
        if (activityData && activityData.isExistingBlock && activityData.dragOffset) {
            // Use the same mobile-aware calculation as the preview
            const pixelsPerMinute = this.isMobileLayout() ? 2 : 1; // Mobile: 60px/30min = 2px/min, Desktop: 30px/30min = 1px/min
            const offsetInMinutes = Math.round(activityData.dragOffset.y / (30 * pixelsPerMinute)) * 30; // Snap to 30-minute intervals
            
            // Calculate final position using the same logic as preview
            const targetTotalMinutes = (hour * 60 + minute) - offsetInMinutes;
            finalStartHour = Math.max(0, Math.floor(targetTotalMinutes / 60));
            finalStartMinute = Math.max(0, targetTotalMinutes % 60);
            
            console.log('  - Calculated final position:', { finalStartHour, finalStartMinute });
        }
        
        if (activityData.isExistingBlock) {
            if (activityData.isDuplicate) {
                console.log('📋 DUPLICATE: Processing duplicate operation');
                
                // Duplicating an existing time block (right-click drag)
                const originalBlock = document.querySelector('.time-block.duplicating');
                console.log('  - Found original duplicating block:', !!originalBlock);
                
                // Check for overlaps before creating duplicate (don't exclude original since it's a copy)
                const hasOverlap = TimeUtils.checkTimeOverlap(dayColumn, finalStartHour, finalStartMinute, activityData.duration);
                
                if (hasOverlap) {
                    console.log('  - ❌ Overlap detected, cancelling duplicate');
                    this.app.components.toast.show('Cannot place duplicate here - time slot is already occupied', 'warning');
                    return;
                }
                
                // Create the duplicate with preserved data but no ID (new entry)
                const newTimeBlock = this.app.managers.timeBlock.createTimeBlock({
                    ...activityData,
                    date: date,
                    startHour: finalStartHour,
                    startMinute: finalStartMinute,
                    duration: activityData.duration, // Keep original duration
                    id: null // Remove ID so it's treated as a new entry
                });
                
                console.log('  - ✅ Created duplicate time block:', !!newTimeBlock);
                
                // Select the newly created time block
                if (newTimeBlock) {
                    this.app.selectTimeBlock(newTimeBlock);
                }
                
                this.app.components.toast.show('Time entry duplicated successfully!', 'success');
                // Auto-save after duplicating
                setTimeout(() => this.app.managers.storage.saveTimesheet(), 500);
            } else {
                // Moving an existing time block (left-click drag)
                // Just move the existing block to the new position
                
                const originalBlock = document.querySelector('.time-block.dragging');
                
                if (!originalBlock) {
                    console.log('  - ⚠️ Original block not found');
                    this.dragState.isProcessingDrop = false;
                    return;
                }
                
                // Check for overlaps at the new location (excluding the original block)
                const hasOverlap = TimeUtils.checkTimeOverlap(dayColumn, finalStartHour, finalStartMinute, activityData.duration, originalBlock);
                
                if (hasOverlap) {
                    this.app.components.toast.show('Cannot move entry here - time slot is already occupied', 'warning');
                    // Reset processing flag
                    this.dragState.isProcessingDrop = false;
                    return;
                }
                
                // Move the time block to the new day column
                dayColumn.appendChild(originalBlock);
                
                // Update the time block's position and data
                const startHourOffset = this.app.state.isFullDay ? 0 : 8;
                originalBlock.style.top = `${(finalStartHour - startHourOffset) * 60 + finalStartMinute}px`;
                
                // Update data attributes
                originalBlock.dataset.startHour = finalStartHour;
                originalBlock.dataset.startMinute = finalStartMinute;
                
                // Clear dragging state
                originalBlock.classList.remove('dragging');
                originalBlock.style.opacity = '';
                
                // Select the moved time block
                this.app.selectTimeBlock(originalBlock);
                
                this.app.components.toast.show('Time entry moved successfully!', 'success');
                
                // Auto-save after moving
                setTimeout(() => this.app.managers.storage.saveTimesheet(), 500);
            }
        } else {
            console.log('🆕 NEW: Creating new time block from sidebar');
            
            // Creating new time block from sidebar activity
            // Check for overlaps before creating new block
            const hasOverlap = TimeUtils.checkTimeOverlap(dayColumn, hour, 0, 1); // Default 1 hour
            
            if (hasOverlap) {
                console.log('  - ❌ Overlap detected, cancelling creation');
                this.app.components.toast.show('Cannot place entry here - time slot is already occupied', 'warning');
                return;
            }
            
            const newTimeBlock = this.app.managers.timeBlock.createTimeBlock({
                ...activityData,
                date: date,
                startHour: hour,
                startMinute: 0,
                duration: 1 // Default 1 hour for new entries
            });
            
            console.log('  - ✅ Created new time block:', !!newTimeBlock);
            
            // Select the newly created time block
            if (newTimeBlock) {
                this.app.selectTimeBlock(newTimeBlock);
            }
            
            this.app.components.toast.show('Time entry created successfully!', 'success');
            
            // Auto-save after creating new time block
            setTimeout(() => this.app.managers.storage.saveTimesheet(), 500);
        }
        
        this.app.updateDaySummaries();
        console.log('✅ DROP: Completed drop operation');
        
        // Reset processing flag
        this.dragState.isProcessingDrop = false;
    }
    
    /**
     * Clean up any orphaned time blocks that might be left in the DOM
     */
    cleanupOrphanedTimeBlocks() {
        // Find time blocks that are in the DOM but not in the timeBlocks array
        const domTimeBlocks = document.querySelectorAll('.time-block');
        const stateTimeBlocks = this.app.state.timeBlocks || [];
        
        domTimeBlocks.forEach(domBlock => {
            // Check if this DOM block is in the state array
            const isInState = stateTimeBlocks.includes(domBlock);
            
            // If it's not in state and has a dragging class, it might be orphaned
            if (!isInState && (domBlock.classList.contains('dragging') || domBlock.classList.contains('duplicating'))) {
                console.warn('Found orphaned time block, cleaning up:', domBlock);
                domBlock.remove();
            }
        });
        
        // Also clean up any time blocks in state that are no longer in DOM
        this.app.state.timeBlocks = stateTimeBlocks.filter(block => {
            if (block && block.parentNode) {
                return true; // Block is still in DOM
            } else {
                console.warn('Found time block in state but not in DOM, removing from state:', block);
                return false; // Remove from state
            }
        });
    }

    /**
     * Start touch drag operation
     */
    startTouchDrag(timeBlock, touchDragData) {
        this.isDragging = true;
        this.dragState.isDragging = true;
        this.dragState.draggedData = touchDragData;
        
        // Visual feedback for touch drag
        timeBlock.classList.add('dragging');
        timeBlock.style.opacity = '0.7';
        
        // Store globally for touch operations
        window.currentDragData = touchDragData;
    }
    
    /**
     * Check if we're in mobile layout
     */
    isMobileLayout() {
        return window.innerWidth <= 1200;
    }
    
    /**
     * Handle touch move during drag
     */
    handleTouchMove(touch) {
        // Find element under touch point
        let elementBelow = document.elementFromPoint(touch.clientX, touch.clientY);
        
        // In mobile layout, we might need to look deeper for time slots
        if (this.isMobileLayout() && !elementBelow?.closest('.time-slot')) {
            // Try to find time slot by looking at nearby coordinates
            const searchRadius = 20;
            for (let dx = -searchRadius; dx <= searchRadius; dx += 10) {
                for (let dy = -searchRadius; dy <= searchRadius; dy += 10) {
                    const testElement = document.elementFromPoint(
                        touch.clientX + dx, 
                        touch.clientY + dy
                    );
                    const timeSlot = testElement?.closest('.time-slot');
                    if (timeSlot) {
                        elementBelow = testElement;
                        break;
                    }
                }
                if (elementBelow?.closest('.time-slot')) break;
            }
        }
        
        const timeSlot = elementBelow?.closest('.time-slot');
        
        if (timeSlot && this.dragState.draggedData) {
            this.showDragPreview(timeSlot);
        }
    }
    
    /**
     * Handle touch drop
     */
    handleTouchDrop(touch) {
        // Find the drop target
        let elementBelow = document.elementFromPoint(touch.clientX, touch.clientY);
        
        // In mobile layout, we might need to look deeper for time slots
        if (this.isMobileLayout() && !elementBelow?.closest('.time-slot')) {
            // Try to find time slot by looking at nearby coordinates
            const searchRadius = 30;
            for (let dx = -searchRadius; dx <= searchRadius; dx += 15) {
                for (let dy = -searchRadius; dy <= searchRadius; dy += 15) {
                    const testElement = document.elementFromPoint(
                        touch.clientX + dx, 
                        touch.clientY + dy
                    );
                    const timeSlot = testElement?.closest('.time-slot');
                    if (timeSlot) {
                        elementBelow = testElement;
                        break;
                    }
                }
                if (elementBelow?.closest('.time-slot')) break;
            }
        }
        
        const timeSlot = elementBelow?.closest('.time-slot');
        
        if (timeSlot) {
            // Create a synthetic drop event
            const syntheticEvent = {
                preventDefault: () => {},
                currentTarget: timeSlot,
                dataTransfer: {
                    getData: () => JSON.stringify(this.dragState.draggedData)
                }
            };
            
            this.dropTimeBlock(syntheticEvent);
        }
    }
    
    /**
     * End touch drag operation
     */
    endTouchDrag(timeBlock) {
        this.isDragging = false;
        this.dragState.isDragging = false;
        this.dragState.draggedData = null;
        
        // Reset visual state
        timeBlock.classList.remove('dragging');
        timeBlock.style.opacity = '';
        
        this.clearDragPreview();
        this.clearDropZones();
        
        // Clear global data
        window.currentDragData = null;
    }

    /**
     * Setup clone button dragging
     */
    setupCloneDragging(cloneBtn, sourceTimeBlock) {
        cloneBtn.addEventListener('dragstart', (e) => {
            e.stopPropagation(); // Prevent the time block's drag from triggering
            
            cloneBtn.classList.add('dragging');
            
            // Store the source time block data for cloning
            const timeBlockData = {
                project: sourceTimeBlock.dataset.project,
                activity: sourceTimeBlock.dataset.activity,
                projectName: sourceTimeBlock.querySelector('.time-block-header').textContent,
                activityName: sourceTimeBlock.querySelector('.time-block-activity').textContent,
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
}

// Export to global scope
window.DragDropManager = DragDropManager;
