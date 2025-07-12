/**
 * Quick entry component for creating time blocks
 */
class QuickEntryComponent {
    constructor(app) {
        this.app = app;
        this.quickEntryData = {
            selectedProject: null,
            selectedTask: null,
            targetTimeSlot: null,
            targetDate: null,
            targetHour: null,
            targetMinute: null
        };
        this.init();
    }
    
    /**
     * Initialize quick entry functionality
     */
    init() {
        this.setupQuickEntryEvents();
    }
    
    /**
     * Setup quick entry event listeners
     */
    setupQuickEntryEvents() {
        // Close popup when clicking outside
        document.addEventListener('click', (e) => {
            const popup = document.getElementById('quickEntryPopup');
            if (popup && popup.style.display === 'block' && 
                !popup.contains(e.target) && 
                !e.target.classList.contains('time-slot')) {
                this.close();
            }
        });
        
        // Close popup on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen()) {
                this.close();
            }
        });
    }
    
    /**
     * Show quick entry popup for a time slot
     */
    show(timeSlot) {
        const dayColumn = timeSlot.closest('.day-column');
        if (!dayColumn) return;
        
        this.quickEntryData.targetTimeSlot = timeSlot;
        this.quickEntryData.targetDate = dayColumn.dataset.date;
        this.quickEntryData.targetHour = parseInt(timeSlot.dataset.hour);
        this.quickEntryData.targetMinute = parseInt(timeSlot.dataset.minute || 0);
        this.quickEntryData.selectedProject = null;
        this.quickEntryData.selectedTask = null;
        
        this.populateProjects();
        
        const popup = document.getElementById('quickEntryPopup');
        if (popup) {
            popup.style.display = 'block';
            
            // Focus first project item
            const firstProject = popup.querySelector('.quick-entry-item');
            if (firstProject) {
                setTimeout(() => firstProject.focus(), 100);
            }
        }
    }
    
    /**
     * Close quick entry popup
     */
    close() {
        const popup = document.getElementById('quickEntryPopup');
        if (popup) {
            popup.style.display = 'none';
        }
        
        this.resetQuickEntryData();
    }
    
    /**
     * Check if quick entry is open
     */
    isOpen() {
        const popup = document.getElementById('quickEntryPopup');
        return popup && popup.style.display === 'block';
    }
    
    /**
     * Reset quick entry data
     */
    resetQuickEntryData() {
        this.quickEntryData = {
            selectedProject: null,
            selectedTask: null,
            targetTimeSlot: null,
            targetDate: null,
            targetHour: null,
            targetMinute: null
        };
    }
    
    /**
     * Populate projects list
     */
    populateProjects() {
        const projectList = document.getElementById('quickProjectList');
        if (!projectList) return;
        
        projectList.innerHTML = '';
        
        // Get all projects from sidebar
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const projectId = projectGroup.dataset.project;
            const projectName = projectGroup.querySelector('.project-name').textContent;
            const projectColorElement = projectGroup.querySelector('.project-color');
            const projectColor = projectColorElement ? 
                getComputedStyle(projectColorElement).backgroundColor : '#6b7280';
            
            const projectItem = this.createProjectItem(projectId, projectName, projectColor);
            projectList.appendChild(projectItem);
        });
        
        // Clear task list
        this.clearTaskList();
        this.updateCreateButton();
    }
    
    /**
     * Create project item element
     */
    createProjectItem(projectId, projectName, projectColor) {
        const projectItem = DOMUtils.createElement('div', {
            className: 'quick-entry-item',
            dataset: { project: projectId },
            tabindex: '0'
        });
        
        const colorDiv = DOMUtils.createElement('div', {
            className: 'quick-entry-item-color',
            style: { backgroundColor: projectColor }
        });
        
        const nameSpan = DOMUtils.createElement('span', {}, projectName);
        
        projectItem.appendChild(colorDiv);
        projectItem.appendChild(nameSpan);
        
        // Add event listeners
        projectItem.addEventListener('click', () => {
            this.selectProject(projectItem, projectId, projectName, projectColor);
        });
        
        projectItem.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.selectProject(projectItem, projectId, projectName, projectColor);
            }
        });
        
        return projectItem;
    }
    
    /**
     * Select a project
     */
    selectProject(projectElement, projectId, projectName, projectColor) {
        // Clear previous selection
        document.querySelectorAll('#quickProjectList .quick-entry-item').forEach(item => {
            item.classList.remove('selected');
        });
        
        // Select current project
        projectElement.classList.add('selected');
        this.quickEntryData.selectedProject = {
            id: projectId,
            name: projectName,
            color: projectColor
        };
        
        // Populate tasks for selected project
        this.populateTasks(projectId);
    }
    
    /**
     * Populate tasks list for selected project
     */
    populateTasks(projectId) {
        const taskList = document.getElementById('quickTaskList');
        if (!taskList) return;
        
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
                
                const taskItem = this.createTaskItem(taskId, taskName);
                taskList.appendChild(taskItem);
            });
        }
        
        // Reset task selection and update button
        this.quickEntryData.selectedTask = null;
        this.updateCreateButton();
    }
    
    /**
     * Create task item element
     */
    createTaskItem(taskId, taskName) {
        const taskItem = DOMUtils.createElement('div', {
            className: 'quick-entry-item',
            dataset: { task: taskId },
            tabindex: '0'
        });
        
        const colorDiv = DOMUtils.createElement('div', {
            className: 'quick-entry-item-color',
            style: { backgroundColor: this.quickEntryData.selectedProject.color }
        });
        
        const nameSpan = DOMUtils.createElement('span', {}, taskName);
        
        taskItem.appendChild(colorDiv);
        taskItem.appendChild(nameSpan);
        
        // Add event listeners
        taskItem.addEventListener('click', () => {
            this.selectTask(taskItem, taskId, taskName);
        });
        
        taskItem.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.selectTask(taskItem, taskId, taskName);
            }
        });
        
        return taskItem;
    }
    
    /**
     * Select a task
     */
    selectTask(taskElement, taskId, taskName) {
        // Clear previous selection
        document.querySelectorAll('#quickTaskList .quick-entry-item').forEach(item => {
            item.classList.remove('selected');
        });
        
        // Select current task
        taskElement.classList.add('selected');
        this.quickEntryData.selectedTask = {
            id: taskId,
            name: taskName
        };
        
        // Update create button
        this.updateCreateButton();
    }
    
    /**
     * Clear task list
     */
    clearTaskList() {
        const taskList = document.getElementById('quickTaskList');
        if (taskList) {
            taskList.innerHTML = '<div style="padding: 1rem; text-align: center; color: #64748b;">Select a project first</div>';
        }
    }
    
    /**
     * Update create button state
     */
    updateCreateButton() {
        const createBtn = document.getElementById('createQuickEntryBtn');
        if (createBtn) {
            createBtn.disabled = !this.quickEntryData.selectedProject || !this.quickEntryData.selectedTask;
        }
    }
    
    /**
     * Create quick entry
     */
    createEntry() {
        if (!this.quickEntryData.selectedProject || !this.quickEntryData.selectedTask) {
            this.app.components.toast.warning('Please select both project and task');
            return;
        }
        
        // Check for overlaps
        const dayColumn = document.querySelector(`[data-date="${this.quickEntryData.targetDate}"]`);
        const hasOverlap = TimeUtils.checkTimeOverlap(
            dayColumn, 
            this.quickEntryData.targetHour, 
            this.quickEntryData.targetMinute, 
            1 // Default 1 hour
        );
        
        if (hasOverlap) {
            this.app.components.toast.warning('Cannot create entry here - time slot is already occupied');
            return;
        }
        
        // Create the time block
        const newTimeBlock = this.app.managers.timeBlock.createTimeBlock({
            project: this.quickEntryData.selectedProject.id,
            task: this.quickEntryData.selectedTask.id,
            projectName: this.quickEntryData.selectedProject.name,
            taskName: this.quickEntryData.selectedTask.name,
            color: this.quickEntryData.selectedProject.color,
            date: this.quickEntryData.targetDate,
            startHour: this.quickEntryData.targetHour,
            startMinute: this.quickEntryData.targetMinute,
            duration: 1 // Default 1 hour
        });
        
        // Select the newly created time block
        if (newTimeBlock) {
            this.app.selectTimeBlock(newTimeBlock);
        }
        
        this.app.updateDaySummaries();
        this.close();
        this.app.components.toast.success('Time entry created successfully!');
        
        // Auto-save after creating
        this.app.managers.storage.autoSave();
    }
    
    /**
     * Show quick entry with pre-selected project and task
     */
    showWithDefaults(timeSlot, projectId, taskId) {
        this.show(timeSlot);
        
        // Pre-select project
        const projectItem = document.querySelector(`#quickProjectList [data-project="${projectId}"]`);
        if (projectItem) {
            projectItem.click();
            
            // Pre-select task after tasks are populated
            setTimeout(() => {
                const taskItem = document.querySelector(`#quickTaskList [data-task="${taskId}"]`);
                if (taskItem) {
                    taskItem.click();
                }
            }, 100);
        }
    }
    
    /**
     * Get recently used projects and tasks
     */
    getRecentlyUsed() {
        // Get recently used from localStorage or app state
        const recent = localStorage.getItem('quickEntry_recent');
        if (recent) {
            try {
                return JSON.parse(recent);
            } catch (e) {
                return { projects: [], tasks: [] };
            }
        }
        return { projects: [], tasks: [] };
    }
    
    /**
     * Save recently used project and task
     */
    saveRecentlyUsed() {
        if (!this.quickEntryData.selectedProject || !this.quickEntryData.selectedTask) return;
        
        const recent = this.getRecentlyUsed();
        
        // Add to recent projects (keep last 5)
        const projectEntry = {
            id: this.quickEntryData.selectedProject.id,
            name: this.quickEntryData.selectedProject.name,
            color: this.quickEntryData.selectedProject.color
        };
        
        recent.projects = recent.projects.filter(p => p.id !== projectEntry.id);
        recent.projects.unshift(projectEntry);
        recent.projects = recent.projects.slice(0, 5);
        
        // Add to recent tasks (keep last 10)
        const taskEntry = {
            id: this.quickEntryData.selectedTask.id,
            name: this.quickEntryData.selectedTask.name,
            projectId: this.quickEntryData.selectedProject.id
        };
        
        recent.tasks = recent.tasks.filter(t => t.id !== taskEntry.id || t.projectId !== taskEntry.projectId);
        recent.tasks.unshift(taskEntry);
        recent.tasks = recent.tasks.slice(0, 10);
        
        localStorage.setItem('quickEntry_recent', JSON.stringify(recent));
    }
    
    /**
     * Show recently used items at top of lists
     */
    showRecentlyUsed() {
        const recent = this.getRecentlyUsed();
        
        if (recent.projects.length > 0) {
            const projectList = document.getElementById('quickProjectList');
            if (projectList) {
                // Add separator
                const separator = DOMUtils.createElement('div', {
                    className: 'quick-entry-separator',
                    style: {
                        padding: '0.5rem 1rem',
                        fontSize: '0.75rem',
                        color: '#64748b',
                        borderBottom: '1px solid #e2e8f0',
                        fontWeight: '500'
                    }
                }, 'Recently Used');
                
                projectList.insertBefore(separator, projectList.firstChild);
                
                // Add recent projects
                recent.projects.forEach((project, index) => {
                    const projectItem = this.createProjectItem(project.id, project.name, project.color);
                    projectItem.classList.add('recent-item');
                    projectList.insertBefore(projectItem, separator.nextSibling);
                });
            }
        }
    }
}

// Export to global scope
window.QuickEntryComponent = QuickEntryComponent;

// Setup global functions for HTML compatibility
window.closeQuickEntry = function() {
    if (window.app && window.app.components.quickEntry) {
        window.app.components.quickEntry.close();
    }
};

window.createQuickEntry = function() {
    if (window.app && window.app.components.quickEntry) {
        window.app.components.quickEntry.createEntry();
    }
};
