/**
 * Sidebar component for project and task management
 */
class SidebarComponent {
    constructor(app) {
        this.app = app;
        this.pinnedTasks = new Set();
        this.init();
    }
    
    /**
     * Initialize sidebar functionality
     */
    init() {
        this.setupSearchFunctionality();
        this.setupProjectToggling();
        this.setupTaskToggling();
        this.setupPinningFunctionality();
        this.setupWeekNavigation();
        this.loadPinnedTasks();
    }
    
    /**
     * Setup search functionality
     */
    setupSearchFunctionality() {
        // Create search input if it doesn't exist
        this.createSearchInput();
        
        const searchInput = document.getElementById('sidebar-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterProjects(e.target.value);
            });
            
            // Add clear button functionality
            const clearBtn = document.getElementById('search-clear');
            if (clearBtn) {
                clearBtn.addEventListener('click', () => {
                    searchInput.value = '';
                    this.clearFilter();
                });
            }
        }
    }
    
    /**
     * Create search input in sidebar
     */
    createSearchInput() {
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar || document.getElementById('sidebar-search')) return;
        
        const searchContainer = document.createElement('div');
        searchContainer.className = 'search-container';
        searchContainer.innerHTML = `
            <div class="search-input-wrapper">
                <input type="text" id="sidebar-search" placeholder="Search projects and tasks..." class="search-input">
                <button id="search-clear" class="search-clear" title="Clear search">×</button>
            </div>
        `;
        
        // Insert after the sidebar header (which contains the title and week navigation)
        const sidebarHeader = sidebar.querySelector('.sidebar-header');
        if (sidebarHeader) {
            sidebarHeader.parentNode.insertBefore(searchContainer, sidebarHeader.nextSibling);
        } else {
            // Fallback: insert at the top if no header found
            sidebar.insertBefore(searchContainer, sidebar.firstChild);
        }
        
        // Add CSS for search functionality
        this.addSearchStyles();
    }
    
    /**
     * Add CSS styles for search functionality
     */
    addSearchStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .search-container {
                padding: 1rem;
                border-bottom: 1px solid #e2e8f0;
                background: #f8fafc;
            }
            
            .search-input-wrapper {
                position: relative;
                margin-bottom: 0.5rem;
            }
            
            .search-input {
                width: 100%;
                padding: 0.5rem 2rem 0.5rem 0.75rem;
                border: 1px solid #d1d5db;
                border-radius: 0.375rem;
                font-size: 0.875rem;
                background: white;
            }
            
            .search-input:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
            
            .search-clear {
                position: absolute;
                right: 0.5rem;
                top: 50%;
                transform: translateY(-50%);
                background: none;
                border: none;
                font-size: 1.25rem;
                color: #6b7280;
                cursor: pointer;
                padding: 0;
                width: 1.5rem;
                height: 1.5rem;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .search-clear:hover {
                color: #374151;
            }
            
            .search-actions {
                display: flex;
                gap: 0.5rem;
            }
            
            .btn-small {
                padding: 0.25rem 0.5rem;
                font-size: 0.75rem;
                border: 1px solid #d1d5db;
                border-radius: 0.25rem;
                background: white;
                cursor: pointer;
                flex: 1;
            }
            
            .btn-small:hover {
                background: #f3f4f6;
            }
            
            .task-group {
                margin-left: 1rem;
                border-left: 2px solid #e5e7eb;
                padding-left: 0.5rem;
            }
            
            .task-group.collapsed .task-block {
                display: none;
            }
            
            .task-toggle {
                cursor: pointer;
                user-select: none;
                font-size: 0.75rem;
                color: #6b7280;
                margin-right: 0.25rem;
            }
            
            .task-buttons {
                display: flex;
                gap: 0.25rem;
                margin-left: auto;
                align-items: center;
            }
            
            .open-button,
            .pin-button {
                background: none;
                border: none;
                cursor: pointer;
                padding: 0.125rem;
                font-size: 0.875rem;
                color: #9ca3af;
                transition: color 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .open-button:hover {
                color: #3b82f6;
            }
            
            .pin-button:hover {
                color: #6b7280;
            }
            
            .pin-button.pinned {
                color: #6b7280;
            }
            
            .pinned-section {
                border-bottom: 1px solid #e2e8f0;
                margin-bottom: 0.5rem;
                padding-bottom: 0.5rem;
            }
            
            .pinned-section .section-title {
                font-size: 0.75rem;
                font-weight: 600;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 0.5rem;
                display: flex;
                align-items: center;
                gap: 0.25rem;
            }
            
            
            .pinned-tasks-section {
                border-bottom: 1px solid #e2e8f0;
                margin-bottom: 1rem;
                background: #f8fafc;
            }
            
            .pinned-section-header {
                padding: 0.75rem 1rem;
                background: #f1f5f9;
                border-bottom: 1px solid #e2e8f0;
            }
            
            .pinned-section-header .section-title {
                font-size: 0.875rem;
                font-weight: 600;
                color: #374151;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            
            .pinned-section-header .section-icon {
                color: #6b7280;
                font-size: 1rem;
            }
            
            .section-count {
                color: #6b7280;
                font-weight: 400;
                font-size: 0.75rem;
            }
            
            .pinned-tasks-container {
                padding: 0.5rem;
            }
            
            .pinned-task-clone {
                margin-bottom: 0.25rem;
                border-radius: 0.375rem;
                background: white;
                border: 1px solid #e5e7eb;
            }
        `;
        
        document.head.appendChild(style);
    }
    
    /**
     * Setup task expand/collapse functionality
     */
    setupTaskToggling() {
        // This will be called after DOM updates to setup task toggles
        this.refreshTaskToggles();
    }
    
    /**
     * Refresh task toggle functionality
     */
    refreshTaskToggles() {
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const tasks = projectGroup.querySelectorAll('.task-block');
            if (tasks.length > 3) { // Only add toggle if more than 3 tasks
                this.addTaskToggle(projectGroup, tasks);
            }
        });
    }
    
    /**
     * Add task toggle to project group
     */
    addTaskToggle(projectGroup, tasks) {
        // Check if toggle already exists
        if (projectGroup.querySelector('.task-toggle')) return;
        
        const projectHeader = projectGroup.querySelector('.project-header');
        if (!projectHeader) return;
        
        // Create task toggle
        const taskToggle = document.createElement('span');
        taskToggle.className = 'task-toggle';
        taskToggle.textContent = `▼ ${tasks.length} tasks`;
        taskToggle.title = 'Click to expand/collapse tasks';
        
        // Insert after project name
        const projectName = projectHeader.querySelector('.project-name');
        if (projectName) {
            projectName.appendChild(taskToggle);
        }
        
        // Create task group container
        const taskGroup = document.createElement('div');
        taskGroup.className = 'task-group';
        
        // Move tasks to task group
        tasks.forEach(task => {
            taskGroup.appendChild(task);
        });
        
        projectGroup.appendChild(taskGroup);
        
        // Add click handler
        taskToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleTasks(projectGroup, taskToggle);
        });
        
        // Initially collapse if more than 5 tasks
        if (tasks.length > 5) {
            this.toggleTasks(projectGroup, taskToggle);
        }
    }
    
    /**
     * Toggle task visibility
     */
    toggleTasks(projectGroup, taskToggle) {
        const taskGroup = projectGroup.querySelector('.task-group');
        if (!taskGroup) return;
        
        taskGroup.classList.toggle('collapsed');
        
        const isCollapsed = taskGroup.classList.contains('collapsed');
        const taskCount = taskGroup.querySelectorAll('.task-block').length;
        
        taskToggle.textContent = `${isCollapsed ? '▶' : '▼'} ${taskCount} tasks`;
    }
    
    /**
     * Setup pinning functionality
     */
    setupPinningFunctionality() {
        // Load pinned tasks from localStorage first for immediate UI
        this.loadPinnedTasks();
        
        // Add pin buttons with current state
        this.addPinButtons();
        
        // Then fetch from backend and sync
        this.fetchHeartStatusFromBackend().then(() => {
            // Refresh pin buttons after backend sync
            this.refreshPinButtons();
            this.reorganizeTasks();
        });
    }
    
    /**
     * Fetch heart status from Frappe backend
     */
    fetchHeartStatusFromBackend() {
        return new Promise((resolve) => {
            if (typeof frappe === 'undefined' || !frappe.call) {
                console.warn('Frappe not available, using localStorage only');
                resolve();
                return;
            }
            
            // Get all task IDs from the sidebar
            const taskIds = [];
            document.querySelectorAll('.task-block').forEach(taskBlock => {
                const taskId = taskBlock.dataset.task;
                if (taskId) {
                    taskIds.push(taskId);
                }
            });
            
            if (taskIds.length === 0) {
                resolve();
                return;
            }
            
            // Fetch heart status for all tasks using Comment doctype with comment_type = "Like"
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Comment',
                    filters: {
                        comment_type: 'Like',
                        reference_doctype: 'Task',
                        reference_name: ['in', taskIds],
                        owner: frappe.session.user
                    },
                    fields: ['reference_name']
                },
                callback: (r) => {
                    if (r.message) {
                        // Update pinned tasks based on backend data
                        this.syncPinnedTasksFromBackend(r.message);
                    }
                    resolve();
                },
                error: (err) => {
                    console.warn('Failed to fetch heart status from backend:', err);
                    resolve();
                }
            });
        });
    }
    
    /**
     * Sync pinned tasks from backend heart status
     */
    syncPinnedTasksFromBackend(likeRecords) {
        // Clear existing pinned tasks
        this.pinnedTasks.clear();
        
        // Process like records from backend
        likeRecords.forEach(likeRecord => {
            const taskId = likeRecord.reference_name;
            // Find the project for this task
            const taskBlock = document.querySelector(`[data-task="${taskId}"]`);
            if (taskBlock) {
                const projectId = taskBlock.dataset.project;
                const taskKey = `${projectId}:${taskId}`;
                this.pinnedTasks.add(taskKey);
            }
        });
        
        // Save to localStorage for offline access
        this.savePinnedTasks();
        
        console.log(`Synced ${this.pinnedTasks.size} pinned tasks from backend`);
    }
    
    /**
     * Add pin buttons to task blocks
     */
    addPinButtons() {
        document.querySelectorAll('.task-block').forEach(taskBlock => {
            if (taskBlock.querySelector('.pin-button')) return; // Already has pin button
            
            // Create button container
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'task-buttons';
            
            // Create open in desk button
            const openButton = document.createElement('button');
            openButton.className = 'open-button mdi';
            openButton.innerHTML = '<i class="mdi mdi-open-in-new"></i>';
            openButton.title = 'Open task in desk view';
            
            // Create pin button
            const pinButton = document.createElement('button');
            pinButton.className = 'pin-button mdi';
            pinButton.innerHTML = '<i class="mdi mdi-pin-outline"></i>'; // Outline pin icon
            pinButton.title = 'Pin this task to top';
            
            const taskId = taskBlock.dataset.task;
            const projectId = taskBlock.dataset.project;
            const taskKey = `${projectId}:${taskId}`;
            
            // Set initial pin state
            if (this.pinnedTasks.has(taskKey)) {
                pinButton.innerHTML = '<i class="mdi mdi-pin"></i>'; // Filled pin icon
                pinButton.classList.add('pinned');
                pinButton.title = 'Unpin this task';
                taskBlock.classList.add('pinned');
            }
            
            // Add event listeners
            openButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.openTaskInDesk(taskId);
            });
            
            pinButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.togglePin(taskBlock, pinButton);
            });
            
            // Add buttons to container
            buttonContainer.appendChild(openButton);
            buttonContainer.appendChild(pinButton);
            
            taskBlock.appendChild(buttonContainer);
        });
    }
    
    /**
     * Refresh pin button states after backend sync
     */
    refreshPinButtons() {
        document.querySelectorAll('.task-block').forEach(taskBlock => {
            const pinButton = taskBlock.querySelector('.pin-button');
            if (!pinButton) return;
            
            const taskId = taskBlock.dataset.task;
            const projectId = taskBlock.dataset.project;
            const taskKey = `${projectId}:${taskId}`;
            
            // Update pin button state based on current pinned tasks
            if (this.pinnedTasks.has(taskKey)) {
                pinButton.innerHTML = '<i class="mdi mdi-pin"></i>'; // Filled pin icon
                pinButton.classList.add('pinned');
                pinButton.title = 'Unpin this task';
                taskBlock.classList.add('pinned');
            } else {
                pinButton.innerHTML = '<i class="mdi mdi-pin-outline"></i>'; // Outline pin icon
                pinButton.classList.remove('pinned');
                pinButton.title = 'Pin this task to top';
                taskBlock.classList.remove('pinned');
            }
        });
    }
    
    /**
     * Open task in Frappe desk view
     */
    openTaskInDesk(taskId) {
        if (typeof frappe !== 'undefined' && frappe.set_route) {
            frappe.set_route('Form', 'Task', taskId);
        } else {
            // Fallback: open in new tab
            const url = `/app/task/${taskId}`;
            window.open(url, '_blank');
        }
    }
    
    /**
     * Toggle pin state of a task
     */
    togglePin(taskBlock, pinButton) {
        const taskId = taskBlock.dataset.task;
        const projectId = taskBlock.dataset.project;
        const taskKey = `${projectId}:${taskId}`;
        
        if (this.pinnedTasks.has(taskKey)) {
            // Unpin
            this.pinnedTasks.delete(taskKey);
            
            // Update the cloned task button (if this is a clone)
            pinButton.innerHTML = '<i class="mdi mdi-pin-outline"></i>'; // Outline pin icon
            pinButton.classList.remove('pinned');
            pinButton.title = 'Pin this task to top';
            taskBlock.classList.remove('pinned');
            
            // Find and update the original task in the project section
            const originalTask = document.querySelector(`[data-project="${projectId}"][data-task="${taskId}"]:not(.pinned-task-clone)`);
            if (originalTask) {
                const originalPinButton = originalTask.querySelector('.pin-button');
                if (originalPinButton) {
                    originalPinButton.innerHTML = '<i class="mdi mdi-pin-outline"></i>';
                    originalPinButton.classList.remove('pinned');
                    originalPinButton.title = 'Pin this task to top';
                }
                originalTask.classList.remove('pinned');
                
                // Show the original task back in its project
                originalTask.style.display = '';
                originalTask.classList.remove('hidden-pinned');
            }
            
            // Use Frappe's API to remove from favorites
            this.updateFrappeHeart(taskId, false);
        } else {
            // Pin
            this.pinnedTasks.add(taskKey);
            
            // Update the current task button
            pinButton.innerHTML = '<i class="mdi mdi-pin"></i>'; // Filled pin icon
            pinButton.classList.add('pinned');
            pinButton.title = 'Unpin this task';
            taskBlock.classList.add('pinned');
            
            // Find and update the original task in the project section (if this is not the original)
            if (taskBlock.classList.contains('pinned-task-clone')) {
                const originalTask = document.querySelector(`[data-project="${projectId}"][data-task="${taskId}"]:not(.pinned-task-clone)`);
                if (originalTask) {
                    const originalPinButton = originalTask.querySelector('.pin-button');
                    if (originalPinButton) {
                        originalPinButton.innerHTML = '<i class="mdi mdi-pin"></i>';
                        originalPinButton.classList.add('pinned');
                        originalPinButton.title = 'Unpin this task';
                    }
                    originalTask.classList.add('pinned');
                }
            }
            
            // Use Frappe's API to add to favorites
            this.updateFrappeHeart(taskId, true);
        }
        
        this.savePinnedTasks();
        this.reorganizeTasks();
    }
    
    /**
     * Update Frappe's heart/favorite status
     */
    updateFrappeHeart(taskId, isPinned) {
        if (typeof frappe === 'undefined' || !frappe.call) {
            console.warn('Frappe not available for heart update');
            return;
        }

        console.log(`Attempting to ${isPinned ? 'pin' : 'unpin'} task ${taskId}`);

        if (isPinned) {
            // First check if already liked to avoid duplicates
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Comment',
                    filters: {
                        comment_type: 'Like',
                        reference_doctype: 'Task',
                        reference_name: taskId,
                        owner: frappe.session.user
                    },
                    fields: ['name']
                },
                callback: (r) => {
                    if (r.message && r.message.length > 0) {
                        console.log(`Task ${taskId} already liked by user`);
                    } else {
                        // Insert new like
                        frappe.call({
                            method: 'frappe.client.insert',
                            args: {
                                doc: {
                                    doctype: 'Comment',
                                    comment_type: 'Like',
                                    reference_doctype: 'Task',
                                    reference_name: taskId,
                                    content: 'Liked'
                                }
                            },
                            callback: (insertResponse) => {
                                console.log(`Task ${taskId} pinned successfully in backend`);
                            },
                            error: (err) => {
                                console.error('Failed to insert like comment:', err);
                                if (this.app && this.app.components && this.app.components.toast) {
                                    this.app.components.toast.show(
                                        `Failed to sync pin status with server for task ${taskId}`, 
                                        'warning'
                                    );
                                }
                            }
                        });
                    }
                },
                error: (err) => {
                    console.error('Failed to check existing likes:', err);
                }
            });
        } else {
            // Remove like by deleting the Comment record
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Comment',
                    filters: {
                        comment_type: 'Like',
                        reference_doctype: 'Task',
                        reference_name: taskId,
                        owner: frappe.session.user
                    },
                    fields: ['name']
                },
                callback: (r) => {
                    if (r.message && r.message.length > 0) {
                        // Delete the like comment
                        frappe.call({
                            method: 'frappe.client.delete',
                            args: {
                                doctype: 'Comment',
                                name: r.message[0].name
                            },
                            callback: (deleteResponse) => {
                                console.log(`Task ${taskId} unpinned successfully in backend`);
                            },
                            error: (err) => {
                                console.error('Failed to delete like comment:', err);
                                if (this.app && this.app.components && this.app.components.toast) {
                                    this.app.components.toast.show(
                                        `Failed to remove pin status from server for task ${taskId}`, 
                                        'warning'
                                    );
                                }
                            }
                        });
                    } else {
                        console.log(`No like found to remove for task ${taskId}`);
                    }
                },
                error: (err) => {
                    console.error('Failed to find like comment to delete:', err);
                }
            });
        }
    }
    
    /**
     * Reorganize tasks to show pinned ones at top
     */
    reorganizeTasks() {
        // Create or update the dedicated pinned tasks section
        this.createPinnedTasksSection();
        
        // Hide pinned tasks from their original project locations (don't remove them)
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const taskContainer = projectGroup.querySelector('.task-group') || projectGroup;
            const tasks = Array.from(taskContainer.querySelectorAll('.task-block'));
            
            // Hide pinned tasks from project groups (they'll be in the pinned section)
            tasks.forEach(task => {
                const taskKey = `${task.dataset.project}:${task.dataset.task}`;
                if (this.pinnedTasks.has(taskKey)) {
                    task.style.display = 'none';
                    task.classList.add('hidden-pinned');
                } else {
                    task.style.display = '';
                    task.classList.remove('hidden-pinned');
                }
            });
            
            // Sort remaining visible tasks alphabetically
            const visibleTasks = Array.from(taskContainer.querySelectorAll('.task-block:not(.hidden-pinned)'));
            visibleTasks.sort((a, b) => {
                return a.dataset.taskName.localeCompare(b.dataset.taskName);
            });
            
            // Reorder visible tasks in DOM
            visibleTasks.forEach(task => {
                taskContainer.appendChild(task);
            });
        });
    }
    
    /**
     * Create dedicated pinned tasks section at top of sidebar
     */
    createPinnedTasksSection() {
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar) {
            console.warn('Sidebar not found');
            return;
        }
        
        // Remove existing pinned section
        const existingPinnedSection = document.getElementById('pinned-tasks-section');
        if (existingPinnedSection) {
            existingPinnedSection.remove();
        }
        
        // If no pinned tasks, don't create section
        if (this.pinnedTasks.size === 0) {
            console.log('No pinned tasks to display');
            return;
        }
        
        console.log(`Creating pinned section for ${this.pinnedTasks.size} tasks:`, [...this.pinnedTasks]);
        
        // Create pinned tasks section
        const pinnedSection = document.createElement('div');
        pinnedSection.id = 'pinned-tasks-section';
        pinnedSection.className = 'pinned-tasks-section';
        
        // Create section header
        const sectionHeader = document.createElement('div');
        sectionHeader.className = 'pinned-section-header';
        sectionHeader.innerHTML = `
            <div class="section-title">
                <i class="mdi mdi-pin section-icon"></i>
                <span class="section-text">Pinned Tasks</span>
                <span class="section-count">(${this.pinnedTasks.size})</span>
            </div>
        `;
        
        pinnedSection.appendChild(sectionHeader);
        
        // Create container for pinned tasks
        const pinnedTasksContainer = document.createElement('div');
        pinnedTasksContainer.className = 'pinned-tasks-container';
        
        // Collect all pinned tasks and clone them
        const pinnedTaskElements = [];
        this.pinnedTasks.forEach(taskKey => {
            const [projectId, taskId] = taskKey.split(':');
            console.log(`Looking for task: project=${projectId}, task=${taskId}`);
            
            // Try multiple selectors to find the original task
            let originalTask = document.querySelector(`[data-project="${projectId}"][data-task="${taskId}"]`);
            
            // If not found, try looking in hidden tasks
            if (!originalTask) {
                originalTask = document.querySelector(`[data-project="${projectId}"][data-task="${taskId}"].hidden-pinned`);
            }
            
            // If still not found, try without hidden class
            if (!originalTask) {
                const allTasks = document.querySelectorAll(`[data-task="${taskId}"]`);
                console.log(`Found ${allTasks.length} tasks with ID ${taskId}`);
                originalTask = Array.from(allTasks).find(task => task.dataset.project === projectId);
            }
            
            if (originalTask) {
                console.log(`Found original task for ${taskKey}:`, originalTask);
                
                const clonedTask = originalTask.cloneNode(true);
                clonedTask.classList.add('pinned-task-clone');
                clonedTask.classList.remove('hidden-pinned'); // Make sure it's visible
                clonedTask.style.display = ''; // Ensure it's not hidden
                
                // Re-add event listeners to cloned buttons
                this.setupClonedTaskButtons(clonedTask, taskId);
                
                pinnedTaskElements.push({
                    element: clonedTask,
                    taskName: clonedTask.dataset.taskName || 'Unknown Task',
                    projectName: this.getProjectName(projectId) || 'Unknown Project'
                });
            } else {
                console.warn(`Could not find original task for ${taskKey}`);
            }
        });
        
        console.log(`Found ${pinnedTaskElements.length} pinned task elements to display`);
        
        // Sort pinned tasks alphabetically
        pinnedTaskElements.sort((a, b) => {
            const aName = `${a.projectName} - ${a.taskName}`;
            const bName = `${b.projectName} - ${b.taskName}`;
            return aName.localeCompare(bName);
        });
        
        // Add sorted pinned tasks to container
        pinnedTaskElements.forEach((item, index) => {
            console.log(`Adding pinned task ${index + 1}:`, item.taskName);
            pinnedTasksContainer.appendChild(item.element);
        });
        
        pinnedSection.appendChild(pinnedTasksContainer);
        
        // Insert pinned section after search container
        const searchContainer = document.querySelector('.search-container');
        if (searchContainer) {
            searchContainer.parentNode.insertBefore(pinnedSection, searchContainer.nextSibling);
            console.log('Inserted pinned section after search container');
        } else {
            sidebar.insertBefore(pinnedSection, sidebar.firstChild);
            console.log('Inserted pinned section at top of sidebar');
        }
        
        console.log('Pinned tasks section created successfully');
    }
    
    /**
     * Setup event listeners for cloned task buttons
     */
    setupClonedTaskButtons(clonedTask, taskId) {
        const openButton = clonedTask.querySelector('.open-button');
        const pinButton = clonedTask.querySelector('.pin-button');
        
        if (openButton) {
            openButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.openTaskInDesk(taskId);
            });
        }
        
        if (pinButton) {
            pinButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.togglePin(clonedTask, pinButton);
            });
        }
        
        // Setup drag functionality for cloned tasks
        this.setupClonedTaskDrag(clonedTask);
    }
    
    /**
     * Setup drag functionality for cloned pinned tasks
     */
    setupClonedTaskDrag(clonedTask) {
        // Make sure the cloned task is draggable
        clonedTask.draggable = true;
        
        clonedTask.addEventListener('dragstart', (e) => {
            clonedTask.classList.add('dragging');
            
            const taskData = {
                project: clonedTask.dataset.project,
                task: clonedTask.dataset.task,
                projectName: clonedTask.dataset.projectName,
                taskName: clonedTask.dataset.taskName,
                color: clonedTask.dataset.color,
                isExistingBlock: false // This is a new task from sidebar, not an existing time block
            };
            
            e.dataTransfer.setData('text/plain', JSON.stringify(taskData));
            e.dataTransfer.effectAllowed = 'copy';
        });
        
        clonedTask.addEventListener('dragend', (e) => {
            clonedTask.classList.remove('dragging');
        });
    }
    
    /**
     * Save pinned tasks to localStorage
     */
    savePinnedTasks() {
        localStorage.setItem('timesheet_pinned_tasks', JSON.stringify([...this.pinnedTasks]));
    }
    
    /**
     * Load pinned tasks from localStorage
     */
    loadPinnedTasks() {
        const saved = localStorage.getItem('timesheet_pinned_tasks');
        if (saved) {
            try {
                const pinnedArray = JSON.parse(saved);
                this.pinnedTasks = new Set(pinnedArray);
            } catch (e) {
                console.warn('Failed to load pinned tasks:', e);
                this.pinnedTasks = new Set();
            }
        }
    }
    
    /**
     * Setup project collapsing/expanding
     */
    setupProjectToggling() {
        document.querySelectorAll('.project-header').forEach(header => {
            header.addEventListener('click', (e) => {
                // Don't toggle if clicking on buttons
                if (e.target.closest('.task-buttons') || e.target.closest('button')) {
                    return;
                }
                
                const projectGroup = header.closest('.project-group');
                if (projectGroup) {
                    this.toggleProject(projectGroup);
                }
            });
        });
    }
    
    /**
     * Setup week navigation
     */
    setupWeekNavigation() {
        // Week navigation buttons are handled by CalendarManager
        // This is just for any sidebar-specific navigation features
    }
    
    /**
     * Toggle project visibility
     */
    toggleProject(projectGroup) {
        projectGroup.classList.toggle('collapsed');
        
        // Update toggle icon
        const toggle = projectGroup.querySelector('.project-toggle');
        if (toggle) {
            if (projectGroup.classList.contains('collapsed')) {
                toggle.textContent = '▶';
            } else {
                toggle.textContent = '▼';
            }
        }
        
        // Save collapsed state to localStorage
        this.saveProjectStates();
    }
    
    /**
     * Toggle project by name (for global function compatibility)
     */
    toggleProjectByName(projectName) {
        const projectGroup = document.querySelector(`[data-project="${projectName}"]`);
        if (projectGroup) {
            this.toggleProject(projectGroup);
        }
    }
    
    /**
     * Expand all projects
     */
    expandAllProjects() {
        document.querySelectorAll('.project-group.collapsed').forEach(projectGroup => {
            this.toggleProject(projectGroup);
        });
    }
    
    /**
     * Collapse all projects
     */
    collapseAllProjects() {
        document.querySelectorAll('.project-group:not(.collapsed)').forEach(projectGroup => {
            this.toggleProject(projectGroup);
        });
    }
    
    /**
     * Save project collapsed states to localStorage
     */
    saveProjectStates() {
        const states = {};
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const projectName = projectGroup.dataset.project;
            states[projectName] = projectGroup.classList.contains('collapsed');
        });
        
        localStorage.setItem('timesheet_project_states', JSON.stringify(states));
    }
    
    /**
     * Load project collapsed states from localStorage
     */
    loadProjectStates() {
        const saved = localStorage.getItem('timesheet_project_states');
        if (!saved) return;
        
        try {
            const states = JSON.parse(saved);
            Object.entries(states).forEach(([projectName, isCollapsed]) => {
                const projectGroup = document.querySelector(`[data-project="${projectName}"]`);
                if (projectGroup) {
                    if (isCollapsed && !projectGroup.classList.contains('collapsed')) {
                        this.toggleProject(projectGroup);
                    } else if (!isCollapsed && projectGroup.classList.contains('collapsed')) {
                        this.toggleProject(projectGroup);
                    }
                }
            });
        } catch (e) {
            console.warn('Failed to load project states:', e);
        }
    }
    
    /**
     * Filter projects and tasks
     */
    filterProjects(searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const projectName = projectGroup.querySelector('.project-name').textContent.toLowerCase();
            const tasks = projectGroup.querySelectorAll('.task-block');
            
            let projectMatches = projectName.includes(term);
            let hasVisibleTasks = false;
            
            // Check tasks
            tasks.forEach(task => {
                const taskName = task.dataset.taskName.toLowerCase();
                const taskMatches = taskName.includes(term);
                
                if (term === '' || taskMatches || projectMatches) {
                    task.style.display = '';
                    hasVisibleTasks = true;
                } else {
                    task.style.display = 'none';
                }
            });
            
            // Show/hide project based on matches
            if (term === '' || projectMatches || hasVisibleTasks) {
                projectGroup.style.display = '';
                // Expand project if it has matching tasks
                if (hasVisibleTasks && term !== '' && projectGroup.classList.contains('collapsed')) {
                    this.toggleProject(projectGroup);
                }
            } else {
                projectGroup.style.display = 'none';
            }
        });
    }
    
    /**
     * Clear project filter
     */
    clearFilter() {
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            projectGroup.style.display = '';
            projectGroup.querySelectorAll('.task-block').forEach(task => {
                task.style.display = '';
            });
        });
    }
    
    /**
     * Get project statistics
     */
    getProjectStats() {
        const stats = {
            totalProjects: 0,
            totalTasks: 0,
            projectsWithTasks: 0,
            averageTasksPerProject: 0
        };
        
        const projectGroups = document.querySelectorAll('.project-group');
        stats.totalProjects = projectGroups.length;
        
        projectGroups.forEach(projectGroup => {
            const tasks = projectGroup.querySelectorAll('.task-block');
            const taskCount = tasks.length;
            
            stats.totalTasks += taskCount;
            if (taskCount > 0) {
                stats.projectsWithTasks++;
            }
        });
        
        if (stats.totalProjects > 0) {
            stats.averageTasksPerProject = Math.round(stats.totalTasks / stats.totalProjects * 10) / 10;
        }
        
        return stats;
    }
    
    /**
     * Highlight project and task
     */
    highlightProjectTask(projectId, taskId) {
        // Clear existing highlights
        this.clearHighlights();
        
        // Highlight project
        const projectGroup = document.querySelector(`[data-project="${projectId}"]`);
        if (projectGroup) {
            projectGroup.classList.add('highlighted');
            
            // Expand project if collapsed
            if (projectGroup.classList.contains('collapsed')) {
                this.toggleProject(projectGroup);
            }
            
            // Highlight task
            if (taskId) {
                const taskBlock = projectGroup.querySelector(`[data-task="${taskId}"]`);
                if (taskBlock) {
                    taskBlock.classList.add('highlighted');
                    
                    // Scroll task into view
                    DOMUtils.scrollIntoView(taskBlock, { block: 'nearest' });
                }
            }
        }
    }
    
    /**
     * Clear all highlights
     */
    clearHighlights() {
        document.querySelectorAll('.highlighted').forEach(element => {
            element.classList.remove('highlighted');
        });
    }
    
    /**
     * Get project color
     */
    getProjectColor(projectId) {
        const projectGroup = document.querySelector(`[data-project="${projectId}"]`);
        if (projectGroup) {
            const colorElement = projectGroup.querySelector('.project-color');
            if (colorElement) {
                return getComputedStyle(colorElement).backgroundColor;
            }
        }
        return '#6b7280'; // Default color
    }
    
    /**
     * Get project name
     */
    getProjectName(projectId) {
        const projectGroup = document.querySelector(`[data-project="${projectId}"]`);
        if (projectGroup) {
            const nameElement = projectGroup.querySelector('.project-name');
            if (nameElement) {
                return nameElement.textContent;
            }
        }
        return projectId;
    }
    
    /**
     * Get task name
     */
    getTaskName(projectId, taskId) {
        const projectGroup = document.querySelector(`[data-project="${projectId}"]`);
        if (projectGroup) {
            const taskBlock = projectGroup.querySelector(`[data-task="${taskId}"]`);
            if (taskBlock) {
                return taskBlock.dataset.taskName;
            }
        }
        return taskId;
    }
    
    /**
     * Get all projects and tasks data
     */
    getProjectsData() {
        const projects = [];
        
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const projectId = projectGroup.dataset.project;
            const projectName = this.getProjectName(projectId);
            const projectColor = this.getProjectColor(projectId);
            
            const tasks = [];
            projectGroup.querySelectorAll('.task-block').forEach(taskBlock => {
                tasks.push({
                    id: taskBlock.dataset.task,
                    name: taskBlock.dataset.taskName,
                    priority: taskBlock.querySelector('.task-priority')?.textContent || null
                });
            });
            
            projects.push({
                id: projectId,
                name: projectName,
                color: projectColor,
                tasks: tasks,
                isCollapsed: projectGroup.classList.contains('collapsed')
            });
        });
        
        return projects;
    }
    
    /**
     * Show project context menu
     */
    showProjectContextMenu(projectGroup, event) {
        event.preventDefault();
        event.stopPropagation();
        
        const projectId = projectGroup.dataset.project;
        const projectName = this.getProjectName(projectId);
        
        const menuItems = [
            {
                text: 'Expand All Tasks',
                icon: '📂',
                action: () => {
                    if (projectGroup.classList.contains('collapsed')) {
                        this.toggleProject(projectGroup);
                    }
                }
            },
            {
                text: 'Collapse Tasks',
                icon: '📁',
                action: () => {
                    if (!projectGroup.classList.contains('collapsed')) {
                        this.toggleProject(projectGroup);
                    }
                }
            },
            {
                text: 'Highlight in Calendar',
                icon: '🔍',
                action: () => {
                    this.highlightProjectInCalendar(projectId);
                }
            }
        ];
        
        this.app.components.contextMenu.show(event.pageX, event.pageY, menuItems);
    }
    
    /**
     * Highlight project entries in calendar
     */
    highlightProjectInCalendar(projectId) {
        // Clear existing highlights
        document.querySelectorAll('.time-block.project-highlighted').forEach(block => {
            block.classList.remove('project-highlighted');
        });
        
        // Highlight time blocks for this project
        document.querySelectorAll(`.time-block[data-project="${projectId}"]`).forEach(block => {
            block.classList.add('project-highlighted');
        });
        
        // Auto-remove highlight after delay
        setTimeout(() => {
            document.querySelectorAll('.time-block.project-highlighted').forEach(block => {
                block.classList.remove('project-highlighted');
            });
        }, 3000);
        
        this.app.components.toast.info(`Highlighted ${this.getProjectName(projectId)} entries in calendar`);
    }
    
    /**
     * Initialize sidebar after DOM is ready
     */
    initializeAfterLoad() {
        // Load saved project states
        this.loadProjectStates();
        
        // Setup any additional functionality that requires full DOM
        this.setupProjectContextMenus();
        
        // Setup new features
        this.refreshTaskToggles();
        this.addPinButtons();
        this.reorganizeTasks();
    }
    
    /**
     * Setup context menus for projects
     */
    setupProjectContextMenus() {
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            projectGroup.addEventListener('contextmenu', (e) => {
                this.showProjectContextMenu(projectGroup, e);
            });
        });
    }
}

// Export to global scope
window.SidebarComponent = SidebarComponent;

// Setup global function for HTML compatibility
window.toggleProject = function(projectName) {
    if (window.app && window.app.components.sidebar) {
        window.app.components.sidebar.toggleProjectByName(projectName);
    }
};
