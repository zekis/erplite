// Global variables
let draggedElement = null;
let timeBlocks = [];
let currentWeekStart = null;
let existingTimesheets = [];
let projectColors = {};
let isFullDay = false; // Track if showing full day (0-24) or working hours (8-18)
let currentMobileDayIndex = 0; // Track current day in mobile view (0-6 for Mon-Sun)
let weekDates = []; // Store week dates for mobile navigation

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get data from window object (set by template)
    if (window.timesheetData) {
        currentWeekStart = window.timesheetData.currentWeekStart;
        existingTimesheets = window.timesheetData.existingTimesheets;
        projectColors = window.timesheetData.projectColors;
    }
    
    initializeExistingTimeBlocks();
    setupDragAndDrop();
    setupTimeSlotClicks();
    initializeMobileNavigation();
    setupSwipeGestures();
    updateDaySummaries();
});

function initializeExistingTimeBlocks() {
    let hasEntriesOutsideWorkingHours = false;
    
    existingTimesheets.forEach(timesheet => {
        if (timesheet.check_in_time && timesheet.check_out_time) {
            const startTime = new Date(timesheet.check_in_time);
            const endTime = new Date(timesheet.check_out_time);
            const startHour = startTime.getHours();
            const endHour = endTime.getHours();
            
            // Check if any time entries are outside working hours (8-18)
            if (startHour < 8 || startHour >= 18 || endHour < 8 || endHour > 18) {
                hasEntriesOutsideWorkingHours = true;
            }
            
            createTimeBlock({
                project: timesheet.project,
                task: timesheet.task,
                projectName: timesheet.project_name || timesheet.project,
                taskName: timesheet.task_name || timesheet.task,
                color: projectColors[timesheet.project] || '#6b7280',
                date: timesheet.date,
                startHour: startHour,
                startMinute: startTime.getMinutes(),
                duration: timesheet.duration_hours || 1,
                description: timesheet.description || '',
                id: timesheet.name
            });
        }
    });
    
    // If there are entries outside working hours, force full day view
    if (hasEntriesOutsideWorkingHours) {
        forceFullDayView();
    }
}

function setupDragAndDrop() {
    // Setup drag start for task blocks
    document.querySelectorAll('.task-block').forEach(block => {
        block.addEventListener('dragstart', function(e) {
            draggedElement = this;
            this.classList.add('dragging');
            
            e.dataTransfer.setData('text/plain', JSON.stringify({
                project: this.dataset.project,
                task: this.dataset.task,
                projectName: this.dataset.projectName,
                taskName: this.dataset.taskName,
                color: this.dataset.color
            }));
        });
        
        block.addEventListener('dragend', function() {
            this.classList.remove('dragging');
            draggedElement = null;
        });
    });
}

function allowDrop(event) {
    event.preventDefault();
}

function dragEnter(event) {
    event.preventDefault();
    
    // Show drag preview if we're dragging a time block
    if (dragState.isDragging && dragState.draggedData) {
        showDragPreview(event.currentTarget);
        // Don't add drop-zone class to individual slots when showing preview
    } else {
        // Only add drop-zone for new entries from sidebar
        event.currentTarget.classList.add('drop-zone');
    }
}

function dragLeave(event) {
    // Only clear drop zones for sidebar drags, not for time block drags
    if (!dragState.isDragging) {
        event.currentTarget.classList.remove('drop-zone');
    }
    
    // Don't clear preview here - let dragEnter handle it
    // The preview should persist as we move between time slots
}

function clearDropZones() {
    document.querySelectorAll('.time-slot.drop-zone').forEach(slot => {
        slot.classList.remove('drop-zone');
    });
}

function showDragPreview(timeSlot) {
    // Clear any existing preview
    clearDragPreview();
    
    if (!dragState.draggedData) return;
    
    const dayColumn = timeSlot.closest('.day-column');
    const targetHour = parseInt(timeSlot.dataset.hour);
    const targetMinute = parseInt(timeSlot.dataset.minute || 0);
    const duration = dragState.draggedData.duration;
    const dragOffset = dragState.draggedData.dragOffset || { x: 0, y: 0 };
    
    console.log(`Preview: targetHour=${targetHour}, targetMinute=${targetMinute}, dragOffset.y=${dragOffset.y}, duration=${duration}`);
    
    // Calculate the offset using the same 30-minute snapping as the drop logic
    const offsetInMinutes = Math.round(dragOffset.y / 30) * 30; // Snap to 30-minute intervals
    const targetTotalMinutes = (targetHour * 60 + targetMinute) - offsetInMinutes;
    const adjustedStartHour = Math.max(0, Math.floor(targetTotalMinutes / 60));
    const adjustedStartMinute = Math.max(0, targetTotalMinutes % 60);
    
    console.log(`Preview: offsetInMinutes=${offsetInMinutes}, adjustedStartHour=${adjustedStartHour}, adjustedStartMinute=${adjustedStartMinute}`);
    
    // Calculate position and height (accounting for 30px time slots)
    const startHourOffset = isFullDay ? 0 : 8;
    const previewTop = (adjustedStartHour - startHourOffset) * 60 + adjustedStartMinute;
    const previewHeight = duration * 60;
    
    // Ensure preview doesn't go outside the calendar bounds
    const maxTop = (24 - startHourOffset) * 60 - previewHeight; // Maximum valid top position
    const finalTop = Math.max(0, Math.min(previewTop, maxTop));
    
    console.log(`Preview: previewTop=${previewTop}, finalTop=${finalTop}, previewHeight=${previewHeight}`);
    
    // Create preview element
    const preview = document.createElement('div');
    preview.className = 'drag-preview';
    preview.style.top = `${finalTop}px`;
    preview.style.height = `${previewHeight}px`;
    
    // Add preview content
    preview.innerHTML = `
        <div style="padding: 0.5rem; font-size: 0.75rem; color: #3b82f6; font-weight: 500;">
            ${dragState.draggedData.projectName}<br>
            ${dragState.draggedData.taskName}<br>
            <span style="font-size: 0.625rem;">${duration}h</span>
        </div>
    `;
    
    dayColumn.appendChild(preview);
    dragState.currentPreview = preview;
}

function clearDragPreview() {
    if (dragState.currentPreview) {
        dragState.currentPreview.remove();
        dragState.currentPreview = null;
    }
}

function checkTimeOverlap(dayColumn, startHour, startMinute, duration, excludeBlock = null) {
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

function dropTimeBlock(event) {
    event.preventDefault();
    event.currentTarget.classList.remove('drop-zone');
    clearDragPreview();
    
    const timeSlot = event.currentTarget;
    const dayColumn = timeSlot.closest('.day-column');
    const date = dayColumn.dataset.date;
    const hour = parseInt(timeSlot.dataset.hour);
    const minute = parseInt(timeSlot.dataset.minute || 0);
    
    let taskData;
    try {
        taskData = JSON.parse(event.dataTransfer.getData('text/plain'));
    } catch (e) {
        // Fallback to global data if dataTransfer fails
        taskData = window.currentDragData;
    }
    
    // Use global data as backup if dataTransfer data is incomplete
    if (!taskData || !taskData.dragOffset) {
        taskData = window.currentDragData || taskData;
    }
    
    console.log('Drop taskData:', taskData);
    
    // Calculate the actual placement position based on drag offset with 30-minute precision
    let finalStartHour = hour;
    let finalStartMinute = minute;
    
    if (taskData && taskData.isExistingBlock && taskData.dragOffset) {
        // Calculate offset in 30-minute increments (30px = 0.5 hours)
        const offsetInMinutes = Math.round(taskData.dragOffset.y / 30) * 30; // Snap to 30-minute intervals
        const offsetHours = Math.floor(offsetInMinutes / 60);
        const offsetMinutes = offsetInMinutes % 60;
        
        // Calculate final position using the same logic as preview
        const targetTotalMinutes = (hour * 60 + minute) - offsetInMinutes;
        finalStartHour = Math.max(0, Math.floor(targetTotalMinutes / 60));
        finalStartMinute = Math.max(0, targetTotalMinutes % 60);
        
        console.log(`Drag offset: ${taskData.dragOffset.y}px, offsetInMinutes: ${offsetInMinutes}, finalStartHour: ${finalStartHour}, finalStartMinute: ${finalStartMinute}`);
    }
    
    if (taskData.isExistingBlock) {
        if (taskData.isDuplicate) {
            // Duplicating an existing time block (right-click drag)
            const originalBlock = document.querySelector('.time-block.duplicating');
            
            // Check for overlaps before creating duplicate (don't exclude original since it's a copy)
            const hasOverlap = checkTimeOverlap(dayColumn, finalStartHour, finalStartMinute, taskData.duration);
            
            if (hasOverlap) {
                showToast('Cannot place duplicate here - time slot is already occupied', 'warning');
                return;
            }
            
            // Create the duplicate with preserved data but no ID (new entry)
            const newTimeBlock = createTimeBlock({
                ...taskData,
                date: date,
                startHour: finalStartHour,
                startMinute: finalStartMinute,
                duration: taskData.duration, // Keep original duration
                id: null // Remove ID so it's treated as a new entry
            });
            
            // Select the newly created time block
            if (newTimeBlock) {
                selectTimeBlock(newTimeBlock);
            }
            
            showToast('Time entry duplicated successfully!', 'success');
            // Auto-save after duplicating
            setTimeout(() => saveTimesheet(), 500);
        } else {
            // Moving an existing time block (left-click drag)
            const originalBlock = document.querySelector('.time-block.dragging');
            if (originalBlock) {
                // Temporarily remove the original block from DOM to check for overlaps
                const originalParent = originalBlock.parentNode;
                const originalNextSibling = originalBlock.nextSibling;
                originalBlock.remove();
                
                // Now check for overlap without the original block in the DOM
                const hasOverlapAfterMove = checkTimeOverlap(dayColumn, finalStartHour, finalStartMinute, taskData.duration);
                
                if (hasOverlapAfterMove) {
                    // Restore the original block to its position
                    if (originalNextSibling) {
                        originalParent.insertBefore(originalBlock, originalNextSibling);
                    } else {
                        originalParent.appendChild(originalBlock);
                    }
                    showToast('Cannot move entry here - time slot is already occupied', 'warning');
                    return;
                }
                
                // Remove from timeBlocks array since we're moving it
                timeBlocks = timeBlocks.filter(block => block !== originalBlock);
                // Note: originalBlock is already removed from DOM above
            }
            
            // Create the moved time block with preserved data and calculated position
            createTimeBlock({
                ...taskData,
                date: date,
                startHour: finalStartHour,
                startMinute: finalStartMinute,
                duration: taskData.duration // Keep original duration
            });
            
            showToast('Time entry moved successfully!', 'success');
            // Auto-save after moving
            setTimeout(() => saveTimesheet(), 500);
        }
    } else {
        // Creating new time block from sidebar task
        // Check for overlaps before creating new block
        const hasOverlap = checkTimeOverlap(dayColumn, hour, 0, 1); // Default 1 hour
        
        if (hasOverlap) {
            showToast('Cannot place entry here - time slot is already occupied', 'warning');
            return;
        }
        
        createTimeBlock({
            ...taskData,
            date: date,
            startHour: hour,
            startMinute: 0,
            duration: 1 // Default 1 hour for new entries
        });
    }
    
    updateDaySummaries();
}

function createTimeBlock(data) {
    const dayColumn = document.querySelector(`[data-date="${data.date}"]`);
    if (!dayColumn) return null;
    
    const template = document.getElementById('time-block-template');
    const timeBlock = template.content.cloneNode(true).querySelector('.time-block');
    
    // Set content
    timeBlock.querySelector('.time-block-header').textContent = data.projectName;
    timeBlock.querySelector('.time-block-task').textContent = data.taskName;
    timeBlock.querySelector('.time-block-duration').textContent = `${data.duration}h`;
    
    // Show description if duration is 1.5+ hours and description exists
    const descriptionElement = timeBlock.querySelector('.time-block-description');
    if (data.duration >= 1.5 && data.description && data.description.trim()) {
        descriptionElement.textContent = data.description;
        descriptionElement.style.display = 'block';
    } else {
        descriptionElement.style.display = 'none';
    }
    
    // Set style - adjust for current hour range
    const startHour = isFullDay ? 0 : 8;
    timeBlock.style.setProperty('--project-color', data.color);
    timeBlock.style.top = `${(data.startHour - startHour) * 60 + (data.startMinute || 0)}px`;
    timeBlock.style.height = `${data.duration * 60}px`;
    
    // Add data attributes
    timeBlock.dataset.project = data.project;
    timeBlock.dataset.task = data.task;
    timeBlock.dataset.duration = data.duration;
    timeBlock.dataset.startHour = data.startHour;
    timeBlock.dataset.startMinute = data.startMinute || 0;
    timeBlock.dataset.description = data.description || '';
    if (data.id) timeBlock.dataset.id = data.id;
    
    // Add event listeners
    timeBlock.addEventListener('click', editTimeBlock);
    
    // Make time block draggable
    setupTimeBlockDragging(timeBlock);
    
    // Setup resize handles
    setupResizeHandles(timeBlock);
    
    dayColumn.appendChild(timeBlock);
    timeBlocks.push(timeBlock);
    
    return timeBlock; // Return the created time block
}

// Global drag state
let dragState = {
    isDragging: false,
    draggedData: null,
    dragOffset: { x: 0, y: 0 },
    currentPreview: null
};

function setupTimeBlockDragging(timeBlock) {
    let dragStartX = 0;
    let dragStartY = 0;
    let originalTimeBlock = null;
    let isDuplicateMode = false;
    
    // Make the time block draggable (but not the resize handles)
    timeBlock.draggable = true;
    
    // Track mouse down for drag detection
    timeBlock.addEventListener('mousedown', function(e) {
        // Don't handle if clicking on resize handles or clone buttons
        if (e.target.classList.contains('resize-handle') || 
            e.target.classList.contains('clone-btn')) {
            return;
        }
        
        isDuplicateMode = e.button === 2; // Right mouse button
        dragStartTime = Date.now();
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        
        // Calculate drag offset relative to the time block
        const rect = this.getBoundingClientRect();
        dragState.dragOffset.x = e.clientX - rect.left;
        dragState.dragOffset.y = e.clientY - rect.top;
    });
    
    timeBlock.addEventListener('dragstart', function(e) {
        // Don't drag if we're clicking on resize handles or clone buttons
        if (e.target.classList.contains('resize-handle') || 
            e.target.classList.contains('clone-btn')) {
            e.preventDefault();
            return;
        }
        
        isDragging = true;
        dragState.isDragging = true;
        originalTimeBlock = this;
        
        // Store the time block data for transfer
        const dayColumn = this.closest('.day-column');
        
        // Get the correct project color from the project colors or CSS variable
        let projectColor = projectColors[this.dataset.project] || '#6b7280';
        
        const timeBlockData = {
            project: this.dataset.project,
            task: this.dataset.task,
            projectName: this.querySelector('.time-block-header').textContent,
            taskName: this.querySelector('.time-block-task').textContent,
            color: projectColor,
            duration: parseFloat(this.dataset.duration),
            startHour: parseInt(this.dataset.startHour),
            startMinute: parseInt(this.dataset.startMinute || 0),
            description: this.dataset.description || '',
            id: this.dataset.id,
            isExistingBlock: true,
            isDuplicate: isDuplicateMode,
            originalParent: this.parentNode,
            originalNextSibling: this.nextSibling,
            height: this.offsetHeight,
            dragOffset: dragState.dragOffset
        };
        
        dragState.draggedData = timeBlockData;
        
        // Add different visual feedback for duplicate vs move
        if (isDuplicateMode) {
            this.classList.add('duplicating');
            this.style.opacity = '0.7';
        } else {
            this.classList.add('dragging');
            // For moving, temporarily remove from DOM so drop zones show everywhere
            setTimeout(() => {
                if (this.parentNode) {
                    this.remove();
                }
            }, 0);
        }
        
        // Store drag data globally as well as in dataTransfer (backup)
        window.currentDragData = timeBlockData;
        
        e.dataTransfer.setData('text/plain', JSON.stringify(timeBlockData));
        e.dataTransfer.effectAllowed = isDuplicateMode ? 'copy' : 'move';
    });
    
    timeBlock.addEventListener('dragend', function() {
        this.classList.remove('dragging', 'duplicating');
        this.style.opacity = '';
        originalTimeBlock = null;
        isDuplicateMode = false;
        
        // Clear drag state and preview
        dragState.isDragging = false;
        dragState.draggedData = null;
        clearDragPreview();
        
        // Reset drag state after a short delay
        setTimeout(() => {
            isDragging = false;
        }, 100);
    });
}

function setupResizeHandles(timeBlock) {
    const topHandle = timeBlock.querySelector('.resize-handle.top');
    const bottomHandle = timeBlock.querySelector('.resize-handle.bottom');
    
    let isResizing = false;
    let startY = 0;
    let startHeight = 0;
    let startTop = 0;
    let activeHandle = null;
    
    function startResize(e, handle) {
        isResizing = true;
        activeHandle = handle;
        startY = e.clientY;
        startHeight = timeBlock.offsetHeight;
        startTop = timeBlock.offsetTop;
        
        document.addEventListener('mousemove', resize);
        document.addEventListener('mouseup', stopResize);
        e.preventDefault();
        e.stopPropagation();
    }
    
    function resize(e) {
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
    }
    
    function stopResize() {
        isResizing = false;
        activeHandle = null;
        document.removeEventListener('mousemove', resize);
        document.removeEventListener('mouseup', stopResize);
        updateDaySummaries();
        
        // Auto-save after resizing
        setTimeout(() => saveTimesheet(), 500);
    }
    
    topHandle.addEventListener('mousedown', (e) => startResize(e, topHandle));
    bottomHandle.addEventListener('mousedown', (e) => startResize(e, bottomHandle));
}

let currentEditingBlock = null;
let selectedTimeBlock = null;
let isDragging = false;
let dragStartTime = 0;
let lastClickTime = 0;
let lastClickedBlock = null;

function editTimeBlock(event) {
    event.stopPropagation();
    
    // Check if this was a drag operation
    if (isDragging) {
        isDragging = false;
        return;
    }
    
    const timeBlock = event.currentTarget;
    const clickTime = Date.now();
    
    // Check for double-click (within 400ms of previous click on same block)
    if (lastClickedBlock === timeBlock && clickTime - lastClickTime < 400) {
        // Double-click detected - open edit modal
        currentEditingBlock = timeBlock;
        populateEditModal(currentEditingBlock);
        document.getElementById('editTimeBlockModal').style.display = 'block';
        
        // Reset double-click tracking
        lastClickTime = 0;
        lastClickedBlock = null;
        return;
    }
    
    // Single click - handle selection if it's a quick click (not a drag)
    if (clickTime - dragStartTime < 200) {
        selectTimeBlock(timeBlock);
        
        // Track for potential double-click
        lastClickTime = clickTime;
        lastClickedBlock = timeBlock;
        return;
    }
    
    // Reset double-click tracking for long clicks
    lastClickTime = 0;
    lastClickedBlock = null;
}

function selectTimeBlock(timeBlock) {
    // Clear previous selection
    if (selectedTimeBlock) {
        selectedTimeBlock.classList.remove('selected');
    }
    
    // Select new block
    selectedTimeBlock = timeBlock;
    timeBlock.classList.add('selected');
    
    // Setup clone button event listeners
    setupCloneButtons(timeBlock);
    
    // Hide selection when clicking elsewhere
    document.addEventListener('click', clearSelection, { once: true });
}

function clearSelection(event) {
    // Don't clear if clicking on the selected block or its controls
    if (selectedTimeBlock && (
        selectedTimeBlock.contains(event.target) ||
        event.target.classList.contains('clone-btn')
    )) {
        // Re-add the listener for next click
        document.addEventListener('click', clearSelection, { once: true });
        return;
    }
    
    if (selectedTimeBlock) {
        selectedTimeBlock.classList.remove('selected');
        selectedTimeBlock = null;
    }
}

function setupCloneButtons(timeBlock) {
    // Setup all control buttons in the unified control bar
    setupControlButtons(timeBlock);
}

function setupControlButtons(timeBlock) {
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
            openEditModal(timeBlock);
        });
    }
    
    if (newCloneBtn) {
        setupCloneDragging(newCloneBtn, timeBlock);
    }
    
    if (newExpandBtn) {
        newExpandBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            adjustDuration(timeBlock, 0.5); // Expand by 30 minutes
        });
    }
    
    if (newShrinkBtn) {
        newShrinkBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            adjustDuration(timeBlock, -0.5); // Shrink by 30 minutes
        });
    }
    
    if (newDeleteBtn) {
        newDeleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteTimeBlockDirect(timeBlock);
        });
    }
}

function setupCloneDragging(cloneBtn, sourceTimeBlock) {
    cloneBtn.addEventListener('dragstart', function(e) {
        e.stopPropagation(); // Prevent the time block's drag from triggering
        
        cloneBtn.classList.add('dragging');
        
        // Store the source time block data for cloning
        const timeBlockData = {
            project: sourceTimeBlock.dataset.project,
            task: sourceTimeBlock.dataset.task,
            projectName: sourceTimeBlock.querySelector('.time-block-header').textContent,
            taskName: sourceTimeBlock.querySelector('.time-block-task').textContent,
            color: sourceTimeBlock.style.backgroundColor,
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
    
    cloneBtn.addEventListener('dragend', function() {
        cloneBtn.classList.remove('dragging');
    });
}

function setupSideButtons(timeBlock) {
    const editBtn = timeBlock.querySelector('.edit-btn');
    const expandBtn = timeBlock.querySelector('.expand-btn');
    const shrinkBtn = timeBlock.querySelector('.shrink-btn');
    
    // Remove existing listeners
    editBtn.replaceWith(editBtn.cloneNode(true));
    expandBtn.replaceWith(expandBtn.cloneNode(true));
    shrinkBtn.replaceWith(shrinkBtn.cloneNode(true));
    
    // Get fresh references
    const newEditBtn = timeBlock.querySelector('.edit-btn');
    const newExpandBtn = timeBlock.querySelector('.expand-btn');
    const newShrinkBtn = timeBlock.querySelector('.shrink-btn');
    
    newEditBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openEditModal(timeBlock);
    });
    
    newExpandBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        adjustDuration(timeBlock, 0.5); // Expand by 30 minutes
    });
    
    newShrinkBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        adjustDuration(timeBlock, -0.5); // Shrink by 30 minutes
    });
}

function setupDeleteButton(timeBlock) {
    const deleteBtn = timeBlock.querySelector('.delete-btn');
    
    // Remove existing listener
    deleteBtn.replaceWith(deleteBtn.cloneNode(true));
    
    // Get fresh reference
    const newDeleteBtn = timeBlock.querySelector('.delete-btn');
    
    newDeleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteTimeBlockDirect(timeBlock);
    });
}

function deleteTimeBlockDirect(timeBlock) {
    if (confirm('Are you sure you want to delete this time entry?')) {
        const entryId = timeBlock.dataset.id;
        
        if (entryId && entryId !== 'null') {
            // Delete from database if it has an ID
            frappe.call({
                method: 'erplite.projects.api.delete_timesheet_entry',
                args: { entry_id: entryId },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        // Remove from frontend after successful deletion
                        timeBlocks = timeBlocks.filter(block => block !== timeBlock);
                        timeBlock.remove();
                        updateDaySummaries();
                        showToast('Time entry deleted successfully!', 'success');
                    } else {
                        showToast('Error: ' + (r.message.message || 'Failed to delete time entry'), 'error');
                    }
                },
                error: function(err) {
                    console.error('Error deleting time entry:', err);
                    showToast('Error: Failed to delete time entry', 'error');
                }
            });
        } else {
            // Just remove from frontend if it's a new entry without ID
            timeBlocks = timeBlocks.filter(block => block !== timeBlock);
            timeBlock.remove();
            updateDaySummaries();
            showToast('Time entry deleted', 'success');
        }
    }
}

function openEditModal(timeBlock) {
    currentEditingBlock = timeBlock;
    populateEditModal(currentEditingBlock);
    document.getElementById('editTimeBlockModal').style.display = 'block';
}

function adjustDuration(timeBlock, change) {
    const currentDuration = parseFloat(timeBlock.dataset.duration);
    const newDuration = Math.max(0.5, currentDuration + change); // Minimum 30 minutes
    
    // Check for overlaps with the new duration, excluding the current block
    const dayColumn = timeBlock.closest('.day-column');
    const startHour = parseInt(timeBlock.dataset.startHour);
    const startMinute = parseInt(timeBlock.dataset.startMinute || 0);
    
    const hasOverlap = checkTimeOverlap(dayColumn, startHour, startMinute, newDuration, timeBlock);
    
    if (hasOverlap) {
        const action = change > 0 ? 'expand' : 'shrink';
        showToast(`Cannot ${action} - would overlap with another entry`, 'warning');
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
    
    updateDaySummaries();
    
    // Auto-save after adjusting
    setTimeout(() => saveTimesheet(), 500);
    
    const action = change > 0 ? 'expanded' : 'shrunk';
    showToast(`Duration ${action} to ${newDuration}h`, 'success');
}

function cloneTimeBlock(sourceBlock, direction) {
    const currentDayColumn = sourceBlock.closest('.day-column');
    const allDayColumns = Array.from(document.querySelectorAll('.day-column'));
    const currentIndex = allDayColumns.indexOf(currentDayColumn);
    const targetIndex = currentIndex + direction;
    
    if (targetIndex < 0 || targetIndex >= allDayColumns.length) {
        showToast('Cannot clone beyond week boundaries', 'warning');
        return;
    }
    
    const targetDayColumn = allDayColumns[targetIndex];
    const targetDate = targetDayColumn.dataset.date;
    
    const startHour = parseInt(sourceBlock.dataset.startHour);
    const startMinute = parseInt(sourceBlock.dataset.startMinute || 0);
    const duration = parseFloat(sourceBlock.dataset.duration);
    
    // Check for overlaps in target day
    const hasOverlap = checkTimeOverlap(targetDayColumn, startHour, startMinute, duration);
    
    if (hasOverlap) {
        const direction_text = direction === -1 ? 'previous' : 'next';
        showToast(`Cannot clone to ${direction_text} day - time slot is already occupied`, 'warning');
        return;
    }
    
    // Create clone with same data
    const cloneData = {
        project: sourceBlock.dataset.project,
        task: sourceBlock.dataset.task,
        projectName: sourceBlock.querySelector('.time-block-header').textContent,
        taskName: sourceBlock.querySelector('.time-block-task').textContent,
        color: sourceBlock.style.backgroundColor,
        date: targetDate,
        startHour: startHour,
        startMinute: startMinute,
        duration: duration,
        description: sourceBlock.dataset.description || ''
    };
    
    createTimeBlock(cloneData);
    updateDaySummaries();
    
    const direction_text = direction === -1 ? 'previous' : 'next';
    showToast(`Time entry cloned to ${direction_text} day!`, 'success');
    
    // Auto-save after cloning
    setTimeout(() => saveTimesheet(), 500);
}

function populateEditModal(timeBlock) {
    const dayColumn = timeBlock.closest('.day-column');
    const date = dayColumn.dataset.date;
    const startHour = parseInt(timeBlock.dataset.startHour);
    const startMinute = parseInt(timeBlock.dataset.startMinute || 0);
    const duration = parseFloat(timeBlock.dataset.duration);
    
    // Calculate end time
    const endHour = Math.floor(startHour + duration);
    const endMinute = Math.round((startHour + duration - endHour) * 60);
    
    // Handle timesheet entry link
    const timesheetEntryLink = document.getElementById('timesheetEntryLink');
    const openTimesheetEntry = document.getElementById('openTimesheetEntry');
    const entryId = timeBlock.dataset.id;
    
    if (entryId && entryId !== 'null') {
        // Show link for existing entries
        timesheetEntryLink.style.display = 'block';
        openTimesheetEntry.href = `/app/timesheet-entry/${entryId}`;
    } else {
        // Hide link for new entries
        timesheetEntryLink.style.display = 'none';
    }
    
    // Populate project dropdown
    const projectSelect = document.getElementById('editProject');
    projectSelect.innerHTML = '<option value="">Select Project</option>';
    
    // Get projects from sidebar
    document.querySelectorAll('.project-group').forEach(projectGroup => {
        const projectId = projectGroup.dataset.project;
        const projectName = projectGroup.querySelector('.project-name').textContent;
        const option = document.createElement('option');
        option.value = projectId;
        option.textContent = projectName;
        if (projectId === timeBlock.dataset.project) {
            option.selected = true;
        }
        projectSelect.appendChild(option);
    });
    
    // Update task options based on selected project
    updateTaskOptions();
    
    // Set current task
    document.getElementById('editTask').value = timeBlock.dataset.task;
    
    // Set times
    document.getElementById('editStartTime').value = 
        `${String(startHour).padStart(2, '0')}:${String(startMinute).padStart(2, '0')}`;
    document.getElementById('editEndTime').value = 
        `${String(endHour).padStart(2, '0')}:${String(endMinute).padStart(2, '0')}`;
    
    // Set description (if available)
    document.getElementById('editDescription').value = timeBlock.dataset.description || '';
}

function updateTaskOptions() {
    const projectSelect = document.getElementById('editProject');
    const taskSelect = document.getElementById('editTask');
    const selectedProject = projectSelect.value;
    
    taskSelect.innerHTML = '<option value="">Select Task</option>';
    
    if (selectedProject) {
        const projectGroup = document.querySelector(`[data-project="${selectedProject}"]`);
        if (projectGroup) {
            projectGroup.querySelectorAll('.task-block').forEach(taskBlock => {
                const taskId = taskBlock.dataset.task;
                const taskName = taskBlock.dataset.taskName;
                const option = document.createElement('option');
                option.value = taskId;
                option.textContent = taskName;
                taskSelect.appendChild(option);
            });
        }
    }
}

function closeEditModal() {
    document.getElementById('editTimeBlockModal').style.display = 'none';
    currentEditingBlock = null;
}

function saveTimeBlockEdit() {
    if (!currentEditingBlock) return;
    
    const projectSelect = document.getElementById('editProject');
    const taskSelect = document.getElementById('editTask');
    const startTime = document.getElementById('editStartTime').value;
    const endTime = document.getElementById('editEndTime').value;
    const description = document.getElementById('editDescription').value;
    
    if (!projectSelect.value || !taskSelect.value || !startTime || !endTime) {
        alert('Please fill in all required fields');
        return;
    }
    
    // Calculate duration
    const [startHour, startMinute] = startTime.split(':').map(Number);
    const [endHour, endMinute] = endTime.split(':').map(Number);
    const duration = (endHour + endMinute/60) - (startHour + startMinute/60);
    
    if (duration <= 0) {
        alert('End time must be after start time');
        return;
    }
    
    // Get project and task names
    const projectName = projectSelect.options[projectSelect.selectedIndex].text;
    const taskName = taskSelect.options[taskSelect.selectedIndex].text;
    
    // Get project color
    const projectGroup = document.querySelector(`[data-project="${projectSelect.value}"]`);
    const projectColor = projectGroup ? 
        getComputedStyle(projectGroup.querySelector('.project-color')).backgroundColor : 
        '#6b7280';
    
    // Update the time block
    currentEditingBlock.dataset.project = projectSelect.value;
    currentEditingBlock.dataset.task = taskSelect.value;
    currentEditingBlock.dataset.startHour = startHour;
    currentEditingBlock.dataset.startMinute = startMinute;
    currentEditingBlock.dataset.duration = duration;
    currentEditingBlock.dataset.description = description;
    
    // Update visual content
    currentEditingBlock.querySelector('.time-block-header').textContent = projectName;
    currentEditingBlock.querySelector('.time-block-task').textContent = taskName;
    currentEditingBlock.querySelector('.time-block-duration').textContent = `${duration.toFixed(1)}h`;
    
    // Update description visibility based on new duration
    const descriptionElement = currentEditingBlock.querySelector('.time-block-description');
    if (duration >= 1.5 && description && description.trim()) {
        descriptionElement.textContent = description;
        descriptionElement.style.display = 'block';
    } else {
        descriptionElement.style.display = 'none';
    }
    
    // Update visual style
    const startHourOffset = isFullDay ? 0 : 8;
    currentEditingBlock.style.setProperty('--project-color', projectColor);
    currentEditingBlock.style.top = `${(startHour - startHourOffset) * 60 + startMinute}px`;
    currentEditingBlock.style.height = `${duration * 60}px`;
    
    // Close modal and update summaries
    closeEditModal();
    updateDaySummaries();
    
    // Immediately save to backend
    saveTimesheet();
    
    showToast('Time entry updated successfully!', 'success');
}

function deleteTimeBlock() {
    if (!currentEditingBlock) return;
    
    if (confirm('Are you sure you want to delete this time entry?')) {
        currentEditingBlock.remove();
        timeBlocks = timeBlocks.filter(block => block !== currentEditingBlock);
        closeEditModal();
        updateDaySummaries();
        showToast('Time entry deleted', 'success');
    }
}

let contextMenuTarget = null;

function showTimeBlockMenu(event) {
    event.preventDefault();
    event.stopPropagation();
    
    contextMenuTarget = event.currentTarget;
    const contextMenu = document.getElementById('contextMenu');
    
    // Position the context menu at the mouse cursor
    contextMenu.style.left = `${event.pageX}px`;
    contextMenu.style.top = `${event.pageY}px`;
    contextMenu.style.display = 'block';
    
    // Hide context menu when clicking elsewhere
    document.addEventListener('click', hideContextMenu);
}

function hideContextMenu() {
    const contextMenu = document.getElementById('contextMenu');
    contextMenu.style.display = 'none';
    contextMenuTarget = null;
    document.removeEventListener('click', hideContextMenu);
}

function editFromContext() {
    if (contextMenuTarget) {
        hideContextMenu();
        // Trigger the edit modal
        currentEditingBlock = contextMenuTarget;
        populateEditModal(currentEditingBlock);
        document.getElementById('editTimeBlockModal').style.display = 'block';
    }
}

function deleteFromContext() {
    console.log('deleteFromContext called, contextMenuTarget:', contextMenuTarget);
    
    if (!contextMenuTarget) {
        console.error('contextMenuTarget is null');
        hideContextMenu();
        showToast('Error: No time entry selected', 'error');
        return;
    }
    
    if (!contextMenuTarget.parentNode) {
        console.error('contextMenuTarget has no parent node');
        hideContextMenu();
        showToast('Error: Time entry no longer exists', 'error');
        return;
    }
    
    // Store a local reference before hiding the context menu
    const targetElement = contextMenuTarget;
    hideContextMenu(); // This sets contextMenuTarget to null
    
    if (confirm('Are you sure you want to delete this time entry?')) {
        try {
            // Remove from timeBlocks array first
            const originalLength = timeBlocks.length;
            timeBlocks = timeBlocks.filter(block => block !== targetElement);
            console.log(`Removed from timeBlocks array: ${originalLength} -> ${timeBlocks.length}`);
            
            // Then remove from DOM using our local reference
            targetElement.remove();
            console.log('Successfully removed from DOM');
            
            updateDaySummaries();
            showToast('Time entry deleted', 'success');
            // Auto-save after deleting
            setTimeout(() => saveTimesheet(), 500);
        } catch (error) {
            console.error('Error deleting time entry:', error);
            showToast('Error: Failed to delete time entry', 'error');
        }
    }
}

function updateDaySummaries() {
    document.querySelectorAll('.day-column').forEach(dayColumn => {
        const blocks = dayColumn.querySelectorAll('.time-block');
        let totalHours = 0;
        
        blocks.forEach(block => {
            totalHours += parseFloat(block.dataset.duration || 0);
        });
        
        const summary = dayColumn.querySelector('.total-hours');
        if (summary) {
            summary.textContent = `${totalHours.toFixed(1)}h`;
        }
    });
}

function toggleProject(projectName) {
    const projectGroup = document.querySelector(`[data-project="${projectName}"]`);
    if (projectGroup) {
        projectGroup.classList.toggle('collapsed');
    }
}

function changeWeek(direction) {
    // Ensure we have a valid currentWeekStart
    if (!currentWeekStart) {
        console.error('currentWeekStart not initialized');
        return;
    }
    
    console.log('Current week start:', currentWeekStart);
    console.log('Direction:', direction);
    
    const currentDate = new Date(currentWeekStart);
    currentDate.setDate(currentDate.getDate() + (direction * 7));
    
    const newWeekStart = currentDate.toISOString().split('T')[0];
    console.log('New week start:', newWeekStart);
    
    window.location.href = `/timesheet-calendar?week=${newWeekStart}`;
}

function clearWeek() {
    if (confirm('Clear all time entries for this week?')) {
        timeBlocks.forEach(block => block.remove());
        timeBlocks = [];
        updateDaySummaries();
    }
}

function saveTimesheet() {
    const entries = [];
    
    // Clean up timeBlocks array - remove any null or detached elements
    timeBlocks = timeBlocks.filter(block => {
        return block && block.parentNode && block.dataset;
    });
    
    timeBlocks.forEach(block => {
        // Double check the block is still valid
        if (!block || !block.parentNode || !block.dataset) {
            return; // Skip invalid blocks
        }
        
        const dayColumn = block.closest('.day-column');
        if (!dayColumn) {
            return; // Skip blocks not in a day column
        }
        
        const date = dayColumn.dataset.date;
        const startHour = parseInt(block.dataset.startHour);
        const startMinute = parseInt(block.dataset.startMinute || 0);
        const duration = parseFloat(block.dataset.duration);
        
        // Generate a temporary ID for new entries if they don't have one
        let tempId = block.dataset.tempId;
        if (!tempId && (!block.dataset.id || block.dataset.id === 'null')) {
            tempId = 'temp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            block.dataset.tempId = tempId;
        }
        
        entries.push({
            id: block.dataset.id || null,
            temp_id: tempId,
            project: block.dataset.project,
            task: block.dataset.task,
            date: date,
            start_time: `${String(startHour).padStart(2, '0')}:${String(startMinute).padStart(2, '0')}`,
            duration: duration,
            description: block.dataset.description || ''
        });
    });
    
    frappe.call({
        method: 'erplite.projects.api.save_timesheet_entries',
        args: { entries: entries },
        callback: function(r) {
            if (r.message && r.message.success) {
                // Update time blocks with new IDs from the server
                if (r.message.entries) {
                    r.message.entries.forEach(savedEntry => {
                        if (savedEntry.temp_id) {
                            // Find the time block with this temp_id and update it with the real ID
                            const timeBlock = timeBlocks.find(block => block.dataset.tempId === savedEntry.temp_id);
                            if (timeBlock) {
                                timeBlock.dataset.id = savedEntry.id;
                                // Remove temp_id since we now have a real ID
                                delete timeBlock.dataset.tempId;
                            }
                        }
                    });
                }
                showToast('Timesheet saved successfully!', 'success');
            } else {
                showToast('Error saving timesheet: ' + (r.message.message || 'Unknown error'), 'error');
            }
        },
        error: function(err) {
            console.error('Error saving timesheet:', err);
            showToast('Error: Failed to save timesheet', 'error');
        }
    });
}

// Quick time entry functions
function addQuickTime(hours) {
    // Add a quick time entry for the specified hours
    const today = new Date().toISOString().split('T')[0];
    const currentHour = new Date().getHours();
    
    // Find first available project/task
    const firstTaskBlock = document.querySelector('.task-block');
    if (!firstTaskBlock) {
        alert('No tasks available. Please create a project and task first.');
        return;
    }
    
    const taskData = {
        project: firstTaskBlock.dataset.project,
        task: firstTaskBlock.dataset.task,
        projectName: firstTaskBlock.dataset.projectName,
        taskName: firstTaskBlock.dataset.taskName,
        color: firstTaskBlock.dataset.color,
        date: today,
        startHour: Math.max(8, currentHour),
        startMinute: 0,
        duration: hours
    };
    
    createTimeBlock(taskData);
    updateDaySummaries();
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + S to save
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveTimesheet();
    }
    
    // Ctrl/Cmd + 1-4 for quick time entries
    if ((e.ctrlKey || e.metaKey) && ['1', '2', '3', '4'].includes(e.key)) {
        e.preventDefault();
        const hours = parseInt(e.key);
        addQuickTime(hours);
    }
});

// Toast notification function
function showToast(message, type = 'success') {
    // Remove any existing toast
    const existingToast = document.querySelector('.toast-notification');
    if (existingToast) {
        existingToast.remove();
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.textContent = message;
    
    // Add to page
    document.body.appendChild(toast);
    
    // Show toast with animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Hide and remove toast after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

function forceFullDayView() {
    isFullDay = true;
    const button = document.getElementById('hourToggle');
    
    // Update button text and disable it
    button.textContent = 'Full Day (Required)';
    button.disabled = true;
    button.title = 'Full day view is required because there are time entries outside working hours (8 AM - 6 PM)';
    
    // Rebuild calendar to show full day
    rebuildCalendar(0, 24); // 0-24 hours
    
    // Show notification to user
    showToast('Switched to full day view - time entries exist outside working hours', 'info');
}

function toggleHourRange() {
    // Don't allow toggle if button is disabled
    const button = document.getElementById('hourToggle');
    if (button.disabled) {
        return;
    }
    
    isFullDay = !isFullDay;
    
    if (isFullDay) {
        button.textContent = 'Show Working Hours';
        rebuildCalendar(0, 24); // 0-24 hours
    } else {
        button.textContent = 'Show Full Day';
        rebuildCalendar(8, 18); // 8-18 hours (working hours)
    }
}

function rebuildCalendar(startHour, endHour) {
    // Store existing time blocks data
    const existingBlocks = [];
    timeBlocks.forEach(block => {
        const dayColumn = block.closest('.day-column');
        existingBlocks.push({
            project: block.dataset.project,
            task: block.dataset.task,
            projectName: block.querySelector('.time-block-header').textContent,
            taskName: block.querySelector('.time-block-task').textContent,
            color: block.style.backgroundColor,
            date: dayColumn.dataset.date,
            startHour: parseInt(block.dataset.startHour),
            startMinute: parseInt(block.dataset.startMinute || 0),
            duration: parseFloat(block.dataset.duration),
            id: block.dataset.id
        });
    });
    
    // Clear existing calendar
    document.querySelectorAll('.day-column').forEach(dayColumn => {
        // Remove all time slots and time blocks
        dayColumn.querySelectorAll('.time-slot, .time-block').forEach(el => el.remove());
        
        // Rebuild time labels
        const timeLabels = dayColumn.querySelector('.time-labels');
        timeLabels.innerHTML = '';
        for (let hour = startHour; hour < endHour; hour++) {
            const timeLabel = document.createElement('div');
            timeLabel.className = 'time-label';
            timeLabel.textContent = `${hour}:00`;
            timeLabels.appendChild(timeLabel);
        }
        
        // Rebuild time slots with 30-minute granularity
        const daySummary = dayColumn.querySelector('.day-summary');
        for (let hour = startHour; hour < endHour; hour++) {
            // Create two 30-minute slots per hour
            for (let halfHour = 0; halfHour < 2; halfHour++) {
                const timeSlot = document.createElement('div');
                timeSlot.className = 'time-slot';
                timeSlot.dataset.hour = hour;
                timeSlot.dataset.minute = halfHour * 30;
                timeSlot.style.height = '30px'; // Half the normal height
                timeSlot.setAttribute('ondrop', 'dropTimeBlock(event)');
                timeSlot.setAttribute('ondragover', 'allowDrop(event)');
                timeSlot.setAttribute('ondragenter', 'dragEnter(event)');
                timeSlot.setAttribute('ondragleave', 'dragLeave(event)');
                dayColumn.insertBefore(timeSlot, daySummary);
            }
        }
    });
    
    // Clear timeBlocks array
    timeBlocks = [];
    
    // Recreate time blocks that are within the new hour range
    existingBlocks.forEach(blockData => {
        if (blockData.startHour >= startHour && blockData.startHour < endHour) {
            // Adjust positioning for new hour range
            const adjustedBlockData = {
                ...blockData,
                startHour: blockData.startHour
            };
            createTimeBlockWithRange(adjustedBlockData, startHour);
        }
    });
    
    updateDaySummaries();
}

function createTimeBlockWithRange(data, startHour) {
    const dayColumn = document.querySelector(`[data-date="${data.date}"]`);
    if (!dayColumn) return;
    
    const template = document.getElementById('time-block-template');
    const timeBlock = template.content.cloneNode(true).querySelector('.time-block');
    
    // Set content
    timeBlock.querySelector('.time-block-header').textContent = data.projectName;
    timeBlock.querySelector('.time-block-task').textContent = data.taskName;
    timeBlock.querySelector('.time-block-duration').textContent = `${data.duration}h`;
    
    // Set style with adjusted positioning
    timeBlock.style.backgroundColor = data.color;
    timeBlock.style.top = `${(data.startHour - startHour) * 60 + (data.startMinute || 0)}px`;
    timeBlock.style.height = `${data.duration * 60}px`;
    
    // Add data attributes
    timeBlock.dataset.project = data.project;
    timeBlock.dataset.task = data.task;
    timeBlock.dataset.duration = data.duration;
    timeBlock.dataset.startHour = data.startHour;
    timeBlock.dataset.startMinute = data.startMinute || 0;
    if (data.id) timeBlock.dataset.id = data.id;
    
    // Add event listeners
    timeBlock.addEventListener('click', editTimeBlock);
    timeBlock.addEventListener('contextmenu', showTimeBlockMenu);
    
    // Make time block draggable
    setupTimeBlockDragging(timeBlock);
    
    // Setup resize handles
    setupResizeHandles(timeBlock);
    
    dayColumn.appendChild(timeBlock);
    timeBlocks.push(timeBlock);
}

// Quick Entry Functions
let quickEntryData = {
    selectedProject: null,
    selectedTask: null,
    targetTimeSlot: null,
    targetDate: null,
    targetHour: null
};

function setupTimeSlotClicks() {
    // Add click listeners to all time slots
    document.querySelectorAll('.time-slot').forEach(timeSlot => {
        timeSlot.addEventListener('click', function(e) {
            // Only show quick entry if the time slot is empty
            if (!this.querySelector('.time-block')) {
                showQuickEntry(this);
            }
        });
    });
}

function showQuickEntry(timeSlot) {
    const dayColumn = timeSlot.closest('.day-column');
    quickEntryData.targetTimeSlot = timeSlot;
    quickEntryData.targetDate = dayColumn.dataset.date;
    quickEntryData.targetHour = parseInt(timeSlot.dataset.hour);
    quickEntryData.selectedProject = null;
    quickEntryData.selectedTask = null;
    
    populateQuickEntryProjects();
    document.getElementById('quickEntryPopup').style.display = 'block';
}

function populateQuickEntryProjects() {
    const projectList = document.getElementById('quickProjectList');
    projectList.innerHTML = '';
    
    // Get all projects from sidebar
    document.querySelectorAll('.project-group').forEach(projectGroup => {
        const projectId = projectGroup.dataset.project;
        const projectName = projectGroup.querySelector('.project-name').textContent;
        const projectColor = getComputedStyle(projectGroup.querySelector('.project-color')).backgroundColor;
        
        const projectItem = document.createElement('div');
        projectItem.className = 'quick-entry-item';
        projectItem.dataset.project = projectId;
        projectItem.innerHTML = `
            <div class="quick-entry-item-color" style="background-color: ${projectColor}"></div>
            <span>${projectName}</span>
        `;
        
        projectItem.addEventListener('click', function() {
            selectQuickEntryProject(this, projectId, projectName, projectColor);
        });
        
        projectList.appendChild(projectItem);
    });
    
    // Clear task list
    document.getElementById('quickTaskList').innerHTML = '<div style="padding: 1rem; text-align: center; color: #64748b;">Select a project first</div>';
    document.getElementById('createQuickEntryBtn').disabled = true;
}

function selectQuickEntryProject(projectElement, projectId, projectName, projectColor) {
    // Clear previous selection
    document.querySelectorAll('#quickProjectList .quick-entry-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    // Select current project
    projectElement.classList.add('selected');
    quickEntryData.selectedProject = {
        id: projectId,
        name: projectName,
        color: projectColor
    };
    
    // Populate tasks for selected project
    populateQuickEntryTasks(projectId);
}

function populateQuickEntryTasks(projectId) {
    const taskList = document.getElementById('quickTaskList');
    taskList.innerHTML = '';
    
    // Find the project group and get its tasks
    const projectGroup = document.querySelector(`[data-project="${projectId}"]`);
    if (projectGroup) {
        const tasks = projectGroup.querySelectorAll('.task-block');
        
        if (tasks.length === 0) {
            taskList.innerHTML = '<div style="padding: 1rem; text-align: center; color: #64748b;">No tasks available for this project</div>';
            return;
        }
        
        tasks.forEach(taskBlock => {
            const taskId = taskBlock.dataset.task;
            const taskName = taskBlock.dataset.taskName;
            
            const taskItem = document.createElement('div');
            taskItem.className = 'quick-entry-item';
            taskItem.dataset.task = taskId;
            taskItem.innerHTML = `
                <div class="quick-entry-item-color" style="background-color: ${quickEntryData.selectedProject.color}"></div>
                <span>${taskName}</span>
            `;
            
            taskItem.addEventListener('click', function() {
                selectQuickEntryTask(this, taskId, taskName);
            });
            
            taskList.appendChild(taskItem);
        });
    }
    
    // Reset task selection and disable create button
    quickEntryData.selectedTask = null;
    document.getElementById('createQuickEntryBtn').disabled = true;
}

function selectQuickEntryTask(taskElement, taskId, taskName) {
    // Clear previous selection
    document.querySelectorAll('#quickTaskList .quick-entry-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    // Select current task
    taskElement.classList.add('selected');
    quickEntryData.selectedTask = {
        id: taskId,
        name: taskName
    };
    
    // Enable create button
    document.getElementById('createQuickEntryBtn').disabled = false;
}

function createQuickEntry() {
    if (!quickEntryData.selectedProject || !quickEntryData.selectedTask) {
        showToast('Please select both project and task', 'warning');
        return;
    }
    
    // Check for overlaps
    const dayColumn = document.querySelector(`[data-date="${quickEntryData.targetDate}"]`);
    const hasOverlap = checkTimeOverlap(dayColumn, quickEntryData.targetHour, 0, 1); // Default 1 hour
    
    if (hasOverlap) {
        showToast('Cannot create entry here - time slot is already occupied', 'warning');
        return;
    }
    
    // Create the time block
    const newTimeBlock = createTimeBlock({
        project: quickEntryData.selectedProject.id,
        task: quickEntryData.selectedTask.id,
        projectName: quickEntryData.selectedProject.name,
        taskName: quickEntryData.selectedTask.name,
        color: quickEntryData.selectedProject.color,
        date: quickEntryData.targetDate,
        startHour: quickEntryData.targetHour,
        startMinute: 0,
        duration: 1 // Default 1 hour
    });
    
    // Select the newly created time block
    if (newTimeBlock) {
        selectTimeBlock(newTimeBlock);
    }
    
    updateDaySummaries();
    closeQuickEntry();
    showToast('Time entry created successfully!', 'success');
    
    // Auto-save after creating
    setTimeout(() => saveTimesheet(), 500);
}

function closeQuickEntry() {
    document.getElementById('quickEntryPopup').style.display = 'none';
    quickEntryData = {
        selectedProject: null,
        selectedTask: null,
        targetTimeSlot: null,
        targetDate: null,
        targetHour: null
    };
}

// Mobile Navigation Functions
function initializeMobileNavigation() {
    // Initialize week dates from day columns
    weekDates = [];
    document.querySelectorAll('.day-column').forEach(dayColumn => {
        weekDates.push(dayColumn.dataset.date);
    });
    
    // Set initial mobile day (Monday = 0)
    currentMobileDayIndex = 0;
    updateMobileDayDisplay();
    updateMobileDayPosition();
}

function updateMobileDayDisplay() {
    if (weekDates.length === 0) return;
    
    const currentDate = new Date(weekDates[currentMobileDayIndex]);
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
    const dayName = dayNames[currentDate.getDay()];
    const monthName = monthNames[currentDate.getMonth()];
    const dayNumber = currentDate.getDate();
    
    document.getElementById('currentDayName').textContent = dayName;
    document.getElementById('currentDayDate').textContent = `${monthName} ${dayNumber}`;
    
    // Update button states
    document.getElementById('prevDayBtn').disabled = currentMobileDayIndex === 0;
    document.getElementById('nextDayBtn').disabled = currentMobileDayIndex === weekDates.length - 1;
}

function updateMobileDayPosition() {
    const calendarDays = document.querySelector('.calendar-days');
    const calendarBody = document.querySelector('.calendar-body');
    
    if (calendarDays && calendarBody) {
        // Each day is 1/7th of the container, so we need to translate by (100/7)% per day
        const translateX = -currentMobileDayIndex * (100 / 7);
        calendarDays.style.transform = `translateX(${translateX}%)`;
        calendarBody.style.transform = `translateX(${translateX}%)`;
    }
}

let lastMobileDayChange = 0;

function changeMobileDay(direction) {
    // Debounce to prevent double clicks
    const now = Date.now();
    if (now - lastMobileDayChange < 300) {
        console.log('Debounced - ignoring rapid click');
        return;
    }
    lastMobileDayChange = now;
    
    console.log('changeMobileDay called with direction:', direction);
    console.log('Current index:', currentMobileDayIndex);
    console.log('Week dates length:', weekDates.length);
    
    const newIndex = currentMobileDayIndex + direction;
    console.log('New index would be:', newIndex);
    
    if (newIndex >= 0 && newIndex < weekDates.length) {
        currentMobileDayIndex = newIndex;
        console.log('Updated currentMobileDayIndex to:', currentMobileDayIndex);
        updateMobileDayDisplay();
        updateMobileDayPosition();
    } else {
        console.log('Index out of bounds, not changing');
    }
}

// Swipe Gesture Support
function setupSwipeGestures() {
    const calendarGrid = document.querySelector('.calendar-grid');
    if (!calendarGrid) return;
    
    let startX = 0;
    let startY = 0;
    let currentX = 0;
    let currentY = 0;
    let isDragging = false;
    
    // Touch events
    calendarGrid.addEventListener('touchstart', function(e) {
        if (window.innerWidth >= 1200) return; // Only on mobile
        
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        isDragging = true;
    }, { passive: true });
    
    calendarGrid.addEventListener('touchmove', function(e) {
        if (!isDragging || window.innerWidth >= 1200) return;
        
        currentX = e.touches[0].clientX;
        currentY = e.touches[0].clientY;
        
        // Prevent default scrolling if horizontal swipe
        const deltaX = Math.abs(currentX - startX);
        const deltaY = Math.abs(currentY - startY);
        
        if (deltaX > deltaY && deltaX > 10) {
            e.preventDefault();
        }
    }, { passive: false });
    
    calendarGrid.addEventListener('touchend', function(e) {
        if (!isDragging || window.innerWidth >= 1200) return;
        
        const deltaX = currentX - startX;
        const deltaY = currentY - startY;
        const minSwipeDistance = 50;
        
        // Check if it's a horizontal swipe
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > minSwipeDistance) {
            if (deltaX > 0) {
                // Swipe right - go to previous day
                changeMobileDay(-1);
            } else {
                // Swipe left - go to next day
                changeMobileDay(1);
            }
        }
        
        isDragging = false;
    }, { passive: true });
    
    // Mouse events for desktop testing
    calendarGrid.addEventListener('mousedown', function(e) {
        if (window.innerWidth >= 1200) return; // Only on mobile
        
        startX = e.clientX;
        startY = e.clientY;
        isDragging = true;
        e.preventDefault();
    });
    
    calendarGrid.addEventListener('mousemove', function(e) {
        if (!isDragging || window.innerWidth >= 1200) return;
        
        currentX = e.clientX;
        currentY = e.clientY;
        e.preventDefault();
    });
    
    calendarGrid.addEventListener('mouseup', function(e) {
        if (!isDragging || window.innerWidth >= 1200) return;
        
        const deltaX = currentX - startX;
        const deltaY = currentY - startY;
        const minSwipeDistance = 50;
        
        // Check if it's a horizontal swipe
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > minSwipeDistance) {
            if (deltaX > 0) {
                // Swipe right - go to previous day
                changeMobileDay(-1);
            } else {
                // Swipe left - go to next day
                changeMobileDay(1);
            }
        }
        
        isDragging = false;
    });
    
    // Prevent context menu on long press
    calendarGrid.addEventListener('contextmenu', function(e) {
        if (window.innerWidth < 1200) {
            e.preventDefault();
        }
    });
}

// Export functions to global scope for HTML onclick handlers
window.toggleProject = toggleProject;
window.changeWeek = changeWeek;
window.clearWeek = clearWeek;
window.saveTimesheet = saveTimesheet;
window.allowDrop = allowDrop;
window.dragEnter = dragEnter;
window.dragLeave = dragLeave;
window.dropTimeBlock = dropTimeBlock;
window.showToast = showToast;
window.toggleHourRange = toggleHourRange;
window.closeEditModal = closeEditModal;
window.updateTaskOptions = updateTaskOptions;
window.saveTimeBlockEdit = saveTimeBlockEdit;
window.deleteTimeBlock = deleteTimeBlock;
window.editFromContext = editFromContext;
window.deleteFromContext = deleteFromContext;
window.closeQuickEntry = closeQuickEntry;
window.createQuickEntry = createQuickEntry;
window.changeMobileDay = changeMobileDay;
