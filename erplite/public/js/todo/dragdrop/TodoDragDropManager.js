/**
 * Todo Drag Drop Manager - Handles drag and drop functionality
 */

class TodoDragDropManager {
    constructor(dataManager, columnManager) {
        this.dataManager = dataManager;
        this.columnManager = columnManager;
        this.draggedTodo = null;
        this.draggedElement = null;
        this.dropZones = [];
        
        // Touch drag properties
        this.touchStartPos = null;
        this.touchElement = null;
        this.isDragging = false;
        
        this.initializeDragDrop();
    }
    
    /**
     * Initialize drag and drop functionality
     */
    initializeDragDrop() {
        this.setupActionDropZones();
        this.setupGlobalDragEvents();
        console.log('Drag drop manager initialized');
    }
    
    /**
     * Setup column drop zones
     */
    setupColumnDropZones() {
        const columns = ['backlog', 'todo', 'progress'];
        
        columns.forEach(columnId => {
            const columnBody = document.getElementById(`${columnId}-body`);
            console.log(`Setting up drop zone for ${columnId}:`, columnBody);
            if (columnBody) {
                this.setupDropZone(columnBody, {
                    type: 'column',
                    columnId: columnId,
                    onDrop: (todo) => this.handleColumnDrop(todo, columnId)
                });
                console.log(`Drop zone setup complete for ${columnId}`);
            } else {
                console.error(`Column body not found for ${columnId}`);
            }
        });
        console.log(`Total drop zones setup: ${this.dropZones.length}`);
    }
    
    /**
     * Setup action drop zones (Complete/Cancel)
     */
    setupActionDropZones() {
        const completeZone = document.querySelector('.complete-zone');
        const cancelZone = document.querySelector('.cancel-zone');
        
        if (completeZone) {
            this.setupDropZone(completeZone, {
                type: 'action',
                action: 'complete',
                onDrop: (todo) => this.handleActionDrop(todo, 'complete')
            });
        }
        
        if (cancelZone) {
            this.setupDropZone(cancelZone, {
                type: 'action',
                action: 'cancel',
                onDrop: (todo) => this.handleActionDrop(todo, 'cancel')
            });
        }
    }
    
    /**
     * Setup drop zone event listeners
     */
    setupDropZone(element, config) {
        element.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            this.handleDragOver(e, element, config);
        });
        
        element.addEventListener('dragenter', (e) => {
            e.preventDefault();
            this.handleDragEnter(e, element, config);
        });
        
        element.addEventListener('dragleave', (e) => {
            this.handleDragLeave(e, element, config);
        });
        
        element.addEventListener('drop', (e) => {
            e.preventDefault();
            this.handleDrop(e, element, config);
        });
        
        this.dropZones.push({ element, config });
    }
    
    /**
     * Setup global drag events
     */
    setupGlobalDragEvents() {
        // Note: Drag events are now handled by inline event handlers in HTML
        // This method is kept for compatibility but does nothing
        console.log('Global drag events setup skipped - using inline handlers');
    }
    
    /**
     * Handle global drag start
     */
    handleGlobalDragStart(e) {
        const todoId = e.target.getAttribute('data-todo-id');
        this.draggedTodo = this.dataManager.getTodoByName(todoId);
        this.draggedElement = e.target;
        
        // Add dragging class
        e.target.classList.add('dragging');
        
        // Store drag data
        e.dataTransfer.setData('text/plain', todoId);
        e.dataTransfer.setData('application/json', JSON.stringify(this.draggedTodo));
        e.dataTransfer.effectAllowed = 'move';
        
        // Show drop zones
        this.showDropZones();
        
        console.log('Drag started:', this.draggedTodo);
    }
    
    /**
     * Handle global drag end
     */
    handleGlobalDragEnd(e) {
        // Remove dragging class
        e.target.classList.remove('dragging');
        
        // Hide drop zones
        this.hideDropZones();
        
        // Clear drag data
        this.draggedTodo = null;
        this.draggedElement = null;
        
        console.log('Drag ended');
    }
    
    /**
     * Handle drag over
     */
    handleDragOver(e, element, config) {
        if (!this.draggedTodo) return;
        
        // Check if drop is allowed
        if (this.isDropAllowed(this.draggedTodo, config)) {
            e.dataTransfer.dropEffect = 'move';
            element.classList.add('drag-over');
        } else {
            e.dataTransfer.dropEffect = 'none';
        }
    }
    
    /**
     * Handle drag enter
     */
    handleDragEnter(e, element, config) {
        if (!this.draggedTodo) return;
        
        if (this.isDropAllowed(this.draggedTodo, config)) {
            element.classList.add('drag-over');
        }
    }
    
    /**
     * Handle drag leave
     */
    handleDragLeave(e, element, config) {
        // Only remove drag-over if we're actually leaving the element
        if (!element.contains(e.relatedTarget)) {
            element.classList.remove('drag-over');
        }
    }
    
    /**
     * Handle drop
     */
    async handleDrop(e, element, config) {
        element.classList.remove('drag-over');
        
        if (!this.draggedTodo) {
            console.log('No dragged todo found');
            return;
        }
        
        // Check if drop is allowed
        if (!this.isDropAllowed(this.draggedTodo, config)) {
            console.log('Drop not allowed for:', this.draggedTodo, config);
            this.showToast('Drop not allowed', 'warning');
            return;
        }
        
        console.log('Executing drop action:', config.type, config);
        
        try {
            // Execute the drop action
            await config.onDrop(this.draggedTodo);
            
            // Show success feedback
            this.showDropSuccess(element, config);
            
        } catch (error) {
            console.error('Drop failed:', error);
            this.showToast('Failed to move todo: ' + error.message, 'error');
        }
    }
    
    /**
     * Handle column drop
     */
    async handleColumnDrop(todo, targetColumnId) {
        const currentColumn = TodoUtils.getTodoColumn(todo);
        
        if (currentColumn === targetColumnId) {
            // Same column, no action needed
            return;
        }
        
        try {
            // Update todo based on target column
            const updates = this.getColumnUpdates(targetColumnId);
            
            // Update in backend
            await this.dataManager.updateTodo(todo.name, updates);
            
            // Update local data
            Object.assign(todo, updates);
            
            // Move in UI
            this.columnManager.moveTodoBetweenColumns(
                todo.name, 
                currentColumn, 
                targetColumnId, 
                todo
            );
            
            this.showToast(`Moved to ${this.getColumnDisplayName(targetColumnId)}`, 'success');
            
        } catch (error) {
            throw new Error('Failed to move todo between columns: ' + error.message);
        }
    }
    
    /**
     * Handle action drop (Complete/Cancel)
     */
    async handleActionDrop(todo, action) {
        const actionConfig = {
            complete: {
                status: 'Closed',
                message: 'Todo completed'
            },
            cancel: {
                status: 'Cancelled',
                message: 'Todo cancelled'
            }
        };
        
        const config = actionConfig[action];
        if (!config) return;
        
        try {
            // Update status in backend
            await this.dataManager.updateTodoStatus(todo.name, config.status);
            
            // Remove from UI (with undo option)
            this.columnManager.removeTodoFromColumn(todo.name);
            
            // Show success with undo option
            this.showToastWithUndo(config.message, 'success', () => {
                this.undoAction(todo, action);
            });
            
        } catch (error) {
            throw new Error(`Failed to ${action} todo: ` + error.message);
        }
    }
    
    /**
     * Get updates needed for target column
     */
    getColumnUpdates(columnId) {
        const updates = {};
        
        switch (columnId) {
            case 'backlog':
                // Remove due date to move to backlog
                updates.date = null;
                break;
                
            case 'todo':
                // Ensure it has a due date and medium priority
                if (!updates.date) {
                    // Set due date to tomorrow if not set
                    const tomorrow = new Date();
                    tomorrow.setDate(tomorrow.getDate() + 1);
                    updates.date = tomorrow.toISOString().split('T')[0];
                }
                break;
                
            case 'progress':
                // Set high priority for in-progress items
                updates.priority = 'High';
                break;
        }
        
        return updates;
    }
    
    /**
     * Check if drop is allowed
     */
    isDropAllowed(todo, config) {
        // Check permissions
        if (!this.dataManager.canEditTodo(todo)) {
            return false;
        }
        
        // Check if it's a valid drop target
        if (config.type === 'column') {
            const currentColumn = TodoUtils.getTodoColumn(todo);
            return currentColumn !== config.columnId;
        }
        
        if (config.type === 'action') {
            // Actions are always allowed if user can edit
            return true;
        }
        
        return false;
    }
    
    /**
     * Show drop zones during drag
     */
    showDropZones() {
        this.dropZones.forEach(({ element, config }) => {
            if (this.isDropAllowed(this.draggedTodo, config)) {
                element.classList.add('drop-zone-active');
            }
        });
    }
    
    /**
     * Hide drop zones after drag
     */
    hideDropZones() {
        this.dropZones.forEach(({ element }) => {
            element.classList.remove('drop-zone-active', 'drag-over');
        });
    }
    
    /**
     * Show drop success animation
     */
    showDropSuccess(element, config) {
        element.classList.add('drop-success');
        
        setTimeout(() => {
            element.classList.remove('drop-success');
        }, 500);
    }
    
    /**
     * Get column display name
     */
    getColumnDisplayName(columnId) {
        const names = {
            backlog: 'Backlog',
            todo: 'To Do',
            progress: 'In Progress'
        };
        return names[columnId] || columnId;
    }
    
    /**
     * Show confirmation dialog
     */
    async showConfirmation(message, title = 'Confirm Action') {
        return new Promise((resolve) => {
            const modal = document.getElementById('confirmModal');
            const titleElement = document.getElementById('confirmTitle');
            const messageElement = document.getElementById('confirmMessage');
            const cancelBtn = document.getElementById('confirmCancel');
            const okBtn = document.getElementById('confirmOk');
            
            if (!modal || !titleElement || !messageElement || !cancelBtn || !okBtn) {
                resolve(true); // Fallback to allowing action
                return;
            }
            
            titleElement.textContent = title;
            messageElement.textContent = message;
            modal.style.display = 'block';
            
            const cleanup = () => {
                modal.style.display = 'none';
                cancelBtn.removeEventListener('click', handleCancel);
                okBtn.removeEventListener('click', handleOk);
            };
            
            const handleCancel = () => {
                cleanup();
                resolve(false);
            };
            
            const handleOk = () => {
                cleanup();
                resolve(true);
            };
            
            cancelBtn.addEventListener('click', handleCancel);
            okBtn.addEventListener('click', handleOk);
        });
    }
    
    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        if (window.showToast) {
            window.showToast(message, type);
        }
    }
    
    /**
     * Show toast with undo option
     */
    showToastWithUndo(message, type, undoCallback) {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="toast-icon mdi mdi-check-circle"></i>
            <span class="toast-message">${message}</span>
            <button class="toast-undo-btn">Undo</button>
            <i class="toast-close mdi mdi-close"></i>
        `;
        
        container.appendChild(toast);
        
        // Show toast
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Add event listeners
        const undoBtn = toast.querySelector('.toast-undo-btn');
        const closeBtn = toast.querySelector('.toast-close');
        
        const hideToast = () => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        };
        
        undoBtn.addEventListener('click', () => {
            undoCallback();
            hideToast();
        });
        
        closeBtn.addEventListener('click', hideToast);
        
        // Auto hide after 8 seconds (longer for undo)
        setTimeout(hideToast, 8000);
    }
    
    /**
     * Undo action (restore todo)
     */
    async undoAction(todo, action) {
        try {
            // Restore to Open status
            await this.dataManager.updateTodoStatus(todo.name, 'Open');
            
            // Refresh the board to show the restored todo
            await this.dataManager.refresh();
            this.columnManager.refreshAllColumns();
            
            this.showToast('Action undone', 'info');
            
        } catch (error) {
            console.error('Failed to undo action:', error);
            this.showToast('Failed to undo action: ' + error.message, 'error');
        }
    }
    
    /**
     * Enable drag and drop
     */
    enable() {
        document.body.classList.remove('drag-disabled');
    }
    
    /**
     * Disable drag and drop
     */
    disable() {
        document.body.classList.add('drag-disabled');
    }
    
    /**
     * Check if drag and drop is enabled
     */
    isEnabled() {
        return !document.body.classList.contains('drag-disabled');
    }
    
    /**
     * Handle touch events for mobile drag and drop
     */
    setupTouchEvents() {        
        document.addEventListener('touchstart', (e) => {
            const card = e.target.closest('.todo-card');
            if (card) {
                this.touchStartPos = {
                    x: e.touches[0].clientX,
                    y: e.touches[0].clientY
                };
                this.touchElement = card;
            }
        });
        
        document.addEventListener('touchmove', (e) => {
            if (!this.touchElement || !this.touchStartPos) return;
            
            const touch = e.touches[0];
            const deltaX = Math.abs(touch.clientX - this.touchStartPos.x);
            const deltaY = Math.abs(touch.clientY - this.touchStartPos.y);
            
            // Start dragging if moved enough
            if (!this.isDragging && (deltaX > 10 || deltaY > 10)) {
                this.isDragging = true;
                this.startTouchDrag(this.touchElement, touch);
            }
            
            if (this.isDragging) {
                e.preventDefault();
                this.updateTouchDrag(touch);
            }
        });
        
        document.addEventListener('touchend', (e) => {
            if (this.isDragging) {
                this.endTouchDrag(e.changedTouches[0]);
            }
            
            this.touchStartPos = null;
            this.touchElement = null;
            this.isDragging = false;
        });
    }
    
    /**
     * Start touch drag
     */
    startTouchDrag(element, touch) {
        const todoId = element.getAttribute('data-todo-id');
        this.draggedTodo = this.dataManager.getTodoByName(todoId);
        this.draggedElement = element;
        
        element.classList.add('dragging');
        this.showDropZones();
    }
    
    /**
     * Update touch drag position
     */
    updateTouchDrag(touch) {
        // Visual feedback for touch drag
        if (this.draggedElement && this.touchStartPos) {
            this.draggedElement.style.transform = `translate(${touch.clientX - this.touchStartPos.x}px, ${touch.clientY - this.touchStartPos.y}px)`;
        }
    }
    
    /**
     * End touch drag
     */
    endTouchDrag(touch) {
        if (!this.draggedElement) return;
        
        // Reset transform
        this.draggedElement.style.transform = '';
        this.draggedElement.classList.remove('dragging');
        
        // Find drop target
        const elementBelow = document.elementFromPoint(touch.clientX, touch.clientY);
        const dropZone = elementBelow?.closest('.column-body, .drop-zone');
        
        if (dropZone) {
            // Find matching drop zone config
            const dropZoneConfig = this.dropZones.find(({ element }) => 
                element === dropZone || element.contains(dropZone)
            );
            
            if (dropZoneConfig && this.isDropAllowed(this.draggedTodo, dropZoneConfig.config)) {
                dropZoneConfig.config.onDrop(this.draggedTodo);
            }
        }
        
        this.hideDropZones();
        this.draggedTodo = null;
        this.draggedElement = null;
    }
    
    /**
     * Simple methods for global handlers - keeping the working pattern
     */
    handleSimpleDragStart(event) {
        console.log('📝 DragDropManager: Simple drag start');
        
        // Keep it EXACTLY like the working version
        event.target.style.opacity = '0.5';
        event.dataTransfer.setData('text/plain', event.target.getAttribute('data-todo-id') || 'unknown');
        event.dataTransfer.effectAllowed = 'move';
        
        // Store minimal data for later use (but don't let it break the drag)
        try {
            const todoId = event.target.getAttribute('data-todo-id');
            this.draggedTodo = this.dataManager.getTodoByName(todoId);
            this.draggedElement = event.target;
            console.log('📝 Dragging todo:', this.draggedTodo?.name);
        } catch (error) {
            console.log('📝 Error getting todo data (but drag continues):', error);
            this.draggedTodo = null;
            this.draggedElement = event.target;
        }
    }
    
    handleSimpleDragEnd(event) {
        console.log('📝 DragDropManager: Simple drag end');
        
        // Reset visual state
        event.target.style.opacity = '1';
        event.target.classList.remove('dragging');
        
        // Clean up drag-over styles
        document.querySelectorAll('.column-body').forEach(col => {
            col.style.backgroundColor = '';
            col.classList.remove('drag-over');
        });
        
        // Clear drag state
        this.draggedTodo = null;
        this.draggedElement = null;
    }
    
    handleSimpleDragOver(event) {
        // Just prevent default - keep it simple
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }
    
    handleSimpleDragEnter(event) {
        console.log('📝 DragDropManager: Simple drag enter');
        event.preventDefault();
        event.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
        event.currentTarget.classList.add('drag-over');
    }
    
    handleSimpleDragLeave(event) {
        // Only remove highlight if we're actually leaving the column
        if (!event.currentTarget.contains(event.relatedTarget)) {
            event.currentTarget.style.backgroundColor = '';
            event.currentTarget.classList.remove('drag-over');
        }
    }
    
    async handleSimpleDrop(event, columnId, draggedCard) {
        console.log('📝 DragDropManager: Simple drop in column:', columnId);
        event.preventDefault();
        event.currentTarget.style.backgroundColor = '';
        event.currentTarget.classList.remove('drag-over');
        
        if (draggedCard && this.draggedTodo) {
            // Get current column
            const currentColumn = this.draggedTodo.column || 'backlog';
            
            // Don't move if it's the same column
            if (currentColumn === columnId) {
                console.log('📝 Same column, no move needed');
                this.showToast('Already in this column', 'info');
                return;
            }
            
            // Move the card to the new column
            const targetColumn = document.getElementById(columnId + '-body');
            if (targetColumn) {
                targetColumn.appendChild(draggedCard);
                console.log('📝 Card moved successfully to', columnId);
                
                // Update the todo data
                this.draggedTodo.column = columnId;
                
                // Update column counts and handle placeholders
                this.updateColumnCounts();
                
                // Show success message
                this.showToast(`Moved to ${this.getColumnDisplayName(columnId)}`, 'success');
                
                // Save to backend
                try {
                    await this.saveColumnChange(this.draggedTodo, columnId);
                    console.log('📝 Backend sync successful');
                } catch (error) {
                    console.error('📝 Backend sync failed:', error);
                    this.showToast('Move saved locally, but failed to sync to server', 'warning');
                }
                
                console.log('📝 Todo data updated:', this.draggedTodo);
            }
        }
    }
    
    /**
     * Save column change to backend
     */
    async saveColumnChange(todo, newColumnId) {
        console.log('📝 Saving column change:', { todoName: todo.name, newColumnId });
        
        if (!this.dataManager || !this.dataManager.updateTodoStatus) {
            console.error('📝 No data manager or update method available');
            throw new Error('Data manager not available');
        }
        
        // Map columns to proper status values
        const columnToStatus = {
            'backlog': 'Backlog',
            'todo': 'Planned', 
            'progress': 'Open'
        };
        
        const newStatus = columnToStatus[newColumnId];
        if (!newStatus) {
            console.error('📝 Invalid column ID:', newColumnId);
            throw new Error('Invalid column');
        }
        
        console.log('📝 Updating todo status to:', newStatus);
        
        // Use the updateTodoStatus method which handles status changes
        await this.dataManager.updateTodoStatus(todo.name, newStatus, newColumnId);
        
        // Update local todo object
        todo.status = newStatus;
        todo.column = newColumnId;
        
        console.log('📝 Todo status updated successfully');
    }

    /**
     * Helper methods
     */
    updateColumnCounts() {
        ['backlog', 'todo', 'progress'].forEach(columnId => {
            const columnBody = document.getElementById(columnId + '-body');
            const countElement = document.getElementById(columnId + '-count');
            if (columnBody && countElement) {
                const cardCount = columnBody.querySelectorAll('.todo-card').length;
                countElement.textContent = cardCount;
                
                // Hide/show placeholder based on card count
                const placeholder = columnBody.querySelector('.empty-state, .no-activitys-message, [class*="empty"], [class*="no-"]');
                if (placeholder) {
                    placeholder.style.display = cardCount > 0 ? 'none' : 'block';
                }
            }
        });
    }
    
    getColumnDisplayName(columnId) {
        const names = {
            backlog: 'Backlog',
            todo: 'To Do',
            progress: 'In Progress'
        };
        return names[columnId] || columnId;
    }
    
    showToast(message, type = 'info') {
        if (window.showToast) {
            window.showToast(message, type);
        }
    }

    /**
     * Cleanup drag and drop
     */
    cleanup() {
        this.dropZones = [];
        this.draggedTodo = null;
        this.draggedElement = null;
    }
}

// Add CSS for drag and drop states
const dragDropCSS = `
.drop-zone-active {
    opacity: 1 !important;
    transform: scale(1.02);
    transition: all 0.2s ease;
}

.drop-success {
    animation: dropSuccess 0.5s ease;
}

@keyframes dropSuccess {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); background-color: rgba(16, 185, 129, 0.1); }
    100% { transform: scale(1); }
}

.drag-disabled .todo-card {
    cursor: default !important;
}

.drag-disabled .todo-card[draggable] {
    pointer-events: none;
}

.toast-undo-btn {
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
}

.toast-undo-btn:hover {
    background: rgba(255, 255, 255, 0.3);
}

/* Touch drag styles */
.todo-card.dragging {
    z-index: 1000;
    pointer-events: none;
}

/* Mobile drag feedback */
@media (max-width: 768px) {
    .todo-card.dragging {
        transform: rotate(5deg) scale(1.05);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
    }
}
`;

// Inject CSS
if (!document.getElementById('todo-dragdrop-styles')) {
    const style = document.createElement('style');
    style.id = 'todo-dragdrop-styles';
    style.textContent = dragDropCSS;
    document.head.appendChild(style);
}

// Make TodoDragDropManager available globally
window.TodoDragDropManager = TodoDragDropManager;
