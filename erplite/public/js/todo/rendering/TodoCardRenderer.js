/**
 * Todo Card Renderer - Handles rendering of todo cards
 */

class TodoCardRenderer {
    constructor() {
        this.cardTemplate = document.getElementById('todo-card-template');
        if (!this.cardTemplate) {
            console.error('Todo card template not found');
        }
    }
    
    /**
     * Render a todo card
     */
    renderCard(todo) {
        if (!this.cardTemplate) {
            console.error('Card template not available');
            return null;
        }
        
        // Clone the template
        const cardElement = this.cardTemplate.content.cloneNode(true);
        const card = cardElement.querySelector('.todo-card');
        
        // Set card data attributes
        card.setAttribute('data-todo-id', todo.name);
        card.setAttribute('data-todo-column', TodoUtils.getTodoColumn(todo));
        
        // Ensure card is draggable (critical for browser drag functionality)
        card.draggable = true;
        card.setAttribute('draggable', 'true');
        
        // Set custom color if available
        if (todo.color) {
            card.style.borderLeftColor = todo.color;
        }
        
        // Render collapsed view
        this.renderCollapsedView(card, todo);
        
        // Render expanded view (card header, body, footer)
        this.renderCardHeader(card, todo);
        this.renderCardBody(card, todo);
        this.renderCardFooter(card, todo);
        this.renderCardReference(card, todo);
        
        // Add event listeners
        this.addCardEventListeners(card, todo);
        
        return card;
    }
    
    /**
     * Render collapsed view (single line preview)
     */
    renderCollapsedView(card, todo) {
        // Priority indicator
        const priorityIndicator = card.querySelector('.priority-indicator');
        if (priorityIndicator) {
            const priority = (todo.priority || 'Medium').toLowerCase();
            priorityIndicator.className = `priority-indicator ${priority}`;
        }
        
        // Description preview
        const descriptionPreview = card.querySelector('.card-description-preview');
        if (descriptionPreview && todo.description) {
            const plainText = this.stripHtml(todo.description);
            descriptionPreview.textContent = plainText;
            descriptionPreview.title = plainText; // Full text on hover
        }
        
        // Due date indicator
        const dueDateIndicator = card.querySelector('.due-date-indicator');
        if (dueDateIndicator) {
            if (todo.due_date && todo.due_date.date) {
                const relativeDateInfo = TodoUtils.formatRelativeDate(todo.due_date.date);
                if (relativeDateInfo) {
                    dueDateIndicator.textContent = relativeDateInfo.text;
                    dueDateIndicator.className = `due-date-indicator ${relativeDateInfo.class}`;
                } else {
                    dueDateIndicator.textContent = TodoUtils.formatDate(todo.due_date.date);
                    dueDateIndicator.className = 'due-date-indicator';
                }
            } else {
                dueDateIndicator.textContent = '';
                dueDateIndicator.className = 'due-date-indicator';
            }
        }
        
        // User avatar small
        const userAvatarSmall = card.querySelector('.user-avatar-small');
        if (userAvatarSmall) {
            if (todo.user) {
                userAvatarSmall.textContent = todo.user.initials || TodoUtils.getUserInitials(todo.user.full_name);
                userAvatarSmall.style.backgroundColor = TodoUtils.generateUserColor(todo.user.name);
                userAvatarSmall.title = todo.user.full_name || todo.user.name;
            } else {
                userAvatarSmall.textContent = '?';
                userAvatarSmall.style.backgroundColor = '#9ca3af';
                userAvatarSmall.title = 'Unassigned';
            }
        }
    }
    
    /**
     * Render card header (priority dropdown and due date picker)
     */
    renderCardHeader(card, todo) {
        // Priority dropdown
        const priorityDropdown = card.querySelector('.priority-dropdown');
        if (priorityDropdown) {
            priorityDropdown.value = todo.priority || 'Medium';
            priorityDropdown.className = `priority-dropdown card-dropdown priority-${(todo.priority || 'Medium').toLowerCase()}`;
        }
        
        // Due date section
        const dueDatePicker = card.querySelector('.due-date-picker');
        const dueDateDisplay = card.querySelector('.due-date-display');
        
        if (dueDatePicker && dueDateDisplay) {
            if (todo.due_date && todo.due_date.date) {
                dueDatePicker.value = todo.due_date.date;
                
                const relativeDateInfo = TodoUtils.formatRelativeDate(todo.due_date.date);
                if (relativeDateInfo) {
                    dueDateDisplay.textContent = relativeDateInfo.text;
                    dueDateDisplay.className = `due-date-display ${relativeDateInfo.class}`;
                } else {
                    dueDateDisplay.textContent = TodoUtils.formatDate(todo.due_date.date);
                    dueDateDisplay.className = 'due-date-display';
                }
                dueDateDisplay.style.display = 'block';
            } else {
                dueDatePicker.value = '';
                dueDateDisplay.textContent = 'No due date';
                dueDateDisplay.className = 'due-date-display';
                dueDateDisplay.style.display = 'block';
            }
        }
    }
    
    /**
     * Render card body (description)
     */
    renderCardBody(card, todo) {
        const description = card.querySelector('.card-description');
        
        if (description && todo.description) {
            // Strip HTML tags
            const plainText = this.stripHtml(todo.description);
            
            // Store full text in data attribute for editing
            description.setAttribute('data-full-text', plainText);
            description.setAttribute('data-original-text', plainText);
            
            // Show full text in expanded cards (no truncation)
            description.textContent = plainText;
            description.title = plainText; // Full text on hover
            
            // Make description editable
            description.contentEditable = true;
        }
    }
    
    /**
     * Render card footer (user info and actions)
     */
    renderCardFooter(card, todo) {
        const userAvatar = card.querySelector('.user-avatar');
        const userName = card.querySelector('.user-name');
        const editBtn = card.querySelector('.edit-btn');
        const deleteBtn = card.querySelector('.delete-btn');
        
        // User info
        if (todo.user) {
            if (userAvatar) {
                userAvatar.textContent = todo.user.initials || TodoUtils.getUserInitials(todo.user.full_name);
                userAvatar.style.backgroundColor = TodoUtils.generateUserColor(todo.user.name);
                userAvatar.title = todo.user.full_name || todo.user.name;
            }
            
            if (userName) {
                userName.textContent = todo.user.full_name || todo.user.name;
            }
        } else {
            // Unassigned
            if (userAvatar) {
                userAvatar.textContent = '?';
                userAvatar.style.backgroundColor = '#9ca3af';
                userAvatar.title = 'Unassigned';
            }
            
            if (userName) {
                userName.textContent = 'Unassigned';
                userName.style.color = '#9ca3af';
            }
        }
        
        // Action buttons visibility based on permissions
        const dataManager = window.todoKanban?.dataManager;
        if (dataManager) {
            const canEdit = dataManager.canEditTodo(todo);
            const canDelete = dataManager.canDeleteTodo(todo);
            
            if (editBtn) {
                editBtn.style.display = canEdit ? 'flex' : 'none';
            }
            
            if (deleteBtn) {
                deleteBtn.style.display = canDelete ? 'flex' : 'none';
            }
        }
    }
    
    /**
     * Render card reference link
     */
    renderCardReference(card, todo) {
        const reference = card.querySelector('.card-reference');
        
        if (reference && todo.reference && todo.reference.type) {
            // Create clickable reference link
            const referenceUrl = this.buildReferenceUrl(todo.reference.type, todo.reference.name);
            
            reference.innerHTML = `
                <i class="mdi mdi-link-variant"></i>
                <a href="${referenceUrl}" target="_blank" class="reference-link" title="Open ${todo.reference.type}: ${todo.reference.name}">
                    ${todo.reference.type}: ${todo.reference.name}
                </a>
            `;
            reference.style.display = 'flex';
            
            // Add click handler to prevent drag when clicking reference
            const referenceLink = reference.querySelector('.reference-link');
            if (referenceLink) {
                referenceLink.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
            }
        } else if (reference) {
            reference.style.display = 'none';
        }
    }
    
    /**
     * Build URL for reference document
     */
    buildReferenceUrl(doctype, docname) {
        // Build Frappe desk URL for the referenced document
        const baseUrl = window.location.origin;
        return `${baseUrl}/app/${doctype.toLowerCase()}/${encodeURIComponent(docname)}`;
    }
    
    /**
     * Add event listeners to card
     */
    addCardEventListeners(card, todo) {
        // Priority dropdown
        const priorityDropdown = card.querySelector('.priority-dropdown');
        if (priorityDropdown) {
            priorityDropdown.addEventListener('change', (e) => {
                e.stopPropagation();
                this.handlePriorityChange(todo, e.target.value);
            });
            
            // Prevent drag when interacting with dropdown
            priorityDropdown.addEventListener('mousedown', (e) => {
                e.stopPropagation();
            });
        }
        
        // Due date picker
        const dueDatePicker = card.querySelector('.due-date-picker');
        const dueDateDisplay = card.querySelector('.due-date-display');
        
        if (dueDatePicker && dueDateDisplay) {
            // Show picker when clicking display
            dueDateDisplay.addEventListener('click', (e) => {
                e.stopPropagation();
                dueDatePicker.classList.add('active');
                dueDatePicker.focus();
            });
            
            // Handle date change
            dueDatePicker.addEventListener('change', (e) => {
                e.stopPropagation();
                this.handleDueDateChange(todo, e.target.value);
                dueDatePicker.classList.remove('active');
            });
            
            // Hide picker on blur
            dueDatePicker.addEventListener('blur', () => {
                dueDatePicker.classList.remove('active');
            });
            
            // Prevent drag when interacting with date picker
            dueDatePicker.addEventListener('mousedown', (e) => {
                e.stopPropagation();
            });
        }
        
        // User dropdown
        const userDropdown = card.querySelector('.user-dropdown');
        if (userDropdown) {
            // Populate user dropdown
            this.populateUserDropdown(userDropdown, todo);
            
            userDropdown.addEventListener('change', (e) => {
                e.stopPropagation();
                this.handleUserChange(todo, e.target.value);
            });
            
            // Prevent drag when interacting with dropdown
            userDropdown.addEventListener('mousedown', (e) => {
                e.stopPropagation();
            });
        }
        
        // Edit button
        const editBtn = card.querySelector('.edit-btn');
        if (editBtn) {
            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.handleEditClick(todo);
            });
        }
        
        // Delete button
        const deleteBtn = card.querySelector('.delete-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.handleDeleteClick(todo);
            });
        }
        
        // Description editing
        const description = card.querySelector('.card-description');
        if (description) {
            // Handle focus - show full text for editing
            description.addEventListener('focus', (e) => {
                const card = e.target.closest('.todo-card');
                if (card) {
                    card.draggable = false;
                }
                
                // Show full text when editing
                const fullText = e.target.getAttribute('data-full-text');
                if (fullText) {
                    e.target.textContent = fullText;
                }
                
                // Add editing class to expand card
                e.target.classList.add('editing');
            });
            
            // Handle blur - save changes and keep full text visible
            description.addEventListener('blur', (e) => {
                const card = e.target.closest('.todo-card');
                if (card) {
                    card.draggable = true;
                }
                
                // Remove editing class
                e.target.classList.remove('editing');
                
                const newText = e.target.textContent.trim();
                
                // Save the changes
                this.handleDescriptionChange(todo, newText);
                
                // Update stored full text
                e.target.setAttribute('data-full-text', newText);
                e.target.setAttribute('data-original-text', newText);
                
                // Keep full text visible (no truncation in expanded cards)
                e.target.textContent = newText;
                e.target.title = newText; // Update hover text
            });
            
            description.addEventListener('keydown', (e) => {
                // Save on Enter, cancel on Escape
                if (e.key === 'Enter') {
                    e.preventDefault();
                    e.target.blur(); // This will trigger the blur event and save
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    // Revert to original text
                    const originalText = e.target.getAttribute('data-original-text');
                    e.target.textContent = originalText;
                    e.target.blur();
                }
            });
            
            // Prevent drag when editing description
            description.addEventListener('mousedown', (e) => {
                if (e.target.contentEditable === 'true') {
                    e.stopPropagation();
                }
            });
        }
        
        // Card click (for future expansion - could open details modal)
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.card-action-btn') && !e.target.closest('.card-dropdown') && e.target !== description) {
                this.handleCardClick(todo);
            }
        });
        
        // Note: Drag events are handled by TodoDragDropManager globally
    }
    
    /**
     * Handle edit button click
     */
    handleEditClick(todo) {
        if (window.todoKanban && window.todoKanban.showEditTodoModal) {
            window.todoKanban.showEditTodoModal(todo);
        }
    }
    
    /**
     * Handle delete button click
     */
    handleDeleteClick(todo) {
        if (window.todoKanban && window.todoKanban.deleteTodo) {
            window.todoKanban.deleteTodo(todo);
        }
    }
    
    /**
     * Handle card click
     */
    handleCardClick(todo) {
        // Could open a details modal or expand the card
        console.log('Card clicked:', todo);
    }
    
    /**
     * Handle priority change
     */
    async handlePriorityChange(todo, newPriority) {
        console.log('Priority changed:', todo.name, 'to', newPriority);
        
        try {
            const dataManager = window.todoKanban?.dataManager;
            if (!dataManager) {
                throw new Error('Data manager not available');
            }
            
            // Update in backend
            await dataManager.updateTodo(todo.name, { priority: newPriority });
            
            // Update local data
            todo.priority = newPriority;
            
            // Update the dropdown styling and collapsed view
            const cardElement = this.getCardElement(todo.name);
            const priorityDropdown = cardElement?.querySelector('.priority-dropdown');
            if (priorityDropdown) {
                priorityDropdown.className = `priority-dropdown card-dropdown priority-${newPriority.toLowerCase()}`;
            }
            
            // Update collapsed view priority indicator
            if (cardElement) {
                this.renderCollapsedView(cardElement, todo);
            }
            
            // Show success message
            if (window.showToast) {
                window.showToast(`Priority updated to ${newPriority}`, 'success');
            }
            
        } catch (error) {
            console.error('Failed to update priority:', error);
            if (window.showToast) {
                window.showToast('Failed to update priority: ' + error.message, 'error');
            }
            
            // Revert the dropdown value
            const cardElement = this.getCardElement(todo.name);
            const priorityDropdown = cardElement?.querySelector('.priority-dropdown');
            if (priorityDropdown) {
                priorityDropdown.value = todo.priority || 'Medium';
            }
        }
    }
    
    /**
     * Handle due date change
     */
    async handleDueDateChange(todo, newDate) {
        console.log('Due date changed:', todo.name, 'to', newDate);
        
        try {
            const dataManager = window.todoKanban?.dataManager;
            if (!dataManager) {
                throw new Error('Data manager not available');
            }
            
            // Update in backend
            await dataManager.updateTodo(todo.name, { date: newDate || null });
            
            // Update local data
            if (newDate) {
                todo.due_date = {
                    date: newDate,
                    formatted: TodoUtils.formatDate(newDate),
                    is_overdue: false,
                    days_diff: 0,
                    relative: TodoUtils.formatRelativeDate(newDate)?.text || 'Set'
                };
            } else {
                todo.due_date = null;
            }
            
            // Update the display in both expanded and collapsed views
            const cardElement = this.getCardElement(todo.name);
            if (cardElement) {
                this.renderCardHeader(cardElement, todo);
                this.renderCollapsedView(cardElement, todo);
            }
            
            // Show success message
            if (window.showToast) {
                const message = newDate ? `Due date set to ${TodoUtils.formatDate(newDate)}` : 'Due date removed';
                window.showToast(message, 'success');
            }
            
        } catch (error) {
            console.error('Failed to update due date:', error);
            if (window.showToast) {
                window.showToast('Failed to update due date: ' + error.message, 'error');
            }
            
            // Revert the date picker value
            const cardElement = this.getCardElement(todo.name);
            const dueDatePicker = cardElement?.querySelector('.due-date-picker');
            if (dueDatePicker) {
                dueDatePicker.value = todo.due_date?.date || '';
            }
        }
    }
    
    /**
     * Handle user assignment change
     */
    async handleUserChange(todo, newUserId) {
        console.log('User assignment changed:', todo.name, 'to', newUserId);
        
        try {
            const dataManager = window.todoKanban?.dataManager;
            if (!dataManager) {
                throw new Error('Data manager not available');
            }
            
            // Check permissions
            if (!dataManager.canEditTodo(todo)) {
                throw new Error('You do not have permission to reassign this todo');
            }
            
            // Update in backend
            await dataManager.updateTodo(todo.name, { allocated_to: newUserId || null });
            
            // Update local data
            if (newUserId) {
                const user = TodoUtils.findUser(newUserId);
                todo.user = user ? {
                    name: user.name,
                    full_name: user.full_name || user.name,
                    initials: TodoUtils.getUserInitials(user.full_name || user.name)
                } : null;
            } else {
                todo.user = null;
            }
            
            // Update both the card footer and collapsed view
            const cardElement = this.getCardElement(todo.name);
            if (cardElement) {
                this.renderCardFooter(cardElement, todo);
                this.renderCollapsedView(cardElement, todo);
            }
            
            // Show success message
            if (window.showToast) {
                const message = newUserId ? `Assigned to ${todo.user?.full_name || 'user'}` : 'Unassigned';
                window.showToast(message, 'success');
            }
            
        } catch (error) {
            console.error('Failed to update user assignment:', error);
            if (window.showToast) {
                window.showToast('Failed to update assignment: ' + error.message, 'error');
            }
            
            // Revert the dropdown value
            const cardElement = this.getCardElement(todo.name);
            const userDropdown = cardElement?.querySelector('.user-dropdown');
            if (userDropdown) {
                userDropdown.value = todo.user?.name || '';
            }
        }
    }
    
    /**
     * Handle description change
     */
    async handleDescriptionChange(todo, newDescription) {
        // Don't save if description hasn't changed
        const originalText = todo.description;
        if (newDescription === originalText || newDescription === '') {
            return;
        }
        
        console.log('Description changed:', todo.name, 'to', newDescription);
        
        try {
            const dataManager = window.todoKanban?.dataManager;
            if (!dataManager) {
                throw new Error('Data manager not available');
            }
            
            // Check permissions
            if (!dataManager.canEditTodo(todo)) {
                throw new Error('You do not have permission to edit this todo');
            }
            
            // Update in backend
            await dataManager.updateTodo(todo.name, { description: newDescription });
            
            // Update local data
            todo.description = newDescription;
            
            // Update the stored original text and collapsed view
            const cardElement = this.getCardElement(todo.name);
            const descriptionElement = cardElement?.querySelector('.card-description');
            if (descriptionElement) {
                descriptionElement.setAttribute('data-original-text', newDescription);
                descriptionElement.title = newDescription; // Update hover text
            }
            
            // Update collapsed view description preview
            if (cardElement) {
                this.renderCollapsedView(cardElement, todo);
            }
            
            // Show success message
            if (window.showToast) {
                window.showToast('Description updated', 'success');
            }
            
        } catch (error) {
            console.error('Failed to update description:', error);
            if (window.showToast) {
                window.showToast('Failed to update description: ' + error.message, 'error');
            }
            
            // Revert the description text
            const cardElement = this.getCardElement(todo.name);
            const descriptionElement = cardElement?.querySelector('.card-description');
            if (descriptionElement) {
                descriptionElement.textContent = originalText;
            }
        }
    }
    
    /**
     * Populate user dropdown with available users
     */
    populateUserDropdown(dropdown, todo) {
        // Clear existing options except the first one
        dropdown.innerHTML = '<option value="">Unassigned</option>';
        
        // Get users from global data
        const users = TodoUtils.getUsers();
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user.name;
            option.textContent = user.full_name || user.name;
            dropdown.appendChild(option);
        });
        
        // Set current value
        dropdown.value = todo.user?.name || '';
    }
    
    /**
     * Handle drag start
     */
    handleDragStart(e, todo) {
        const card = e.target;
        card.classList.add('dragging');
        
        // Set drag data
        e.dataTransfer.setData('text/plain', todo.name);
        e.dataTransfer.setData('application/json', JSON.stringify(todo));
        e.dataTransfer.effectAllowed = 'move';
        
        // Create drag image (optional)
        this.createDragImage(e, card);
    }
    
    /**
     * Handle drag end
     */
    handleDragEnd(e, todo) {
        const card = e.target;
        card.classList.remove('dragging');
        
        // Clean up any drag-related styling
        document.querySelectorAll('.drag-over').forEach(el => {
            el.classList.remove('drag-over');
        });
    }
    
    /**
     * Create custom drag image
     */
    createDragImage(e, card) {
        // Create a clone of the card for dragging
        const dragImage = card.cloneNode(true);
        dragImage.style.transform = 'rotate(5deg)';
        dragImage.style.opacity = '0.8';
        dragImage.style.position = 'absolute';
        dragImage.style.top = '-1000px';
        dragImage.style.left = '-1000px';
        dragImage.style.width = card.offsetWidth + 'px';
        dragImage.style.pointerEvents = 'none';
        
        document.body.appendChild(dragImage);
        
        // Set as drag image
        e.dataTransfer.setDragImage(dragImage, card.offsetWidth / 2, card.offsetHeight / 2);
        
        // Clean up after drag
        setTimeout(() => {
            if (dragImage.parentNode) {
                dragImage.parentNode.removeChild(dragImage);
            }
        }, 0);
    }
    
    /**
     * Update card data
     */
    updateCard(cardElement, todo) {
        // Update data attributes
        cardElement.setAttribute('data-todo-column', TodoUtils.getTodoColumn(todo));
        
        // Re-render collapsed view
        this.renderCollapsedView(cardElement, todo);
        
        // Re-render expanded view parts
        this.renderCardHeader(cardElement, todo);
        this.renderCardBody(cardElement, todo);
        this.renderCardFooter(cardElement, todo);
        this.renderCardReference(cardElement, todo);
    }
    
    /**
     * Animate card addition
     */
    animateCardIn(cardElement) {
        cardElement.style.opacity = '0';
        cardElement.style.transform = 'translateY(20px) scale(0.95)';
        
        // Trigger animation
        requestAnimationFrame(() => {
            cardElement.style.transition = 'all 0.3s ease';
            cardElement.style.opacity = '1';
            cardElement.style.transform = 'translateY(0) scale(1)';
        });
        
        // Clean up
        setTimeout(() => {
            cardElement.style.transition = '';
        }, 300);
    }
    
    /**
     * Animate card removal
     */
    animateCardOut(cardElement, callback) {
        cardElement.style.transition = 'all 0.3s ease';
        cardElement.style.opacity = '0';
        cardElement.style.transform = 'translateY(-20px) scale(0.95)';
        
        setTimeout(() => {
            if (callback) callback();
        }, 300);
    }
    
    /**
     * Strip HTML tags from text
     */
    stripHtml(html) {
        const div = document.createElement('div');
        div.innerHTML = html;
        return div.textContent || div.innerText || '';
    }
    
    /**
     * Get card element by todo ID
     */
    getCardElement(todoId) {
        return document.querySelector(`[data-todo-id="${todoId}"]`);
    }
    
    /**
     * Remove card from DOM
     */
    removeCard(todoId) {
        const cardElement = this.getCardElement(todoId);
        if (cardElement) {
            this.animateCardOut(cardElement, () => {
                if (cardElement.parentNode) {
                    cardElement.parentNode.removeChild(cardElement);
                }
            });
        }
    }
    
    /**
     * Highlight card (for search results, etc.)
     */
    highlightCard(todoId, duration = 2000) {
        const cardElement = this.getCardElement(todoId);
        if (cardElement) {
            cardElement.classList.add('highlighted');
            
            setTimeout(() => {
                cardElement.classList.remove('highlighted');
            }, duration);
        }
    }
    
    /**
     * Get all card elements
     */
    getAllCardElements() {
        return document.querySelectorAll('.todo-card');
    }
    
    /**
     * Clear all cards from a column
     */
    clearColumn(columnId) {
        const columnBody = document.getElementById(`${columnId}-body`);
        if (columnBody) {
            columnBody.innerHTML = '';
        }
    }
    
    /**
     * Get cards count in column
     */
    getColumnCardCount(columnId) {
        const columnBody = document.getElementById(`${columnId}-body`);
        if (columnBody) {
            return columnBody.querySelectorAll('.todo-card').length;
        }
        return 0;
    }
    
    /**
     * Sort cards in column
     */
    sortCardsInColumn(columnId, sortFn) {
        const columnBody = document.getElementById(`${columnId}-body`);
        if (!columnBody) return;
        
        const cards = Array.from(columnBody.querySelectorAll('.todo-card'));
        cards.sort(sortFn);
        
        // Re-append in sorted order
        cards.forEach(card => columnBody.appendChild(card));
    }
    
    /**
     * Filter cards visibility
     */
    filterCards(filterFn) {
        const cards = this.getAllCardElements();
        cards.forEach(card => {
            const todoId = card.getAttribute('data-todo-id');
            const dataManager = window.todoKanban?.dataManager;
            
            if (dataManager) {
                const todo = dataManager.getTodoByName(todoId);
                if (todo) {
                    const shouldShow = filterFn(todo);
                    card.style.display = shouldShow ? 'block' : 'none';
                }
            }
        });
    }
    
    /**
     * Reset all card filters
     */
    resetCardFilters() {
        const cards = this.getAllCardElements();
        cards.forEach(card => {
            card.style.display = 'block';
        });
    }
}

// Make TodoCardRenderer available globally
window.TodoCardRenderer = TodoCardRenderer;
