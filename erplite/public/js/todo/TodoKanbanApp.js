/**
 * Todo Kanban Application - Main application class
 */

class TodoKanbanApp {
    constructor() {
        console.log('Initializing TodoKanbanApp...');
        
        // Initialize managers
        this.dataManager = new TodoDataManager();
        this.cardRenderer = new TodoCardRenderer();
        this.columnManager = new TodoColumnManager(this.cardRenderer);
        this.dragDropManager = new TodoDragDropManager(this.dataManager, this.columnManager);
        this.modalManager = new TodoModalManager(this.dataManager);
        
        // State
        this.currentUserFilter = null;
        this.currentSearchQuery = '';
        this.isInitialized = false;
        this.autoRefreshInterval = null;
        this.autoRefreshEnabled = true;
        // UI toggles
        // showActivities controls whether activity-referencing todos are shown. Default: false (hidden)
        this.showActivities = (localStorage.getItem('todo_show_activities') === '1');
        
        // Initialize the application
        this.initialize();
    }
    
    /**
     * Initialize the application
     */
    async initialize() {
        try {
            console.log('Setting up TodoKanbanApp...');
            
            // Setup UI event listeners
            this.setupEventListeners();
            
            // Initialize modal manager
            this.modalManager.initialize();
            
            // Setup touch events for mobile
            this.dragDropManager.setupTouchEvents();
            
            // Load initial data and render
            await this.loadInitialData();
            
            // Mark as initialized
            this.isInitialized = true;
            
            // Start auto-refresh
            this.startAutoRefresh();
            
            console.log('TodoKanbanApp initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize TodoKanbanApp:', error);
            this.showToast('Failed to initialize application: ' + error.message, 'error');
        }
    }
    
    /**
     * Setup UI event listeners
     */
    setupEventListeners() {
        // Header buttons
        const addTodoBtn = document.getElementById('addTodoBtn');
        const refreshBtn = document.getElementById('refreshBtn');
        
        if (addTodoBtn) {
            addTodoBtn.addEventListener('click', () => this.createBlankTodo());
        }
        
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshTodos());
        }
        
        // Setup user filter dropdown
        this.setupUserFilterDropdown();
        
        // Setup search functionality
        this.setupSearchInput();
        
        // Setup activity reference toggle (hide/show todos referencing activity doctypes)
        this.setupActivityToggle();
        
        // Keyboard shortcuts (global)
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));
        
        // Window events
        window.addEventListener('resize', () => this.handleResize());
        window.addEventListener('beforeunload', () => this.cleanup());
        
        // Setup quick-add inputs
        this.setupQuickAddInputs();
    }
    
    /**
     * Setup search input functionality
     */
    setupSearchInput() {
        const searchInput = document.getElementById('searchInput');
        const clearSearchBtn = document.getElementById('clearSearchBtn');
        
        if (!searchInput) return;
        
        let searchTimeout;
        
        // Handle search input with debounce
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            
            // Show/hide clear button
            if (clearSearchBtn) {
                clearSearchBtn.style.display = query ? 'flex' : 'none';
            }
            
            // Debounce search to avoid too many updates
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.handleSearch(query);
            }, 300);
        });
        
        // Handle clear button
        if (clearSearchBtn) {
            clearSearchBtn.addEventListener('click', () => {
                searchInput.value = '';
                clearSearchBtn.style.display = 'none';
                this.handleSearch('');
                searchInput.focus();
            });
        }
        
        // Handle keyboard shortcuts in search
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                searchInput.value = '';
                if (clearSearchBtn) {
                    clearSearchBtn.style.display = 'none';
                }
                this.handleSearch('');
                searchInput.blur();
            }
        });
    }
    
    /**
     * Setup user filter dropdown functionality
     */
    setupUserFilterDropdown() {
        const userFilterButton = document.getElementById('userFilter');
        const userFilterDropdown = document.getElementById('userFilterDropdown');
        
        if (!userFilterButton || !userFilterDropdown) return;
        
        // Toggle dropdown on button click
        userFilterButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleUserFilterDropdown();
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!userFilterButton.contains(e.target) && !userFilterDropdown.contains(e.target)) {
                this.hideUserFilterDropdown();
            }
        });
        
        // Handle filter option clicks
        userFilterDropdown.addEventListener('click', (e) => {
            const option = e.target.closest('.filter-option');
            if (option) {
                const userId = option.getAttribute('data-user-id');
                this.selectUserFilter(userId);
            }
        });
        
        // Initialize dropdown content
        this.updateUserFilterDropdown();
    }
    
    /**
     * Toggle user filter dropdown
     */
    toggleUserFilterDropdown() {
        const dropdown = document.getElementById('userFilterDropdown');
        const button = document.getElementById('userFilter');
        
        if (!dropdown || !button) return;
        
        if (dropdown.classList.contains('show')) {
            this.hideUserFilterDropdown();
        } else {
            this.showUserFilterDropdown();
        }
    }
    
    /**
     * Show user filter dropdown
     */
    showUserFilterDropdown() {
        const dropdown = document.getElementById('userFilterDropdown');
        const button = document.getElementById('userFilter');
        
        if (!dropdown || !button) return;
        
        // Update dropdown content before showing
        this.updateUserFilterDropdown();
        
        dropdown.classList.add('show');
        button.classList.add('active');
    }
    
    /**
     * Hide user filter dropdown
     */
    hideUserFilterDropdown() {
        const dropdown = document.getElementById('userFilterDropdown');
        const button = document.getElementById('userFilter');
        
        if (!dropdown || !button) return;
        
        dropdown.classList.remove('show');
        button.classList.remove('active');
    }
    
    /**
     * Update user filter dropdown content
     */
    updateUserFilterDropdown() {
        const activeUsersList = document.getElementById('activeUsersList');
        const allUsersCount = document.getElementById('allUsersCount');
        
        if (!activeUsersList || !allUsersCount) return;
        
        // Update "All Users" count
        allUsersCount.textContent = `${this.dataManager.todos.length} tasks`;
        
        // Get users with todos
        const usersWithTodos = this.getUsersWithTodos();
        
        // Clear existing options
        activeUsersList.innerHTML = '';
        
        if (usersWithTodos.length === 0) {
            activeUsersList.innerHTML = '<div class="filter-option disabled">No assigned users</div>';
            return;
        }
        
        // Add user options
        usersWithTodos.forEach(user => {
            const userInitials = this.getUserInitials(user.full_name || user.name);
            // Use assignedName (how todos are actually assigned) for filtering
            const userFilterId = user.assignedName || user.name;
            const isSelected = this.currentUserFilter === userFilterId;
            
            const option = document.createElement('div');
            option.className = `filter-option ${isSelected ? 'active' : ''}`;
            option.setAttribute('data-user-id', userFilterId);
            
            option.innerHTML = `
                <div class="user-avatar">
                    ${userInitials}
                </div>
                <div class="user-info">
                    <div class="user-name">${user.full_name || user.name}</div>
                    <div class="user-count">${user.todoCount} task${user.todoCount !== 1 ? 's' : ''}</div>
                </div>
            `;
            
            activeUsersList.appendChild(option);
        });
    }
    
    /**
     * Select a user filter
     */
    selectUserFilter(userId) {
        this.handleUserFilterChange(userId);
        this.hideUserFilterDropdown();
    }
    
    /**
     * Get user initials for avatar
     */
    getUserInitials(fullName) {
        if (!fullName) return '?';
        
        const parts = fullName.trim().split(' ');
        if (parts.length >= 2) {
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        } else {
            return parts[0].substring(0, 2).toUpperCase();
        }
    }
    
    /**
     * Load initial data
     */
    async loadInitialData() {
        try {
            // Show loading state
            this.showLoading();
            
            // Initial render with current filters (respects "Show Activities" default/persisted state)
            this.applyCurrentFilters();
            
            console.log('Initial data loaded:', {
                totalTodos: this.dataManager.todos.length
            });
            
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showToast('Failed to load todos: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * Refresh todos from server
     */
    async refreshTodos() {
        try {
            this.showLoading();
            
            // Fetch fresh data from server
            await this.dataManager.getTodos();
            
            // Apply current filters
            this.applyCurrentFilters();
            
            this.showToast('Todos refreshed', 'success');
            
        } catch (error) {
            console.error('Failed to refresh todos:', error);
            this.showToast('Failed to refresh todos: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * Apply current filters and render
     */
    applyCurrentFilters() {
        let filteredTodos = this.dataManager.todos;
        
        // Apply user filter
        if (this.currentUserFilter) {
            filteredTodos = this.dataManager.filterTodosByUser(this.currentUserFilter);
        }
        
        // Apply search filter
        if (this.currentSearchQuery) {
            filteredTodos = this.dataManager.searchTodos(this.currentSearchQuery);
        }
        
        // Apply activity toggle: if showActivities is false, exclude todos referencing activity doctypes
        if (!this.showActivities) {
            filteredTodos = filteredTodos.filter(todo => {
                const refType = todo.reference && todo.reference.type;
                return !this.isActivityReference(refType);
            });
        }
        
        // Group by columns
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
        
        // Render columns
        this.columnManager.renderAllColumns(todosByColumn);
    }
    
    /**
     * Handle user filter change
     */
    handleUserFilterChange(userId) {
        this.currentUserFilter = userId || null;
        this.applyCurrentFilters();
        
        // Update the user filter display
        this.updateUserFilterDisplay();
        
        console.log('User filter changed:', userId);
    }
    
    /**
     * Update user filter display with current selection
     */
    updateUserFilterDisplay() {
        const userFilter = document.getElementById('userFilter');
        if (!userFilter) return;
        
        if (this.currentUserFilter) {
            const user = this.dataManager.getUserById(this.currentUserFilter);
            if (user) {
                userFilter.textContent = user.full_name || user.name;
                userFilter.classList.add('active');
            }
        } else {
            userFilter.textContent = 'All Users';
            userFilter.classList.remove('active');
        }
    }
    
    /**
     * Get users who have todos assigned with counts
     */
    getUsersWithTodos() {
        const userCounts = {};
        
        // Count active todos per user - exclude closed/cancelled todos
        this.dataManager.todos.forEach(todo => {
            // Skip closed or cancelled todos
            if (todo.status === 'Closed' || todo.status === 'Cancelled') {
                return;
            }
            
            let userId = null;
            
            // Check different possible user field formats
            if (todo.allocated_to) {
                userId = todo.allocated_to;
            } else if (todo.user && todo.user.name) {
                userId = todo.user.name;
            } else if (todo.user && typeof todo.user === 'string') {
                userId = todo.user;
            }
            
            if (userId) {
                userCounts[userId] = (userCounts[userId] || 0) + 1;
            }
        });
        
        // Try to match assigned names to system users
        const usersWithTodos = [];
        Object.keys(userCounts).forEach(assignedName => {
            // Try multiple matching strategies
            let matchedUser = null;
            
            // Strategy 1: Direct match by name (email)
            matchedUser = this.dataManager.users.find(user => user.name === assignedName);
            
            // Strategy 2: Match by full_name
            if (!matchedUser) {
                matchedUser = this.dataManager.users.find(user => 
                    (user.full_name || '').toLowerCase() === assignedName.toLowerCase()
                );
            }
            
            // Strategy 3: Match by first name
            if (!matchedUser) {
                matchedUser = this.dataManager.users.find(user => {
                    const firstName = (user.full_name || user.name || '').split(' ')[0].toLowerCase();
                    return firstName === assignedName.toLowerCase();
                });
            }
            
            // Strategy 4: Partial match in full name
            if (!matchedUser) {
                matchedUser = this.dataManager.users.find(user => 
                    (user.full_name || '').toLowerCase().includes(assignedName.toLowerCase())
                );
            }
            
            if (matchedUser) {
                usersWithTodos.push({
                    ...matchedUser,
                    assignedName: assignedName, // Keep track of how todos are assigned
                    todoCount: userCounts[assignedName]
                });
            } else {
                // If we can't find user details, create a basic user object
                usersWithTodos.push({
                    name: assignedName,
                    full_name: assignedName,
                    assignedName: assignedName,
                    todoCount: userCounts[assignedName]
                });
            }
        });
        
        // Sort by todo count (descending) then by name
        return usersWithTodos.sort((a, b) => {
            if (b.todoCount !== a.todoCount) {
                return b.todoCount - a.todoCount;
            }
            return (a.full_name || a.name).localeCompare(b.full_name || b.name);
        });
    }
    
    /**
     * Handle search
     */
    handleSearch(query) {
        this.currentSearchQuery = query;
        this.applyCurrentFilters();
        
        console.log('Search query changed:', query);
    }
    
    /**
     * Setup activity toggle UI ("Show Activities" switch)
     */
    setupActivityToggle() {
        const toggle = document.getElementById('activityToggle');
        if (!toggle) return;
        
        // Initialize from state: checked = showActivities
        toggle.checked = !!this.showActivities;
        
        toggle.addEventListener('change', (e) => {
            this.showActivities = !!e.target.checked;
            // Persist user preference: '1' = show activities, '0' = hide activities
            try {
                localStorage.setItem('todo_show_activities', this.showActivities ? '1' : '0');
            } catch (err) {
                // Ignore storage errors (e.g., private mode)
            }
            console.log('Show activities set to', this.showActivities);
            this.applyCurrentFilters();
        });
    }
    
    /**
     * Determine if a doctype is considered an "activity" reference.
     * Only 'Activity' is considered for this filter.
     */
    isActivityReference(doctype) {
        if (!doctype) return false;
        return String(doctype).toLowerCase() === 'activity';
    }
    
    /**
     * Show add todo modal
     */
    showAddTodoModal() {
        this.modalManager.showAddTodoModal();
    }
    
    /**
     * Show edit todo modal
     */
    showEditTodoModal(todo) {
        this.modalManager.showEditTodoModal(todo);
    }
    
    /**
     * Delete todo with confirmation
     */
    async deleteTodo(todo) {
        const confirmed = await this.modalManager.showConfirmModal(
            'Delete Todo',
            `Are you sure you want to delete "${TodoUtils.truncateText(todo.description, 50)}"?`
        );
        
        if (!confirmed) return;
        
        try {
            this.showLoading();
            
            // Delete from backend
            await this.dataManager.deleteTodo(todo.name);
            
            // Remove from UI
            this.columnManager.removeTodoFromColumn(todo.name);
            
            this.showToast('Todo deleted successfully', 'success');
            
        } catch (error) {
            console.error('Failed to delete todo:', error);
            this.showToast('Failed to delete todo: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    /**
     * Create a new blank todo directly in backlog
     */
    async createBlankTodo() {
        try {
            // Show loading state
            const addBtn = document.getElementById('addTodoBtn');
            if (addBtn) {
                addBtn.disabled = true;
                addBtn.innerHTML = '<i class="mdi mdi-loading mdi-spin"></i> Creating...';
            }
            
            // Create blank todo in backend
            const response = await this.dataManager.createTodo({
                description: 'New task - click to edit',
                priority: 'Medium',
                allocated_to: this.dataManager.currentUser,
                date: null,
                color: null
            });
            
            if (response.success) {
                // Refresh todos to get the new one with proper ID
                await this.refreshTodos();
                
                // Find the newly created todo and make it editable
                const newTodo = this.dataManager.todos.find(t => t.name === response.todo_name);
                if (newTodo) {
                    // Wait a moment for the card to render
                    setTimeout(() => {
                        this.makeCardDescriptionEditable(response.todo_name);
                    }, 100);
                }
                
                if (window.showToast) {
                    window.showToast('New task created - click to edit', 'success');
                }
            } else {
                throw new Error(response.message || 'Failed to create todo');
            }
            
        } catch (error) {
            console.error('Failed to create blank todo:', error);
            if (window.showToast) {
                window.showToast('Failed to create task: ' + error.message, 'error');
            }
        } finally {
            // Restore button state
            const addBtn = document.getElementById('addTodoBtn');
            if (addBtn) {
                addBtn.disabled = false;
                addBtn.innerHTML = '<i class="mdi mdi-plus"></i> Add Todo';
            }
        }
    }
    
    /**
     * Make a card's description editable
     */
    makeCardDescriptionEditable(todoId) {
        const cardElement = document.querySelector(`[data-todo-id="${todoId}"]`);
        if (!cardElement) return;
        
        const descriptionElement = cardElement.querySelector('.card-description');
        if (!descriptionElement) return;
        
        // Focus and select the description for editing
        descriptionElement.focus();
        
        // If it has the default text, select it all for easy replacement
        if (descriptionElement.textContent.includes('New task - click to edit')) {
            const range = document.createRange();
            range.selectNodeContents(descriptionElement);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
        }
    }
    
    /**
     * Show add todo modal (fallback for complex todos)
     */
    showAddTodoModal() {
        if (this.modalManager) {
            this.modalManager.showAddTodoModal();
        }
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(e) {
        // Only handle shortcuts if no input is focused
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.contentEditable === 'true') {
            return;
        }
        
        // Ctrl/Cmd + N: New todo
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            this.createBlankTodo();
        }
        
        // Ctrl/Cmd + R: Refresh
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            this.refreshTodos();
        }
        
        // F: Focus search (if search field exists)
        if (e.key === 'f' && !e.ctrlKey && !e.metaKey) {
            const searchField = document.getElementById('searchInput');
            if (searchField) {
                e.preventDefault();
                searchField.focus();
            }
        }
        
        // Escape: Clear filters
        if (e.key === 'Escape') {
            this.clearAllFilters();
        }
    }
    
    /**
     * Clear all filters
     */
    clearAllFilters() {
        this.currentUserFilter = null;
        this.currentSearchQuery = '';
        
        // Reset UI elements
        const userFilter = document.getElementById('userFilter');
        if (userFilter) {
            userFilter.value = '';
        }
        
        // Re-render with all todos
        const todosByColumn = this.dataManager.getTodosByColumn();
        this.columnManager.renderAllColumns(todosByColumn);
        
        this.showToast('Filters cleared', 'info');
    }
    
    /**
     * Handle window resize
     */
    handleResize() {
        if (this.columnManager) {
            this.columnManager.handleResize();
        }
    }
    
    /**
     * Close all modals
     */
    closeModals() {
        if (this.modalManager) {
            this.modalManager.closeTodoModal();
            this.modalManager.closeConfirmModal();
        }
    }
    
    /**
     * Show loading overlay
     */
    showLoading() {
        if (window.showLoading) {
            window.showLoading();
        }
    }
    
    /**
     * Hide loading overlay
     */
    hideLoading() {
        if (window.hideLoading) {
            window.hideLoading();
        }
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
     * Get application statistics
     */
    getStatistics() {
        const stats = this.columnManager.getColumnStats();
        const overdueTodos = this.dataManager.getOverdueTodos();
        const todayTodos = this.dataManager.getTodosDueToday();
        const priorityDistribution = this.dataManager.getPriorityDistribution();
        
        return {
            ...stats,
            overdue: overdueTodos.length,
            dueToday: todayTodos.length,
            priorities: priorityDistribution,
            users: this.dataManager.users.length,
            isManager: this.dataManager.isManager
        };
    }
    
    /**
     * Export data
     */
    exportData(format = 'json') {
        const data = {
            todos: this.dataManager.todos,
            columns: this.columnManager.exportColumnData(),
            statistics: this.getStatistics(),
            filters: {
                user: this.currentUserFilter,
                search: this.currentSearchQuery
            },
            exported_at: new Date().toISOString(),
            exported_by: this.dataManager.currentUser
        };
        
        if (format === 'json') {
            const jsonString = JSON.stringify(data, null, 2);
            this.downloadFile(jsonString, 'todos-export.json', 'application/json');
        }
        
        return data;
    }
    
    /**
     * Download file
     */
    downloadFile(content, filename, contentType) {
        const blob = new Blob([content], { type: contentType });
        const url = URL.createObjectURL(blob);
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        URL.revokeObjectURL(url);
    }
    
    /**
     * Highlight overdue todos
     */
    highlightOverdueTodos() {
        this.columnManager.highlightOverdueTodos();
    }
    
    /**
     * Get todos by status
     */
    getTodosByStatus(status) {
        return this.dataManager.todos.filter(todo => todo.status === status);
    }
    
    /**
     * Get todos by priority
     */
    getTodosByPriority(priority) {
        return this.dataManager.todos.filter(todo => todo.priority === priority);
    }
    
    /**
     * Get todos by user
     */
    getTodosByUser(userId) {
        return this.dataManager.filterTodosByUser(userId);
    }
    
    /**
     * Search todos
     */
    searchTodos(query) {
        return this.dataManager.searchTodos(query);
    }
    
    /**
     * Add todo programmatically
     */
    async addTodo(todoData) {
        try {
            await this.dataManager.createTodo(todoData);
            await this.refreshTodos();
            return true;
        } catch (error) {
            console.error('Failed to add todo:', error);
            this.showToast('Failed to add todo: ' + error.message, 'error');
            return false;
        }
    }
    
    /**
     * Update todo programmatically
     */
    async updateTodo(todoName, updates) {
        try {
            await this.dataManager.updateTodo(todoName, updates);
            await this.refreshTodos();
            return true;
        } catch (error) {
            console.error('Failed to update todo:', error);
            this.showToast('Failed to update todo: ' + error.message, 'error');
            return false;
        }
    }
    
    /**
     * Get todo by name
     */
    getTodo(todoName) {
        return this.dataManager.getTodoByName(todoName);
    }
    
    /**
     * Check if user can perform action
     */
    canUserPerformAction(action, todo = null) {
        switch (action) {
            case 'create':
                return true; // All users can create todos
            case 'edit':
                return todo ? this.dataManager.canEditTodo(todo) : false;
            case 'delete':
                return todo ? this.dataManager.canDeleteTodo(todo) : false;
            case 'assign':
                return this.dataManager.isManager;
            default:
                return false;
        }
    }
    
    /**
     * Enable/disable drag and drop
     */
    setDragDropEnabled(enabled) {
        if (enabled) {
            this.dragDropManager.enable();
        } else {
            this.dragDropManager.disable();
        }
    }
    
    /**
     * Check if application is initialized
     */
    isReady() {
        return this.isInitialized;
    }
    
    /**
     * Get current state
     */
    getState() {
        return {
            initialized: this.isInitialized,
            totalTodos: this.dataManager.todos.length,
            currentFilters: {
                user: this.currentUserFilter,
                search: this.currentSearchQuery
            },
            statistics: this.getStatistics(),
            dragDropEnabled: this.dragDropManager.isEnabled()
        };
    }
    
    /**
     * Debug information
     */
    debug() {
        console.group('TodoKanbanApp Debug Info');
        console.log('State:', this.getState());
        console.log('Data Manager:', this.dataManager);
        console.log('Column Manager:', this.columnManager);
        console.log('Drag Drop Manager:', this.dragDropManager);
        console.log('Modal Manager:', this.modalManager);
        console.groupEnd();
    }
    
    /**
     * Setup quick-add inputs for each column
     */
    setupQuickAddInputs() {
        const quickAddInputs = document.querySelectorAll('.quick-add-input');
        
        quickAddInputs.forEach(input => {
            let isCreating = false; // Flag to prevent double creation
            
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (!isCreating) {
                        isCreating = true;
                        this.handleQuickAdd(input).finally(() => {
                            isCreating = false;
                        });
                    }
                }
            });
            
            // Remove blur event to prevent double creation
            // Users can press Enter to create, or click away to cancel
        });
    }
    
    /**
     * Handle quick-add todo creation
     */
    async handleQuickAdd(input) {
        const description = input.value.trim();
        if (!description) return;
        
        const column = input.getAttribute('data-column');
        
        try {
            // Show loading state
            input.disabled = true;
            input.placeholder = 'Creating...';
            
            // Determine status based on column
            let status = 'Backlog';
            let priority = 'Medium';
            
            switch (column) {
                case 'backlog':
                    status = 'Backlog';
                    priority = 'Medium';
                    break;
                case 'todo':
                    status = 'Planned';
                    priority = 'Medium';
                    break;
                case 'progress':
                    status = 'Open';
                    priority = 'High';
                    break;
            }
            
            // Create todo with appropriate status
            const response = await this.dataManager.createTodo({
                description: description,
                priority: priority,
                allocated_to: this.dataManager.currentUser,
                date: null,
                color: null
            });
            
            if (response.success) {
                // If not creating in backlog, need to update status
                if (status !== 'Backlog') {
                    await this.dataManager.updateTodoStatus(response.todo_name, status, column);
                }
                
                // Clear input
                input.value = '';
                
                // Refresh todos to show the new one
                await this.refreshTodos();
                
                this.showToast(`Task added to ${column}`, 'success');
            } else {
                throw new Error(response.message || 'Failed to create todo');
            }
            
        } catch (error) {
            console.error('Failed to create quick todo:', error);
            this.showToast('Failed to create task: ' + error.message, 'error');
        } finally {
            // Restore input state
            input.disabled = false;
            input.placeholder = input.getAttribute('placeholder') || 'Add task...';
        }
    }
    
    /**
     * Start auto-refresh timer
     */
    startAutoRefresh() {
        if (!this.autoRefreshEnabled) return;
        
        // Clear any existing interval
        this.stopAutoRefresh();
        
        // Set up new interval for 10 seconds
        this.autoRefreshInterval = setInterval(async () => {
            try {
                // Only refresh if page is visible and no modals are open
                if (!document.hidden && !this.isModalOpen()) {
                    await this.quietRefresh();
                }
            } catch (error) {
                console.error('Auto-refresh failed:', error);
                // Don't show error toast for auto-refresh failures to keep it quiet
            }
        }, 10000); // 10 seconds
        
        console.log('Auto-refresh started (10 second interval)');
    }
    
    /**
     * Stop auto-refresh timer
     */
    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
            console.log('Auto-refresh stopped');
        }
    }
    
    /**
     * Enable/disable auto-refresh
     */
    setAutoRefreshEnabled(enabled) {
        this.autoRefreshEnabled = enabled;
        
        if (enabled) {
            this.startAutoRefresh();
        } else {
            this.stopAutoRefresh();
        }
    }
    
    /**
     * Quiet refresh - updates data without showing loading or success messages
     */
    async quietRefresh() {
        try {
            // Check if user is actively editing any task description
            if (this.isUserEditing()) {
                return;
            }
            
            // Store current data for comparison (only UI-relevant fields)
            const currentTodosHash = this.getUIRelevantDataHash(this.dataManager.todos);
            
            // Fetch fresh data from server without showing loading
            await this.dataManager.getTodos();
            
            // Compare with new data (only UI-relevant fields)
            const newTodosHash = this.getUIRelevantDataHash(this.dataManager.todos);
            
            // Only update UI if data has actually changed
            if (currentTodosHash !== newTodosHash) {
                console.log('Meaningful data changed, updating UI...');
                // Apply current filters and re-render
                this.applyCurrentFilters();
            } else {
                console.log('No meaningful changes detected, skipping UI update');
            }
            
        } catch (error) {
            console.error('Quiet refresh failed:', error);
            // Don't show error messages to keep it quiet
        }
    }
    
    /**
     * Get hash of UI-relevant data only (excluding timestamps and other metadata)
     */
    getUIRelevantDataHash(todos) {
        // Extract only the fields that affect UI display
        const relevantData = todos.map(todo => ({
            name: todo.name,
            description: todo.description,
            status: todo.status,
            priority: todo.priority,
            allocated_to: todo.allocated_to,
            color: todo.color,
            date: todo.date, // due date is UI relevant
            column: todo.column
        }));
        
        return JSON.stringify(relevantData);
    }
    
    /**
     * Check if user is currently editing any task description
     */
    isUserEditing() {
        // Check for focused editable elements
        const activeElement = document.activeElement;
        
        // Check if active element is a card description being edited
        if (activeElement && activeElement.classList.contains('card-description')) {
            return true;
        }
        
        // Check if any card description has the 'editing' class
        const editingDescriptions = document.querySelectorAll('.card-description.editing');
        if (editingDescriptions.length > 0) {
            return true;
        }
        
        // Check if any contenteditable element is focused
        if (activeElement && activeElement.contentEditable === 'true') {
            return true;
        }
        
        // Check for any input fields or textareas that might be focused
        if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
            return true;
        }
        
        return false;
    }
    
    /**
     * Check if any modal is currently open
     */
    isModalOpen() {
        const modals = document.querySelectorAll('.modal');
        return Array.from(modals).some(modal => 
            modal.style.display === 'block' || modal.classList.contains('show')
        );
    }
    
    /**
     * Cleanup resources
     */
    cleanup() {
        console.log('Cleaning up TodoKanbanApp...');
        
        // Stop auto-refresh
        this.stopAutoRefresh();
        
        if (this.dragDropManager) {
            this.dragDropManager.cleanup();
        }
        
        if (this.modalManager) {
            this.modalManager.cleanup();
        }
        
        if (this.dataManager) {
            this.dataManager.clearCache();
        }
        
        this.isInitialized = false;
    }
}

// Make TodoKanbanApp available globally
window.TodoKanbanApp = TodoKanbanApp;

// Auto-initialize if DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('TodoKanbanApp class loaded and ready');
    });
} else {
    console.log('TodoKanbanApp class loaded and ready');
}
