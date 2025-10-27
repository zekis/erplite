/**
 * Todo Column Manager - Handles column operations and layout (Simplified - No Grouping)
 */

class TodoColumnManager {
    constructor(cardRenderer) {
        this.cardRenderer = cardRenderer;
        this.columns = ['backlog', 'todo', 'progress'];
        this.columnElements = {};
        this.columnCounts = {};
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
        
        // Save current card states before clearing
        const cardStates = this.saveCardStates(columnBody);
        
        // Clear existing cards
        columnBody.innerHTML = '';
        
        // Sort todos
        const sortedTodos = this.sortTodos(todos);
        
        // Render individual cards
        sortedTodos.forEach(todo => {
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
        
        // Add as individual card
        this.addIndividualCard(columnBody, todo);
        
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
            
            // Animate out and remove
            this.cardRenderer.animateCardOut(cardElement, () => {
                if (cardElement.parentNode) {
                    cardElement.parentNode.removeChild(cardElement);
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
            // Restore expanded state - remove collapsed class and add expanded class
            cardElement.classList.remove('collapsed');
            cardElement.classList.add('expanded');
            
            // Update the button state to collapse button
            const expandBtn = cardElement.querySelector('.expand-btn');
            if (expandBtn) {
                expandBtn.innerHTML = '<i class="mdi mdi-chevron-up"></i>';
                expandBtn.title = 'Collapse card';
                expandBtn.classList.remove('expand-btn');
                expandBtn.classList.add('collapse-btn');
            }
            
            // Update persistent storage to ensure it's saved
            this.cardStates[todoId] = true;
        } else if (wasExpanded === false) {
            // Explicitly collapsed - add collapsed class and remove expanded class
            cardElement.classList.remove('expanded');
            cardElement.classList.add('collapsed');
            
            // Update the button state to expand button
            const collapseBtn = cardElement.querySelector('.collapse-btn');
            if (collapseBtn) {
                collapseBtn.innerHTML = '<i class="mdi mdi-chevron-down"></i>';
                collapseBtn.title = 'Expand card';
                collapseBtn.classList.remove('collapse-btn');
                collapseBtn.classList.add('expand-btn');
            }
            
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

// Add CSS for empty state (simplified - no group styles)
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
