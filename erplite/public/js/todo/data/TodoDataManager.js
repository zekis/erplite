/**
 * Todo Data Manager - Handles all API interactions
 */

class TodoDataManager {
    constructor() {
        this.baseUrl = '/api/method/erplite.www.todo.index';
        this.todos = [];
        this.users = [];
        this.currentUser = null;
        this.isManager = false;
        this.loading = false;
        
        // Initialize from window data
        this.initializeFromWindowData();
    }
    
    /**
     * Initialize data from window.todoKanbanData
     */
    initializeFromWindowData() {
        const data = window.todoKanbanData;
        if (data) {
            this.todos = data.todos || [];
            this.users = data.users || [];
            this.currentUser = data.currentUser;
            this.isManager = data.isManager || false;
        }
    }
    
    /**
     * Get all todos
     */
    async getTodos() {
        try {
            this.loading = true;
            
            const response = await this.makeRequest('get_todos');
            
            if (response.message) {
                this.todos = response.message.todos || [];
                return this.todos;
            }
            
            throw new Error('Invalid response format');
            
        } catch (error) {
            console.error('Error fetching todos:', error);
            throw error;
        } finally {
            this.loading = false;
        }
    }
    
    /**
     * Create a new todo
     */
    async createTodo(todoData) {
        try {
            this.loading = true;
            
            const response = await this.makeRequest('create_todo', {
                description: todoData.description,
                priority: todoData.priority || 'Medium',
                allocated_to: todoData.allocated_to,
                date: todoData.date,
                color: todoData.color
            });
            
            if (response.message && response.message.success) {
                // Refresh todos to get the new one
                await this.getTodos();
                return response.message;
            }
            
            throw new Error(response.message?.message || 'Failed to create todo');
            
        } catch (error) {
            console.error('Error creating todo:', error);
            throw error;
        } finally {
            this.loading = false;
        }
    }
    
    /**
     * Update an existing todo
     */
    async updateTodo(todoName, updates) {
        try {
            this.loading = true;
            
            const params = {
                todo_name: todoName,
                ...updates
            };
            
            const response = await this.makeRequest('update_todo', params);
            
            if (response.message && response.message.success) {
                // Update local todo data
                const todoIndex = this.todos.findIndex(t => t.name === todoName);
                if (todoIndex !== -1) {
                    this.todos[todoIndex] = { ...this.todos[todoIndex], ...updates };
                }
                return response.message;
            }
            
            throw new Error(response.message?.message || 'Failed to update todo');
            
        } catch (error) {
            console.error('Error updating todo:', error);
            throw error;
        } finally {
            this.loading = false;
        }
    }
    
    /**
     * Update todo status (for drag and drop)
     */
    async updateTodoStatus(todoName, newStatus, newColumn = null) {
        try {
            this.loading = true;
            
            const response = await this.makeRequest('update_todo_status', {
                todo_name: todoName,
                new_status: newStatus,
                new_column: newColumn
            });
            
            if (response.message && response.message.success) {
                // Remove todo from local array if it's completed/cancelled
                if (newStatus === 'Closed' || newStatus === 'Cancelled') {
                    this.todos = this.todos.filter(t => t.name !== todoName);
                } else {
                    // Update local todo data
                    const todoIndex = this.todos.findIndex(t => t.name === todoName);
                    if (todoIndex !== -1) {
                        this.todos[todoIndex].status = newStatus;
                        if (newColumn === 'progress') {
                            this.todos[todoIndex].priority = 'High';
                        }
                    }
                }
                return response.message;
            }
            
            throw new Error(response.message?.message || 'Failed to update todo status');
            
        } catch (error) {
            console.error('Error updating todo status:', error);
            throw error;
        } finally {
            this.loading = false;
        }
    }
    
    /**
     * Delete a todo
     */
    async deleteTodo(todoName) {
        try {
            this.loading = true;
            
            const response = await this.makeRequest('delete_todo', {
                todo_name: todoName
            });
            
            if (response.message && response.message.success) {
                // Remove from local array
                this.todos = this.todos.filter(t => t.name !== todoName);
                return response.message;
            }
            
            throw new Error(response.message?.message || 'Failed to delete todo');
            
        } catch (error) {
            console.error('Error deleting todo:', error);
            throw error;
        } finally {
            this.loading = false;
        }
    }
    
    /**
     * Get todos grouped by column
     */
    getTodosByColumn() {
        const columns = {
            backlog: [],
            todo: [],
            progress: []
        };
        
        this.todos.forEach(todo => {
            const column = TodoUtils.getTodoColumn(todo);
            if (column && columns[column]) {
                columns[column].push(todo);
            }
        });
        
        return columns;
    }
    
    /**
     * Filter todos by user
     */
    filterTodosByUser(userId) {
        if (!userId) return this.todos;
        
        return this.todos.filter(todo => {
            // Check multiple possible user assignment fields
            if (todo.allocated_to && todo.allocated_to !== 'undefined') {
                return todo.allocated_to === userId;
            } else if (todo.user && todo.user.name) {
                return todo.user.name === userId;
            } else if (todo.user && typeof todo.user === 'string') {
                return todo.user === userId;
            }
            return false;
        });
    }
    
    /**
     * Search todos by description
     */
    searchTodos(query) {
        if (!query) return this.todos;
        
        const lowerQuery = query.toLowerCase();
        return this.todos.filter(todo => 
            todo.description.toLowerCase().includes(lowerQuery)
        );
    }
    
    /**
     * Get todo by name
     */
    getTodoByName(todoName) {
        return this.todos.find(todo => todo.name === todoName);
    }
    
    /**
     * Get user by ID
     */
    getUserById(userId) {
        return this.users.find(user => user.name === userId);
    }
    
    /**
     * Check if current user can edit todo
     */
    canEditTodo(todo) {
        if (this.isManager) return true;
        return todo.allocated_to === this.currentUser;
    }
    
    /**
     * Check if current user can delete todo
     */
    canDeleteTodo(todo) {
        if (this.isManager) return true;
        return todo.allocated_to === this.currentUser;
    }
    
    /**
     * Make API request to Frappe
     */
    async makeRequest(method, params = {}) {
        const url = `${this.baseUrl}.${method}`;
        
        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Frappe-CSRF-Token': this.getCSRFToken()
            },
            body: this.buildFormData(params)
        };
        
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.exc) {
            throw new Error(data.exc);
        }
        
        return data;
    }
    
    /**
     * Get CSRF token from meta tag or cookie
     */
    getCSRFToken() {
        // Try to get from meta tag first
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            return metaToken.getAttribute('content');
        }
        
        // Try to get from cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token') {
                return decodeURIComponent(value);
            }
        }
        
        // Try frappe global if available
        if (typeof frappe !== 'undefined' && frappe.csrf_token) {
            return frappe.csrf_token;
        }
        
        return '';
    }
    
    /**
     * Build form data for POST request
     */
    buildFormData(params) {
        const formData = new URLSearchParams();
        
        for (const [key, value] of Object.entries(params)) {
            if (value !== null && value !== undefined) {
                formData.append(key, value);
            }
        }
        
        return formData;
    }
    
    /**
     * Get loading state
     */
    isLoading() {
        return this.loading;
    }
    
    /**
     * Get todos count by column
     */
    getTodosCountByColumn() {
        const columns = this.getTodosByColumn();
        return {
            backlog: columns.backlog.length,
            todo: columns.todo.length,
            progress: columns.progress.length,
            total: this.todos.length
        };
    }
    
    /**
     * Get overdue todos
     */
    getOverdueTodos() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        return this.todos.filter(todo => {
            if (!todo.date || todo.status !== 'Open') return false;
            
            const dueDate = new Date(todo.date);
            dueDate.setHours(0, 0, 0, 0);
            
            return dueDate < today;
        });
    }
    
    /**
     * Get todos due today
     */
    getTodosDueToday() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        return this.todos.filter(todo => {
            if (!todo.date || todo.status !== 'Open') return false;
            
            const dueDate = new Date(todo.date);
            dueDate.setHours(0, 0, 0, 0);
            
            return dueDate.getTime() === today.getTime();
        });
    }
    
    /**
     * Get user's workload (number of assigned todos)
     */
    getUserWorkload(userId) {
        return this.todos.filter(todo => 
            todo.allocated_to === userId && todo.status === 'Open'
        ).length;
    }
    
    /**
     * Get priority distribution
     */
    getPriorityDistribution() {
        const distribution = { High: 0, Medium: 0, Low: 0 };
        
        this.todos.forEach(todo => {
            if (todo.status === 'Open') {
                distribution[todo.priority] = (distribution[todo.priority] || 0) + 1;
            }
        });
        
        return distribution;
    }
    
    /**
     * Export todos data
     */
    exportTodos(format = 'json') {
        const data = {
            todos: this.todos,
            exported_at: new Date().toISOString(),
            exported_by: this.currentUser
        };
        
        if (format === 'json') {
            return JSON.stringify(data, null, 2);
        }
        
        // Add CSV export if needed
        return data;
    }
    
    /**
     * Clear local cache
     */
    clearCache() {
        this.todos = [];
        this.users = [];
    }
    
    /**
     * Refresh data from server
     */
    async refresh() {
        await this.getTodos();
    }
}

// Make TodoDataManager available globally
window.TodoDataManager = TodoDataManager;
