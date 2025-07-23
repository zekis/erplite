/**
 * Todo Column Manager - Handles column operations and layout
 */

class TodoColumnManager {
    constructor(cardRenderer) {
        this.cardRenderer = cardRenderer;
        this.columns = ['backlog', 'todo', 'progress'];
        this.columnElements = {};
        this.columnCounts = {};
        this.groupStates = {}; // Persistent storage for group states
        this.cardStates = {}; // Persistent storage for individual card states
        
        this.initializeColumns();
    }
    
    /**
     * Initialize column elements and references
     */
    initializeColumns() {
        this.columns.forEach(columnId => {
            this.columnElements[columnId] = {
                container: document.querySelector(`[data-column="${columnId}"]`),
                body: document.getElementById(`${columnId}-body`),
                count: document.getElementById(`${columnId}-count`)
            };
        });
    }
    
    /**
     * Render todos in all columns
     */
    renderAllColumns(todosByColumn) {
        // Clear all columns first
        this.clearAllColumns();
        
        // Render each column
        this.columns.forEach(columnId => {
            const todos = todosByColumn[columnId] || [];
            this.renderColumn(columnId, todos);
        });
        
        // Update column counts
        this.updateAllColumnCounts(todosByColumn);
    }
    
    /**
     * Render a specific column
     */
    renderColumn(columnId, todos) {
        const columnBody = this.columnElements[columnId]?.body;
        if (!columnBody) {
            console.error(`Column body not found for: ${columnId}`);
            return;
        }
        
        // Save current group and card states before clearing
        const groupStates = this.saveGroupStates(columnBody);
        const cardStates = this.saveCardStates(columnBody);
        
        // Clear existing cards
        columnBody.innerHTML = '';
        
        // Group todos by reference doctype and name
        const groupedTodos = this.groupTodosByReference(todos);
        
        // Separate groups and individual cards
        const groups = [];
        const individualCards = [];
        
        Object.keys(groupedTodos).forEach(groupKey => {
            const group = groupedTodos[groupKey];
            
            if (group.todos.length === 1) {
                // Single todo - add to individual cards
                individualCards.push(group.todos[0]);
            } else {
                // Multiple todos with same reference - add to groups
                groups.push(group);
            }
        });
        
        // Render groups first (at the top)
        groups.forEach(group => {
            const groupElement = this.renderTodoGroup(group);
            if (groupElement) {
                columnBody.appendChild(groupElement);
                
                // Restore group state if it was previously expanded
                this.restoreGroupState(groupElement, groupStates);
                
                // Animate group in
                requestAnimationFrame(() => {
                    this.animateGroupIn(groupElement);
                });
            }
        });
        
        // Then render individual cards below groups
        individualCards.forEach(todo => {
            const cardElement = this.cardRenderer.renderCard(todo);
            if (cardElement) {
                columnBody.appendChild(cardElement);
                
                // Restore card state if it was previously expanded
                this.restoreCardState(cardElement, cardStates);
                
                // Animate card in
                requestAnimationFrame(() => {
                    this.cardRenderer.animateCardIn(cardElement);
                });
            }
        });
        
        // Update column count
        this.updateColumnCount(columnId, todos.length);
        
        // Add empty state if no todos
        if (todos.length === 0) {
            this.showEmptyState(columnId);
        }
    }
    
    /**
     * Group todos by reference doctype and name
     */
    groupTodosByReference(todos) {
        const groups = {};
        const sortedTodos = this.sortTodos(todos);
        
        sortedTodos.forEach(todo => {
            let groupKey;
            
            if (todo.reference && todo.reference.type && todo.reference.name) {
                // Group by reference doctype and name
                groupKey = `${todo.reference.type}:${todo.reference.name}`;
            } else {
                // No reference - each todo gets its own group
                groupKey = `no-ref:${todo.name}`;
            }
            
            if (!groups[groupKey]) {
                groups[groupKey] = {
                    reference: todo.reference,
                    todos: [],
                    priority: todo.priority,
                    earliestDueDate: todo.due_date
                };
            }
            
            groups[groupKey].todos.push(todo);
            
            // Update group priority to highest priority in group
            const priorityOrder = { 'High': 3, 'Medium': 2, 'Low': 1 };
            const currentPriority = priorityOrder[groups[groupKey].priority] || 0;
            const todoPriority = priorityOrder[todo.priority] || 0;
            
            if (todoPriority > currentPriority) {
                groups[groupKey].priority = todo.priority;
            }
            
            // Update group due date to earliest in group
            if (todo.due_date && (!groups[groupKey].earliestDueDate || 
                new Date(todo.due_date.date) < new Date(groups[groupKey].earliestDueDate.date))) {
                groups[groupKey].earliestDueDate = todo.due_date;
            }
        });
        
        // Sort groups by priority and due date
        const sortedGroups = {};
        Object.keys(groups)
            .sort((a, b) => {
                const groupA = groups[a];
                const groupB = groups[b];
                
                // Sort by priority first
                const priorityOrder = { 'High': 3, 'Medium': 2, 'Low': 1 };
                const aPriority = priorityOrder[groupA.priority] || 0;
                const bPriority = priorityOrder[groupB.priority] || 0;
                
                if (aPriority !== bPriority) {
                    return bPriority - aPriority;
                }
                
                // Then by due date
                if (groupA.earliestDueDate && groupB.earliestDueDate) {
                    return new Date(groupA.earliestDueDate.date) - new Date(groupB.earliestDueDate.date);
                } else if (groupA.earliestDueDate) {
                    return -1;
                } else if (groupB.earliestDueDate) {
                    return 1;
                }
                
                return 0;
            })
            .forEach(key => {
                sortedGroups[key] = groups[key];
            });
        
        return sortedGroups;
    }
    
    /**
     * Render a todo group
     */
    renderTodoGroup(group) {
        const groupElement = document.createElement('div');
        groupElement.className = 'todo-group';
        
        // Create group header
        const groupHeader = document.createElement('div');
        groupHeader.className = 'todo-group-header';
        
        const referenceInfo = group.reference ? 
            `${group.reference.type}: ${group.reference.name}` : 
            'Related Tasks';
        
        const todoCount = group.todos.length;
        const priorityClass = (group.priority || 'Medium').toLowerCase();
        
        groupHeader.innerHTML = `
            <div class="group-reference">
                <i class="mdi mdi-link-variant group-reference-icon"></i>
                <span class="group-reference-text">${referenceInfo}</span>
            </div>
            <div class="group-meta">
                <span class="group-priority priority-${priorityClass}">${group.priority || 'Medium'}</span>
                <span class="group-count">${todoCount} task${todoCount > 1 ? 's' : ''}</span>
                <button class="group-toggle-btn" title="Toggle group">
                    <i class="mdi mdi-chevron-down"></i>
                </button>
            </div>
        `;
        
        // Create group body (initially collapsed)
        const groupBody = document.createElement('div');
        groupBody.className = 'todo-group-body collapsed';
        
        // Render todos in group
        group.todos.forEach(todo => {
            const cardElement = this.cardRenderer.renderCard(todo);
            if (cardElement) {
                cardElement.classList.add('grouped-card');
                groupBody.appendChild(cardElement);
            }
        });
        
        // Add toggle functionality
        const toggleBtn = groupHeader.querySelector('.group-toggle-btn');
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleGroup(groupBody, toggleBtn);
        });
        
        // Add click to expand functionality to header
        groupHeader.addEventListener('click', () => {
            this.toggleGroup(groupBody, toggleBtn);
        });
        
        groupElement.appendChild(groupHeader);
        groupElement.appendChild(groupBody);
        
        return groupElement;
    }
    
    /**
     * Toggle group expanded/collapsed state
     */
    toggleGroup(groupBody, toggleBtn) {
        const isCollapsed = groupBody.classList.contains('collapsed');
        
        // Get group key for persistent storage
        const groupElement = groupBody.closest('.todo-group');
        const referenceText = groupElement?.querySelector('.group-reference-text');
        const groupKey = referenceText?.textContent;
        
        if (isCollapsed) {
            groupBody.classList.remove('collapsed');
            groupBody.classList.add('expanded');
            toggleBtn.innerHTML = '<i class="mdi mdi-chevron-up"></i>';
            toggleBtn.title = 'Collapse group';
            
            // Save expanded state
            if (groupKey) {
                this.groupStates[groupKey] = true;
            }
        } else {
            groupBody.classList.remove('expanded');
            groupBody.classList.add('collapsed');
            toggleBtn.innerHTML = '<i class="mdi mdi-chevron-down"></i>';
            toggleBtn.title = 'Expand group';
            
            // Save collapsed state
            if (groupKey) {
                this.groupStates[groupKey] = false;
            }
        }
    }
    
    /**
     * Animate group in
     */
    animateGroupIn(groupElement) {
        groupElement.style.opacity = '0';
        groupElement.style.transform = 'translateY(20px) scale(0.95)';
        
        // Trigger animation
        requestAnimationFrame(() => {
            groupElement.style.transition = 'all 0.3s ease';
            groupElement.style.opacity = '1';
            groupElement.style.transform = 'translateY(0) scale(1)';
        });
        
        // Clean up
        setTimeout(() => {
            groupElement.style.transition = '';
        }, 300);
    }
    
    /**
     * Sort todos within a column
     */
    sortTodos(todos) {
        return todos.sort((a, b) => {
            // First sort by priority
            const priorityOrder = { 'High': 3, 'Medium': 2, 'Low': 1 };
            const aPriority = priorityOrder[a.priority] || 0;
            const bPriority = priorityOrder[b.priority] || 0;
            
            if (aPriority !== bPriority) {
                return bPriority - aPriority; // High priority first
            }
            
            // Then sort by due date (earliest first)
            if (a.due_date && b.due_date) {
                return new Date(a.due_date.date) - new Date(b.due_date.date);
            } else if (a.due_date) {
                return -1; // Items with due dates come first
            } else if (b.due_date) {
                return 1;
            }
            
            // Finally sort by creation date (newest first)
            return new Date(b.created) - new Date(a.created);
        });
    }
    
    /**
     * Add todo to column
     */
    addTodoToColumn(columnId, todo) {
        const columnBody = this.columnElements[columnId]?.body;
        if (!columnBody) {
            console.error(`Column body not found for: ${columnId}`);
            return;
        }
        
        // Remove empty state if present
        this.hideEmptyState(columnId);
        
        // Check if this todo can be grouped with existing todos
        const existingGroup = this.findExistingGroup(columnBody, todo);
        
        if (existingGroup) {
            // Add to existing group
            this.addTodoToExistingGroup(existingGroup, todo);
        } else {
            // Check if we need to create a new group with existing individual cards
            const matchingIndividualCard = this.findMatchingIndividualCard(columnBody, todo);
            
            if (matchingIndividualCard) {
                // Create new group with both cards
                this.createNewGroupFromCards(columnBody, matchingIndividualCard, todo);
            } else {
                // Add as individual card
                this.addIndividualCard(columnBody, todo);
            }
        }
        
        // Update count
        this.incrementColumnCount(columnId);
    }
    
    /**
     * Remove todo from column
     */
    removeTodoFromColumn(todoId) {
        const cardElement = this.cardRenderer.getCardElement(todoId);
        if (cardElement) {
            const columnId = this.getColumnIdFromCard(cardElement);
            const isGroupedCard = cardElement.classList.contains('grouped-card');
            const parentGroup = isGroupedCard ? cardElement.closest('.todo-group') : null;
            
            // Animate out and remove
            this.cardRenderer.animateCardOut(cardElement, () => {
                if (cardElement.parentNode) {
                    cardElement.parentNode.removeChild(cardElement);
                }
                
                // If this was a grouped card, check if group is now empty
                if (parentGroup) {
                    this.checkAndCleanupEmptyGroup(parentGroup);
                }
                
                // Update count
                if (columnId) {
                    this.decrementColumnCount(columnId);
                    
                    // Show empty state if no cards left
                    if (this.cardRenderer.getColumnCardCount(columnId) === 0) {
                        this.showEmptyState(columnId);
                    }
                }
            });
        }
    }
    
    /**
     * Check and cleanup empty group after removing a card
     */
    checkAndCleanupEmptyGroup(groupElement) {
        const groupBody = groupElement.querySelector('.todo-group-body');
        const remainingCards = groupBody.querySelectorAll('.grouped-card');
        
        if (remainingCards.length === 0) {
            // Group is empty, remove it with animation
            this.animateGroupOut(groupElement, () => {
                if (groupElement.parentNode) {
                    groupElement.parentNode.removeChild(groupElement);
                }
            });
        } else if (remainingCards.length === 1) {
            // Only one card left, convert back to individual card
            const lastCard = remainingCards[0];
            const columnBody = groupElement.parentNode;
            
            // Remove grouped-card class
            lastCard.classList.remove('grouped-card');
            
            // Move card out of group and remove group
            columnBody.insertBefore(lastCard, groupElement);
            
            // Remove the now-empty group
            this.animateGroupOut(groupElement, () => {
                if (groupElement.parentNode) {
                    groupElement.parentNode.removeChild(groupElement);
                }
            });
        } else {
            // Update group count
            const groupCount = groupElement.querySelector('.group-count');
            if (groupCount) {
                const count = remainingCards.length;
                groupCount.textContent = `${count} task${count > 1 ? 's' : ''}`;
            }
        }
    }
    
    /**
     * Animate group out (removal)
     */
    animateGroupOut(groupElement, callback) {
        groupElement.style.transition = 'all 0.3s ease';
        groupElement.style.opacity = '0';
        groupElement.style.transform = 'translateY(-20px) scale(0.95)';
        
        setTimeout(() => {
            if (callback) callback();
        }, 300);
    }
    
    /**
     * Find existing group that matches the todo's reference
     */
    findExistingGroup(columnBody, todo) {
        if (!todo.reference || !todo.reference.type || !todo.reference.name) {
            return null;
        }
        
        const groups = columnBody.querySelectorAll('.todo-group');
        for (let group of groups) {
            const referenceText = group.querySelector('.group-reference-text');
            if (referenceText) {
                const expectedText = `${todo.reference.type}: ${todo.reference.name}`;
                if (referenceText.textContent === expectedText) {
                    return group;
                }
            }
        }
        
        return null;
    }
    
    /**
     * Find individual card that matches the todo's reference
     */
    findMatchingIndividualCard(columnBody, todo) {
        if (!todo.reference || !todo.reference.type || !todo.reference.name) {
            return null;
        }
        
        const individualCards = columnBody.querySelectorAll('.todo-card:not(.grouped-card)');
        for (let card of individualCards) {
            const todoId = card.getAttribute('data-todo-id');
            const dataManager = window.todoKanban?.dataManager;
            
            if (dataManager) {
                const existingTodo = dataManager.getTodoByName(todoId);
                if (existingTodo && existingTodo.reference && 
                    existingTodo.reference.type === todo.reference.type &&
                    existingTodo.reference.name === todo.reference.name) {
                    return card;
                }
            }
        }
        
        return null;
    }
    
    /**
     * Add todo to existing group
     */
    addTodoToExistingGroup(groupElement, todo) {
        const groupBody = groupElement.querySelector('.todo-group-body');
        const groupCount = groupElement.querySelector('.group-count');
        
        // Create card element
        const cardElement = this.cardRenderer.renderCard(todo);
        if (cardElement) {
            cardElement.classList.add('grouped-card');
            
            // Find correct position within group (maintain sort order)
            const insertPosition = this.findInsertPositionInGroup(groupBody, todo);
            
            if (insertPosition) {
                groupBody.insertBefore(cardElement, insertPosition);
            } else {
                groupBody.appendChild(cardElement);
            }
            
            // Update group count
            const currentCount = groupBody.querySelectorAll('.grouped-card').length;
            if (groupCount) {
                groupCount.textContent = `${currentCount} task${currentCount > 1 ? 's' : ''}`;
            }
            
            // Update group priority if needed
            this.updateGroupPriority(groupElement, todo);
            
            // Animate card in
            this.cardRenderer.animateCardIn(cardElement);
        }
    }
    
    /**
     * Create new group from two matching cards
     */
    createNewGroupFromCards(columnBody, existingCard, newTodo) {
        // Get existing todo data
        const existingTodoId = existingCard.getAttribute('data-todo-id');
        const dataManager = window.todoKanban?.dataManager;
        const existingTodo = dataManager?.getTodoByName(existingTodoId);
        
        if (!existingTodo) return;
        
        // Create group data
        const groupData = {
            reference: newTodo.reference,
            todos: [existingTodo, newTodo],
            priority: this.getHigherPriority(existingTodo.priority, newTodo.priority),
            earliestDueDate: this.getEarlierDate(existingTodo.due_date, newTodo.due_date)
        };
        
        // Create group element
        const groupElement = this.renderTodoGroup(groupData);
        
        // Replace existing card with group
        columnBody.insertBefore(groupElement, existingCard);
        existingCard.remove();
        
        // Animate group in
        this.animateGroupIn(groupElement);
    }
    
    /**
     * Add todo as individual card
     */
    addIndividualCard(columnBody, todo) {
        const cardElement = this.cardRenderer.renderCard(todo);
        if (cardElement) {
            // Find correct position to insert (maintain sort order)
            const insertPosition = this.findInsertPosition(columnBody, todo);
            
            if (insertPosition) {
                columnBody.insertBefore(cardElement, insertPosition);
            } else {
                columnBody.appendChild(cardElement);
            }
            
            // Animate card in
            this.cardRenderer.animateCardIn(cardElement);
        }
    }
    
    /**
     * Find insert position within a group
     */
    findInsertPositionInGroup(groupBody, newTodo) {
        const cards = groupBody.querySelectorAll('.grouped-card');
        
        for (let card of cards) {
            const todoId = card.getAttribute('data-todo-id');
            const dataManager = window.todoKanban?.dataManager;
            
            if (dataManager) {
                const existingTodo = dataManager.getTodoByName(todoId);
                if (existingTodo && this.shouldInsertBefore(newTodo, existingTodo)) {
                    return card;
                }
            }
        }
        
        return null; // Insert at end
    }
    
    /**
     * Update group priority based on new todo
     */
    updateGroupPriority(groupElement, newTodo) {
        const priorityElement = groupElement.querySelector('.group-priority');
        if (!priorityElement) return;
        
        const currentPriority = priorityElement.textContent;
        const newPriority = this.getHigherPriority(currentPriority, newTodo.priority);
        
        if (newPriority !== currentPriority) {
            priorityElement.textContent = newPriority;
            priorityElement.className = `group-priority priority-${newPriority.toLowerCase()}`;
        }
    }
    
    /**
     * Get higher priority between two priorities
     */
    getHigherPriority(priority1, priority2) {
        const priorityOrder = { 'High': 3, 'Medium': 2, 'Low': 1 };
        const p1Value = priorityOrder[priority1] || 0;
        const p2Value = priorityOrder[priority2] || 0;
        
        return p1Value >= p2Value ? priority1 : priority2;
    }
    
    /**
     * Get earlier date between two due dates
     */
    getEarlierDate(date1, date2) {
        if (!date1) return date2;
        if (!date2) return date1;
        
        const d1 = new Date(date1.date);
        const d2 = new Date(date2.date);
        
        return d1 <= d2 ? date1 : date2;
    }
    
    /**
     * Move todo between columns
     */
    moveTodoBetweenColumns(todoId, fromColumnId, toColumnId, todo) {
        // Remove from source column
        this.removeTodoFromColumn(todoId);
        
        // Add to destination column
        setTimeout(() => {
            this.addTodoToColumn(toColumnId, todo);
        }, 150); // Small delay for smooth animation
    }
    
    /**
     * Find correct insert position for maintaining sort order
     */
    findInsertPosition(columnBody, newTodo) {
        const cards = columnBody.querySelectorAll('.todo-card');
        
        for (let card of cards) {
            const todoId = card.getAttribute('data-todo-id');
            const dataManager = window.todoKanban?.dataManager;
            
            if (dataManager) {
                const existingTodo = dataManager.getTodoByName(todoId);
                if (existingTodo && this.shouldInsertBefore(newTodo, existingTodo)) {
                    return card;
                }
            }
        }
        
        return null; // Insert at end
    }
    
    /**
     * Determine if new todo should be inserted before existing todo
     */
    shouldInsertBefore(newTodo, existingTodo) {
        // Compare by priority first
        const priorityOrder = { 'High': 3, 'Medium': 2, 'Low': 1 };
        const newPriority = priorityOrder[newTodo.priority] || 0;
        const existingPriority = priorityOrder[existingTodo.priority] || 0;
        
        if (newPriority > existingPriority) {
            return true;
        } else if (newPriority < existingPriority) {
            return false;
        }
        
        // Same priority, compare by due date
        if (newTodo.due_date && existingTodo.due_date) {
            return new Date(newTodo.due_date.date) < new Date(existingTodo.due_date.date);
        } else if (newTodo.due_date) {
            return true; // New todo has due date, existing doesn't
        } else if (existingTodo.due_date) {
            return false; // Existing has due date, new doesn't
        }
        
        // No due dates, compare by creation date (newer first)
        return new Date(newTodo.created) > new Date(existingTodo.created);
    }
    
    /**
     * Get column ID from card element
     */
    getColumnIdFromCard(cardElement) {
        const column = cardElement.closest('.kanban-column');
        return column ? column.getAttribute('data-column') : null;
    }
    
    /**
     * Update column count
     */
    updateColumnCount(columnId, count) {
        const countElement = this.columnElements[columnId]?.count;
        if (countElement) {
            countElement.textContent = count;
            this.columnCounts[columnId] = count;
        }
    }
    
    /**
     * Update all column counts
     */
    updateAllColumnCounts(todosByColumn) {
        this.columns.forEach(columnId => {
            const count = todosByColumn[columnId]?.length || 0;
            this.updateColumnCount(columnId, count);
        });
    }
    
    /**
     * Increment column count
     */
    incrementColumnCount(columnId) {
        const currentCount = this.columnCounts[columnId] || 0;
        this.updateColumnCount(columnId, currentCount + 1);
    }
    
    /**
     * Decrement column count
     */
    decrementColumnCount(columnId) {
        const currentCount = this.columnCounts[columnId] || 0;
        this.updateColumnCount(columnId, Math.max(0, currentCount - 1));
    }
    
    /**
     * Clear all columns
     */
    clearAllColumns() {
        this.columns.forEach(columnId => {
            this.clearColumn(columnId);
        });
    }
    
    /**
     * Clear specific column
     */
    clearColumn(columnId) {
        const columnBody = this.columnElements[columnId]?.body;
        if (columnBody) {
            columnBody.innerHTML = '';
        }
        this.updateColumnCount(columnId, 0);
    }
    
    /**
     * Show empty state for column
     */
    showEmptyState(columnId) {
        const columnBody = this.columnElements[columnId]?.body;
        if (!columnBody) return;
        
        const emptyState = this.createEmptyState(columnId);
        columnBody.appendChild(emptyState);
    }
    
    /**
     * Hide empty state for column
     */
    hideEmptyState(columnId) {
        const columnBody = this.columnElements[columnId]?.body;
        if (!columnBody) return;
        
        const emptyState = columnBody.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
    }
    
    /**
     * Create empty state element
     */
    createEmptyState(columnId) {
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state';
        
        const messages = {
            backlog: {
                icon: 'mdi-inbox-outline',
                title: 'No items in backlog',
                subtitle: 'Tasks without due dates will appear here'
            },
            todo: {
                icon: 'mdi-format-list-checks',
                title: 'No scheduled tasks',
                subtitle: 'Tasks with due dates will appear here'
            },
            progress: {
                icon: 'mdi-clock-outline',
                title: 'Nothing in progress',
                subtitle: 'High priority tasks will appear here'
            }
        };
        
        const message = messages[columnId] || messages.backlog;
        
        emptyState.innerHTML = `
            <div class="empty-state-content">
                <i class="mdi ${message.icon} empty-state-icon"></i>
                <div class="empty-state-title">${message.title}</div>
                <div class="empty-state-subtitle">${message.subtitle}</div>
            </div>
        `;
        
        return emptyState;
    }
    
    /**
     * Filter columns by user
     */
    filterColumnsByUser(userId) {
        const dataManager = window.todoKanban?.dataManager;
        if (!dataManager) return;
        
        const filteredTodos = userId ? 
            dataManager.filterTodosByUser(userId) : 
            dataManager.todos;
        
        const todosByColumn = {
            backlog: [],
            todo: [],
            progress: []
        };
        
        filteredTodos.forEach(todo => {
            const column = TodoUtils.getTodoColumn(todo);
            if (column && todosByColumn[column]) {
                todosByColumn[column].push(todo);
            }
        });
        
        this.renderAllColumns(todosByColumn);
    }
    
    /**
     * Search todos in columns
     */
    searchInColumns(query) {
        if (!query) {
            this.cardRenderer.resetCardFilters();
            return;
        }
        
        this.cardRenderer.filterCards(todo => {
            return todo.description.toLowerCase().includes(query.toLowerCase());
        });
    }
    
    /**
     * Highlight overdue todos
     */
    highlightOverdueTodos() {
        const dataManager = window.todoKanban?.dataManager;
        if (!dataManager) return;
        
        const overdueTodos = dataManager.getOverdueTodos();
        overdueTodos.forEach(todo => {
            this.cardRenderer.highlightCard(todo.name, 3000);
        });
    }
    
    /**
     * Get column statistics
     */
    getColumnStats() {
        return {
            counts: { ...this.columnCounts },
            total: Object.values(this.columnCounts).reduce((sum, count) => sum + count, 0)
        };
    }
    
    /**
     * Refresh specific column
     */
    refreshColumn(columnId) {
        const dataManager = window.todoKanban?.dataManager;
        if (!dataManager) return;
        
        const todosByColumn = dataManager.getTodosByColumn();
        const todos = todosByColumn[columnId] || [];
        
        this.renderColumn(columnId, todos);
    }
    
    /**
     * Refresh all columns
     */
    refreshAllColumns() {
        const dataManager = window.todoKanban?.dataManager;
        if (!dataManager) return;
        
        const todosByColumn = dataManager.getTodosByColumn();
        this.renderAllColumns(todosByColumn);
    }
    
    /**
     * Handle column resize (for responsive design)
     */
    handleResize() {
        // Could implement responsive column layout adjustments here
        const isMobile = window.innerWidth < 768;
        
        if (isMobile) {
            // Mobile-specific adjustments
            this.adjustForMobile();
        } else {
            // Desktop adjustments
            this.adjustForDesktop();
        }
    }
    
    /**
     * Adjust layout for mobile
     */
    adjustForMobile() {
        // Implementation for mobile layout adjustments
        document.body.classList.add('mobile-layout');
    }
    
    /**
     * Adjust layout for desktop
     */
    adjustForDesktop() {
        // Implementation for desktop layout adjustments
        document.body.classList.remove('mobile-layout');
    }
    
    /**
     * Save current card states before re-rendering
     */
    saveCardStates(columnBody) {
        const cardStates = {};
        const cards = columnBody.querySelectorAll('.todo-card');
        
        cards.forEach(card => {
            const todoId = card.getAttribute('data-todo-id');
            if (todoId) {
                // Check if card is in expanded state (not collapsed)
                const isExpanded = !card.classList.contains('collapsed');
                cardStates[todoId] = isExpanded;
            }
        });
        
        return cardStates;
    }
    
    /**
     * Save current group states before re-rendering
     */
    saveGroupStates(columnBody) {
        const groupStates = {};
        const groups = columnBody.querySelectorAll('.todo-group');
        
        groups.forEach(group => {
            const referenceText = group.querySelector('.group-reference-text');
            const groupBody = group.querySelector('.todo-group-body');
            
            if (referenceText && groupBody) {
                const groupKey = referenceText.textContent;
                const isExpanded = groupBody.classList.contains('expanded');
                groupStates[groupKey] = isExpanded;
            }
        });
        
        return groupStates;
    }
    
    /**
     * Restore card state after re-rendering
     */
    restoreCardState(cardElement, cardStates) {
        const todoId = cardElement.getAttribute('data-todo-id');
        if (!todoId) return;
        
        // Check persistent storage first, then fallback to temporary cardStates
        const wasExpanded = this.cardStates[todoId] !== undefined ? 
            this.cardStates[todoId] : 
            cardStates[todoId];
        
        if (wasExpanded) {
            // Restore expanded state - remove collapsed class if present
            cardElement.classList.remove('collapsed');
            
            // Update persistent storage to ensure it's saved
            this.cardStates[todoId] = true;
        } else if (wasExpanded === false) {
            // Explicitly collapsed - add collapsed class
            cardElement.classList.add('collapsed');
            
            // Update persistent storage
            this.cardStates[todoId] = false;
        }
        // If undefined, leave in default state
    }
    
    /**
     * Toggle individual card expanded/collapsed state
     */
    toggleCard(todoId, isExpanded) {
        // Save the card state
        this.cardStates[todoId] = isExpanded;
        
        console.log(`Card ${todoId} toggled to ${isExpanded ? 'expanded' : 'collapsed'}`);
    }
    
    /**
     * Restore group state after re-rendering
     */
    restoreGroupState(groupElement, groupStates) {
        const referenceText = groupElement.querySelector('.group-reference-text');
        const groupBody = groupElement.querySelector('.todo-group-body');
        const toggleBtn = groupElement.querySelector('.group-toggle-btn');
        
        if (referenceText && groupBody && toggleBtn) {
            const groupKey = referenceText.textContent;
            
            // Check persistent storage first, then fallback to temporary groupStates
            const wasExpanded = this.groupStates[groupKey] !== undefined ? 
                this.groupStates[groupKey] : 
                groupStates[groupKey];
            
            if (wasExpanded) {
                // Restore expanded state
                groupBody.classList.remove('collapsed');
                groupBody.classList.add('expanded');
                toggleBtn.innerHTML = '<i class="mdi mdi-chevron-up"></i>';
                toggleBtn.title = 'Collapse group';
                
                // Update persistent storage to ensure it's saved
                this.groupStates[groupKey] = true;
            }
            // If not expanded, it stays in default collapsed state
        }
    }
    
    /**
     * Export column data
     */
    exportColumnData() {
        const dataManager = window.todoKanban?.dataManager;
        if (!dataManager) return null;
        
        const todosByColumn = dataManager.getTodosByColumn();
        const stats = this.getColumnStats();
        
        return {
            columns: todosByColumn,
            statistics: stats,
            exported_at: new Date().toISOString()
        };
    }
}

// Add CSS for empty state and todo groups
const emptyStateCSS = `
.empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem 1rem;
    text-align: center;
    opacity: 0.6;
}

.empty-state-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
}

.empty-state-icon {
    font-size: 2rem;
    color: var(--gray-400);
    margin-bottom: 0.5rem;
}

.empty-state-title {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--gray-600);
}

.empty-state-subtitle {
    font-size: 0.75rem;
    color: var(--gray-500);
    line-height: 1.4;
}

/* Todo Group Styles */
.todo-group {
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: var(--card-border-radius);
    margin-bottom: 0.75rem;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    transition: all 0.2s ease;
}

.todo-group:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    border-color: var(--gray-300);
}

.todo-group-header {
    background: var(--gray-50);
    border-bottom: 1px solid var(--gray-200);
    padding: 0.75rem 1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    transition: all 0.2s ease;
}

.todo-group-header:hover {
    background: var(--gray-100);
}

.group-reference {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex: 1;
    min-width: 0;
}

.group-reference-icon {
    color: var(--primary-color);
    font-size: 1rem;
    flex-shrink: 0;
}

.group-reference-text {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--gray-700);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.group-meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-shrink: 0;
}

.group-priority {
    padding: 0.125rem 0.375rem;
    border-radius: 0.25rem;
    font-size: 0.625rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.025em;
}

.group-priority.priority-high {
    background: #fee2e2;
    color: #991b1b;
}

.group-priority.priority-medium {
    background: #fef3c7;
    color: #92400e;
}

.group-priority.priority-low {
    background: #dcfce7;
    color: #166534;
}

.group-count {
    font-size: 0.75rem;
    color: var(--gray-500);
    font-weight: 500;
}

.group-toggle-btn {
    width: 24px;
    height: 24px;
    border: none;
    border-radius: 0.25rem;
    background: transparent;
    color: var(--gray-400);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    font-size: 1rem;
}

.group-toggle-btn:hover {
    background: var(--gray-200);
    color: var(--gray-600);
}

.todo-group-body {
    transition: all 0.3s ease;
    overflow: hidden;
}

.todo-group-body.collapsed {
    max-height: 0;
    opacity: 0;
}

.todo-group-body.expanded {
    max-height: 1000px;
    opacity: 1;
    padding: 0.5rem;
}

.grouped-card {
    margin-bottom: 0.5rem;
    border-left: 3px solid var(--primary-color);
}

.grouped-card:last-child {
    margin-bottom: 0;
}

.mobile-layout .kanban-board {
    flex-direction: column;
    overflow-y: auto;
    overflow-x: hidden;
}

.mobile-layout .kanban-column {
    flex: none;
    margin-bottom: 1rem;
}

.mobile-layout .actions-column {
    order: -1;
    flex-direction: row;
}

.mobile-layout .actions-body {
    flex-direction: row;
    gap: 0.5rem;
}

.mobile-layout .drop-zone {
    height: 60px;
    min-width: 120px;
}

/* Mobile group adjustments */
@media (max-width: 768px) {
    .todo-group-header {
        padding: 0.5rem 0.75rem;
    }
    
    .group-reference-text {
        font-size: 0.8125rem;
    }
    
    .group-meta {
        gap: 0.5rem;
    }
    
    .group-count {
        display: none;
    }
}
`;

// Inject CSS
if (!document.getElementById('todo-column-styles')) {
    const style = document.createElement('style');
    style.id = 'todo-column-styles';
    style.textContent = emptyStateCSS;
    document.head.appendChild(style);
}

// Make TodoColumnManager available globally
window.TodoColumnManager = TodoColumnManager;
