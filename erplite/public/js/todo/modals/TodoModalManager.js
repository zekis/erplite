/**
 * Todo Modal Manager - Handles modal dialogs for creating and editing todos
 */

class TodoModalManager {
    constructor(dataManager) {
        this.dataManager = dataManager;
        this.currentTodo = null;
        this.isEditing = false;
        
        this.initializeModals();
    }
    
    /**
     * Initialize modal elements and event listeners
     */
    initializeModals() {
        this.todoModal = document.getElementById('todoModal');
        this.confirmModal = document.getElementById('confirmModal');
        
        if (this.todoModal) {
            this.setupTodoModal();
        }
        
        if (this.confirmModal) {
            this.setupConfirmModal();
        }
    }
    
    /**
     * Setup todo modal event listeners
     */
    setupTodoModal() {
        // Modal elements
        this.modalTitle = document.getElementById('modalTitle');
        this.todoForm = document.getElementById('todoForm');
        this.closeBtn = document.getElementById('closeModal');
        this.cancelBtn = document.getElementById('cancelBtn');
        this.saveBtn = document.getElementById('saveBtn');
        
        // Form elements
        this.todoId = document.getElementById('todoId');
        this.todoDescription = document.getElementById('todoDescription');
        this.todoPriority = document.getElementById('todoPriority');
        this.todoDueDate = document.getElementById('todoDueDate');
        this.todoAssignedTo = document.getElementById('todoAssignedTo');
        this.todoColor = document.getElementById('todoColor');
        
        // Event listeners
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.closeTodoModal());
        }
        
        if (this.cancelBtn) {
            this.cancelBtn.addEventListener('click', () => this.closeTodoModal());
        }
        
        if (this.saveBtn) {
            this.saveBtn.addEventListener('click', () => this.saveTodo());
        }
        
        if (this.todoForm) {
            this.todoForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveTodo();
            });
        }
        
        // Close modal when clicking outside
        this.todoModal.addEventListener('click', (e) => {
            if (e.target === this.todoModal) {
                this.closeTodoModal();
            }
        });
        
        // Form validation
        if (this.todoDescription) {
            this.todoDescription.addEventListener('input', () => this.validateForm());
        }
    }
    
    /**
     * Setup confirm modal event listeners
     */
    setupConfirmModal() {
        this.confirmTitle = document.getElementById('confirmTitle');
        this.confirmMessage = document.getElementById('confirmMessage');
        this.confirmCancel = document.getElementById('confirmCancel');
        this.confirmOk = document.getElementById('confirmOk');
        
        // Close modal when clicking outside
        this.confirmModal.addEventListener('click', (e) => {
            if (e.target === this.confirmModal) {
                this.closeConfirmModal();
            }
        });
    }
    
    /**
     * Show add todo modal
     */
    showAddTodoModal() {
        this.currentTodo = null;
        this.isEditing = false;
        
        // Set modal title
        if (this.modalTitle) {
            this.modalTitle.textContent = 'Add Todo';
        }
        
        // Set save button text
        if (this.saveBtn) {
            this.saveBtn.textContent = 'Add Todo';
        }
        
        // Clear form
        this.clearForm();
        
        // Set default values
        this.setDefaultValues();
        
        // Show modal
        this.showModal(this.todoModal);
        
        // Focus on description field
        if (this.todoDescription) {
            setTimeout(() => {
                this.todoDescription.focus();
            }, 100);
        }
    }
    
    /**
     * Show edit todo modal
     */
    showEditTodoModal(todo) {
        this.currentTodo = todo;
        this.isEditing = true;
        
        // Set modal title
        if (this.modalTitle) {
            this.modalTitle.textContent = 'Edit Todo';
        }
        
        // Set save button text
        if (this.saveBtn) {
            this.saveBtn.textContent = 'Update Todo';
        }
        
        // Populate form with todo data
        this.populateForm(todo);
        
        // Show modal
        this.showModal(this.todoModal);
        
        // Focus on description field
        if (this.todoDescription) {
            setTimeout(() => {
                this.todoDescription.focus();
                this.todoDescription.setSelectionRange(0, this.todoDescription.value.length);
            }, 100);
        }
    }
    
    /**
     * Close todo modal
     */
    closeTodoModal() {
        this.hideModal(this.todoModal);
        this.currentTodo = null;
        this.isEditing = false;
        this.clearForm();
    }
    
    /**
     * Save todo (create or update)
     */
    async saveTodo() {
        if (!this.validateForm()) {
            return;
        }
        
        const formData = this.getFormData();
        
        try {
            // Show loading state
            this.setLoadingState(true);
            
            if (this.isEditing && this.currentTodo) {
                // Update existing todo
                await this.updateTodo(formData);
            } else {
                // Create new todo
                await this.createTodo(formData);
            }
            
            // Close modal
            this.closeTodoModal();
            
            // Refresh the board
            if (window.todoKanban) {
                await window.todoKanban.refreshTodos();
            }
            
            // Show success message
            const message = this.isEditing ? 'Todo updated successfully' : 'Todo created successfully';
            this.showToast(message, 'success');
            
        } catch (error) {
            console.error('Error saving todo:', error);
            this.showToast('Failed to save todo: ' + error.message, 'error');
        } finally {
            this.setLoadingState(false);
        }
    }
    
    /**
     * Create new todo
     */
    async createTodo(formData) {
        await this.dataManager.createTodo(formData);
    }
    
    /**
     * Update existing todo
     */
    async updateTodo(formData) {
        await this.dataManager.updateTodo(this.currentTodo.name, formData);
    }
    
    /**
     * Get form data
     */
    getFormData() {
        const data = {};
        
        if (this.todoDescription) {
            data.description = this.todoDescription.value.trim();
        }
        
        if (this.todoPriority) {
            data.priority = this.todoPriority.value;
        }
        
        if (this.todoDueDate && this.todoDueDate.value) {
            data.date = this.todoDueDate.value;
        }
        
        if (this.todoAssignedTo) {
            data.allocated_to = this.todoAssignedTo.value || null;
        }
        
        if (this.todoColor) {
            data.color = this.todoColor.value;
        }
        
        return data;
    }
    
    /**
     * Populate form with todo data
     */
    populateForm(todo) {
        if (this.todoId) {
            this.todoId.value = todo.name;
        }
        
        if (this.todoDescription) {
            this.todoDescription.value = todo.description || '';
        }
        
        if (this.todoPriority) {
            this.todoPriority.value = todo.priority || 'Medium';
        }
        
        if (this.todoDueDate && todo.due_date) {
            this.todoDueDate.value = todo.due_date.date;
        }
        
        if (this.todoAssignedTo && todo.user) {
            this.todoAssignedTo.value = todo.user.name || '';
        }
        
        if (this.todoColor) {
            this.todoColor.value = todo.color || '#3b82f6';
        }
    }
    
    /**
     * Clear form
     */
    clearForm() {
        if (this.todoForm) {
            this.todoForm.reset();
        }
        
        if (this.todoId) {
            this.todoId.value = '';
        }
    }
    
    /**
     * Set default values
     */
    setDefaultValues() {
        if (this.todoPriority) {
            this.todoPriority.value = 'Medium';
        }
        
        if (this.todoColor) {
            this.todoColor.value = '#3b82f6';
        }
        
        // Set default assignee to current user if not manager
        if (this.todoAssignedTo && !this.dataManager.isManager) {
            this.todoAssignedTo.value = this.dataManager.currentUser;
            this.todoAssignedTo.disabled = true;
        }
    }
    
    /**
     * Validate form
     */
    validateForm() {
        let isValid = true;
        
        // Clear previous errors
        this.clearFormErrors();
        
        // Validate description
        if (!this.todoDescription || !this.todoDescription.value.trim()) {
            this.showFieldError(this.todoDescription, 'Description is required');
            isValid = false;
        }
        
        // Update save button state
        if (this.saveBtn) {
            this.saveBtn.disabled = !isValid;
        }
        
        return isValid;
    }
    
    /**
     * Show field error
     */
    showFieldError(field, message) {
        if (!field) return;
        
        field.classList.add('error');
        
        // Create or update error message
        let errorElement = field.parentNode.querySelector('.field-error');
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.className = 'field-error';
            field.parentNode.appendChild(errorElement);
        }
        errorElement.textContent = message;
    }
    
    /**
     * Clear form errors
     */
    clearFormErrors() {
        const errorFields = this.todoModal.querySelectorAll('.error');
        errorFields.forEach(field => field.classList.remove('error'));
        
        const errorMessages = this.todoModal.querySelectorAll('.field-error');
        errorMessages.forEach(msg => msg.remove());
    }
    
    /**
     * Set loading state
     */
    setLoadingState(loading) {
        if (this.saveBtn) {
            this.saveBtn.disabled = loading;
            this.saveBtn.innerHTML = loading ? 
                '<i class="mdi mdi-loading mdi-spin"></i> Saving...' : 
                (this.isEditing ? 'Update Todo' : 'Add Todo');
        }
        
        // Disable form fields during loading
        const formFields = this.todoModal.querySelectorAll('input, select, textarea');
        formFields.forEach(field => {
            field.disabled = loading;
        });
    }
    
    /**
     * Show confirmation modal
     */
    showConfirmModal(title, message, onConfirm, onCancel) {
        return new Promise((resolve) => {
            if (!this.confirmModal) {
                resolve(false);
                return;
            }
            
            // Set content
            if (this.confirmTitle) {
                this.confirmTitle.textContent = title;
            }
            
            if (this.confirmMessage) {
                this.confirmMessage.textContent = message;
            }
            
            // Setup event handlers
            const handleConfirm = () => {
                this.closeConfirmModal();
                if (onConfirm) onConfirm();
                resolve(true);
            };
            
            const handleCancel = () => {
                this.closeConfirmModal();
                if (onCancel) onCancel();
                resolve(false);
            };
            
            // Remove existing listeners
            if (this.confirmOk) {
                this.confirmOk.replaceWith(this.confirmOk.cloneNode(true));
                this.confirmOk = document.getElementById('confirmOk');
                this.confirmOk.addEventListener('click', handleConfirm);
            }
            
            if (this.confirmCancel) {
                this.confirmCancel.replaceWith(this.confirmCancel.cloneNode(true));
                this.confirmCancel = document.getElementById('confirmCancel');
                this.confirmCancel.addEventListener('click', handleCancel);
            }
            
            // Show modal
            this.showModal(this.confirmModal);
        });
    }
    
    /**
     * Close confirm modal
     */
    closeConfirmModal() {
        this.hideModal(this.confirmModal);
    }
    
    /**
     * Show modal with animation
     */
    showModal(modal) {
        if (!modal) return;
        
        modal.style.display = 'block';
        document.body.classList.add('modal-open');
        
        // Trigger animation
        requestAnimationFrame(() => {
            modal.classList.add('show');
        });
    }
    
    /**
     * Hide modal with animation
     */
    hideModal(modal) {
        if (!modal) return;
        
        modal.classList.remove('show');
        document.body.classList.remove('modal-open');
        
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
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
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(e) {
        // Escape key - close modals
        if (e.key === 'Escape') {
            if (this.todoModal && this.todoModal.style.display === 'block') {
                this.closeTodoModal();
            } else if (this.confirmModal && this.confirmModal.style.display === 'block') {
                this.closeConfirmModal();
            }
        }
        
        // Enter key - save todo (if in todo modal)
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            if (this.todoModal && this.todoModal.style.display === 'block') {
                e.preventDefault();
                this.saveTodo();
            }
        }
    }
    
    /**
     * Auto-resize textarea
     */
    setupAutoResize() {
        if (this.todoDescription) {
            this.todoDescription.addEventListener('input', () => {
                this.todoDescription.style.height = 'auto';
                this.todoDescription.style.height = this.todoDescription.scrollHeight + 'px';
            });
        }
    }
    
    /**
     * Setup form enhancements
     */
    setupFormEnhancements() {
        this.setupAutoResize();
        
        // Add character counter for description
        if (this.todoDescription) {
            const counter = document.createElement('div');
            counter.className = 'character-counter';
            this.todoDescription.parentNode.appendChild(counter);
            
            const updateCounter = () => {
                const length = this.todoDescription.value.length;
                counter.textContent = `${length} characters`;
                counter.className = `character-counter ${length > 500 ? 'warning' : ''}`;
            };
            
            this.todoDescription.addEventListener('input', updateCounter);
            updateCounter();
        }
        
        // Add date picker enhancements
        if (this.todoDueDate) {
            // Set min date to today
            const today = new Date().toISOString().split('T')[0];
            this.todoDueDate.min = today;
            
            // Add quick date buttons
            this.addQuickDateButtons();
        }
    }
    
    /**
     * Add quick date selection buttons
     */
    addQuickDateButtons() {
        if (!this.todoDueDate) return;
        
        const quickDates = document.createElement('div');
        quickDates.className = 'quick-dates';
        quickDates.innerHTML = `
            <button type="button" class="quick-date-btn" data-days="0">Today</button>
            <button type="button" class="quick-date-btn" data-days="1">Tomorrow</button>
            <button type="button" class="quick-date-btn" data-days="7">Next Week</button>
            <button type="button" class="quick-date-btn" data-days="30">Next Month</button>
        `;
        
        this.todoDueDate.parentNode.appendChild(quickDates);
        
        // Add event listeners
        quickDates.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-date-btn')) {
                const days = parseInt(e.target.getAttribute('data-days'));
                const date = new Date();
                date.setDate(date.getDate() + days);
                this.todoDueDate.value = date.toISOString().split('T')[0];
            }
        });
    }
    
    /**
     * Initialize modal manager
     */
    initialize() {
        this.setupFormEnhancements();
        
        // Add keyboard shortcut listener
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });
    }
    
    /**
     * Cleanup modal manager
     */
    cleanup() {
        this.closeTodoModal();
        this.closeConfirmModal();
    }
}

// Add CSS for modal enhancements
const modalCSS = `
.modal.show {
    animation: modalFadeIn 0.3s ease;
}

@keyframes modalFadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.modal-open {
    overflow: hidden;
}

.field-error {
    color: var(--danger-color);
    font-size: 0.75rem;
    margin-top: 0.25rem;
}

.form-group input.error,
.form-group textarea.error,
.form-group select.error {
    border-color: var(--danger-color);
    box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
}

.character-counter {
    font-size: 0.75rem;
    color: var(--gray-500);
    text-align: right;
    margin-top: 0.25rem;
}

.character-counter.warning {
    color: var(--warning-color);
}

.quick-dates {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
    flex-wrap: wrap;
}

.quick-date-btn {
    padding: 0.25rem 0.5rem;
    border: 1px solid var(--gray-300);
    background: white;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
}

.quick-date-btn:hover {
    background: var(--gray-50);
    border-color: var(--gray-400);
}

.quick-date-btn:active {
    background: var(--gray-100);
}

.mdi-spin {
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Mobile modal adjustments */
@media (max-width: 768px) {
    .modal-content {
        width: 95%;
        margin: 5% auto;
        max-height: 90vh;
        overflow-y: auto;
    }
    
    .quick-dates {
        justify-content: center;
    }
    
    .quick-date-btn {
        flex: 1;
        min-width: 0;
    }
}
`;

// Inject CSS
if (!document.getElementById('todo-modal-styles')) {
    const style = document.createElement('style');
    style.id = 'todo-modal-styles';
    style.textContent = modalCSS;
    document.head.appendChild(style);
}

// Make TodoModalManager available globally
window.TodoModalManager = TodoModalManager;
