/**
 * Main Scheduler Application Controller
 * Coordinates all components and manages application state
 */
class SchedulerApp {
    constructor() {
        this.state = {
            currentStartDate: null,
            projects: [],
            resources: [],
            scheduleEntries: [],
            projectColors: {},
            scheduleRows: [], // Array of {project, task, person, entries}
            dateRange: 30,
            isLoading: false
        };
        
        this.init();
    }
    
    /**
     * Initialize the application
     */
    init() {
        console.log('Initializing Scheduler...');
        
        // Load initial data from window object (set by template)
        this.loadInitialData();
        
        // Initialize drag and drop for template cards
        this.initializeTemplateDragDrop();
        
        // Load and render initial data
        this.loadSchedulerData();
        
        console.log('Scheduler initialized successfully');
    }
    
    /**
     * Load initial data from window object
     */
    loadInitialData() {
        if (window.schedulerData) {
            this.state.currentStartDate = window.schedulerData.currentStartDate || this.getTodayString();
            this.state.projects = window.schedulerData.projects || [];
            this.state.resources = window.schedulerData.resources || [];
            this.state.scheduleEntries = window.schedulerData.scheduleEntries || [];
            this.state.projectColors = window.schedulerData.projectColors || {};
        } else {
            this.state.currentStartDate = this.getTodayString();
        }
    }
    
    /**
     * Load scheduler data from API
     */
    async loadSchedulerData() {
        try {
            this.setLoading(true);
            
            // Calculate end date
            const endDate = this.addDays(this.state.currentStartDate, this.state.dateRange);
            
            // Make API calls for both old and new data
            const [projectsResponse, scheduleRowsResponse] = await Promise.all([
                this.apiCall('erplite.scheduler.api.get_scheduler_data', {
                    start_date: this.state.currentStartDate,
                    end_date: endDate
                }),
                this.apiCall('erplite.scheduler.api.get_schedule_rows', {
                    start_date: this.state.currentStartDate,
                    end_date: endDate
                })
            ]);
            
            if (projectsResponse) {
                this.state.projects = projectsResponse.projects || [];
                this.state.resources = projectsResponse.resources || [];
                this.state.projectColors = projectsResponse.project_colors || {};
            }
            
            if (scheduleRowsResponse) {
                this.state.scheduleRows = this.processScheduleRowsFromAPI(scheduleRowsResponse);
            } else {
                this.processScheduleRows();
            }
            
            this.renderAll();
        } catch (error) {
            console.error('Failed to load scheduler data:', error);
            this.showToast('Failed to load scheduler data: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }
    
    /**
     * Process schedule rows from API response (Structure only - no time entries)
     */
    processScheduleRowsFromAPI(scheduleRowsData) {
        const processedRows = [];
        
        // Group schedule rows by project
        const projectGroups = {};
        
        scheduleRowsData.forEach(row => {
            const projectKey = row.project || 'unassigned';
            
            if (!projectGroups[projectKey]) {
                projectGroups[projectKey] = {
                    project: row.project,
                    projectName: row.project_name,
                    rows: []
                };
            }
            
            // Only load the structure - no time entries for frontend development
            projectGroups[projectKey].rows.push({
                type: 'task-row',
                scheduleRowId: row.name,
                project: row.project,
                projectName: row.project_name,
                task: row.task,
                taskName: row.task_name,
                resource: row.resource,
                resourceName: row.resource_name,
                entries: [], // Empty entries for frontend development
                dailyEntries: {} // Empty daily entries for frontend development
            });
        });
        
        // Add default projects that don't have schedule rows yet
        this.addDefaultProjectsToGroups(projectGroups);
        
        // Convert to flat array with project headers and task rows
        Object.keys(projectGroups).sort().forEach(projectKey => {
            const projectGroup = projectGroups[projectKey];
            
            // Add project header row
            processedRows.push({
                type: 'project-header',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                task: null,
                taskName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
            
            // Add existing schedule rows (structure only)
            projectGroup.rows.forEach(row => {
                processedRows.push(row);
            });
            
            // Add blank task row for this project
            processedRows.push({
                type: 'task-row',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                task: null,
                taskName: null,
                resource: null,
                resourceName: null,
                entries: [],
                dailyEntries: {}
            });
        });
        
        return processedRows;
    }
    
    /**
     * Add default projects to project groups
     */
    addDefaultProjectsToGroups(projectGroups) {
        // Get all projects that have status "Active" or "Open"
        const openProjects = this.state.projects.filter(project => 
            project.status === 'Active' || project.status === 'Open'
        );
        
        // For each open project, ensure it exists in project groups
        openProjects.forEach(project => {
            const projectKey = project.name;
            if (!projectGroups[projectKey]) {
                projectGroups[projectKey] = {
                    project: project.name,
                    projectName: project.project_name,
                    rows: []
                };
            }
        });
    }
    
    /**
     * Process schedule entries into rows with project headers and task rows (legacy fallback)
     */
    processScheduleRows() {
        this.state.scheduleRows = [];
        
        // Group entries by project and task
        const projectGroups = {};
        
        this.state.scheduleEntries.forEach(entry => {
            const projectKey = entry.project || 'unassigned';
            const taskKey = entry.task || 'unassigned';
            const resourceKey = entry.resource || 'unassigned';
            
            if (!projectGroups[projectKey]) {
                projectGroups[projectKey] = {
                    project: entry.project,
                    projectName: entry.project_name || entry.project,
                    tasks: {}
                };
            }
            
            if (!projectGroups[projectKey].tasks[taskKey]) {
                projectGroups[projectKey].tasks[taskKey] = {
                    task: entry.task,
                    taskName: entry.task_name || entry.task,
                    resources: {}
                };
            }
            
            if (!projectGroups[projectKey].tasks[taskKey].resources[resourceKey]) {
                projectGroups[projectKey].tasks[taskKey].resources[resourceKey] = {
                    resource: entry.resource,
                    resourceName: entry.resource_name || this.getResourceName(entry.resource),
                    entries: []
                };
            }
            
            projectGroups[projectKey].tasks[taskKey].resources[resourceKey].entries.push(entry);
        });
        
        // Add default projects
        this.addDefaultProjects(projectGroups);
        
        // Convert to flat array with project headers and task rows
        Object.keys(projectGroups).sort().forEach(projectKey => {
            const projectGroup = projectGroups[projectKey];
            
            // Add project header row
            this.state.scheduleRows.push({
                type: 'project-header',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                task: null,
                taskName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
            
            // Add task rows
            Object.keys(projectGroup.tasks).forEach(taskKey => {
                const taskGroup = projectGroup.tasks[taskKey];
                
                Object.keys(taskGroup.resources).forEach(resourceKey => {
                    const resourceGroup = taskGroup.resources[resourceKey];
                    
                    this.state.scheduleRows.push({
                        type: 'task-row',
                        project: projectGroup.project,
                        projectName: projectGroup.projectName,
                        task: taskGroup.task,
                        taskName: taskGroup.taskName,
                        resource: resourceGroup.resource,
                        resourceName: resourceGroup.resourceName,
                        entries: resourceGroup.entries
                    });
                });
                
                // Add blank row for adding more resources to this task
                if (taskGroup.task) {
                    this.state.scheduleRows.push({
                        type: 'task-row',
                        project: projectGroup.project,
                        projectName: projectGroup.projectName,
                        task: taskGroup.task,
                        taskName: taskGroup.taskName,
                        resource: null,
                        resourceName: null,
                        entries: []
                    });
                }
            });
            
            // Add blank task row for this project
            this.state.scheduleRows.push({
                type: 'task-row',
                project: projectGroup.project,
                projectName: projectGroup.projectName,
                task: null,
                taskName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
        });
        
        // No need for empty project rows since we show all active projects
    }
    
    /**
     * Get resource name by ID
     */
    getResourceName(resourceId) {
        if (!resourceId) return 'Unassigned';
        const resource = this.state.resources.find(r => r.name === resourceId);
        return resource ? resource.resource_name : resourceId;
    }
    
    /**
     * Render all components
     */
    renderAll() {
        this.updateDateRange();
        this.renderDateColumns();
        this.renderScheduleRows();
    }
    
    /**
     * Update date range display
     */
    updateDateRange() {
        const startDate = new Date(this.state.currentStartDate);
        const endDate = this.addDays(this.state.currentStartDate, this.state.dateRange - 1);
        
        const formatDate = (date) => {
            return new Date(date).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric',
                year: 'numeric'
            });
        };
        
        const display = document.getElementById('dateRangeDisplay');
        if (display) {
            display.textContent = `${formatDate(startDate)} - ${formatDate(endDate)}`;
        }
    }
    
    /**
     * Render date columns header
     */
    renderDateColumns() {
        const container = document.getElementById('dateColumns');
        if (!container) return;
        
        container.innerHTML = '';
        
        const today = this.getTodayString();
        
        for (let i = 0; i < this.state.dateRange; i++) {
            const date = this.addDays(this.state.currentStartDate, i);
            const dateObj = new Date(date);
            
            const column = document.createElement('div');
            column.className = 'date-column';
            if (date === today) {
                column.classList.add('today');
            }
            
            // Check if it's a weekend (Saturday = 6, Sunday = 0)
            const dayOfWeek = dateObj.getDay();
            if (dayOfWeek === 0 || dayOfWeek === 6) {
                column.classList.add('weekend');
            }
            
            column.innerHTML = `
                <div>${dateObj.toLocaleDateString('en-US', { weekday: 'short' })}</div>
                <div class="date-day">${dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</div>
            `;
            
            container.appendChild(column);
        }
    }
    
    /**
     * Render schedule rows
     */
    renderScheduleRows() {
        const container = document.getElementById('gridBody');
        if (!container) return;
        
        container.innerHTML = '';
        
        this.state.scheduleRows.forEach((row, index) => {
            const rowElement = this.createScheduleRow(row, index);
            container.appendChild(rowElement);
        });
        
        // Render time block cards after all rows are created
        this.renderTimeBlockCards();
    }
    
    /**
     * Render time block cards for schedule rows
     */
    renderTimeBlockCards() {
        // Remove existing time block cards
        document.querySelectorAll('.time-block-card').forEach(card => card.remove());
        
        this.state.scheduleRows.forEach((row, rowIndex) => {
            if (row.type !== 'task-row' || !row.dailyEntries) return;
            
            // Parse entries
            let entries = {};
            try {
                if (typeof row.dailyEntries === 'string') {
                    entries = JSON.parse(row.dailyEntries);
                } else {
                    entries = row.dailyEntries;
                }
            } catch (e) {
                console.warn('Failed to parse entries for row:', rowIndex);
                return;
            }
            
            // Check if it's optimized format or simple daily entries
            if (entries.blocks || entries.individual_days) {
                // Handle optimized format
                if (entries.blocks) {
                    entries.blocks.forEach(block => {
                        this.renderTimeBlockCard(rowIndex, block, 'block', row);
                    });
                }
                
                if (entries.individual_days) {
                    Object.keys(entries.individual_days).forEach(date => {
                        const entry = entries.individual_days[date];
                        this.renderTimeBlockCard(rowIndex, {
                            start_date: date,
                            end_date: date,
                            ...entry
                        }, 'individual', row);
                    });
                }
            } else {
                // Handle simple daily entries format (from templates)
                const sortedDates = Object.keys(entries).sort();
                
                if (sortedDates.length === 0) return;
                
                // Group consecutive dates with identical entries into blocks
                const blocks = this.groupConsecutiveEntries(entries);
                
                blocks.forEach(block => {
                    this.renderTimeBlockCard(rowIndex, block, block.start_date === block.end_date ? 'individual' : 'block', row);
                });
            }
        });
    }
    
    /**
     * Render a single time block card
     */
    renderTimeBlockCard(rowIndex, blockData, type, row) {
        const startDate = blockData.start_date;
        const endDate = blockData.end_date;
        
        // Find the row element
        const rowElement = document.querySelector(`[data-row-index="${rowIndex}"]`);
        if (!rowElement) return;
        
        const daysContainer = rowElement.querySelector('.schedule-days');
        if (!daysContainer) return;
        
        // Calculate position and width
        const startCell = daysContainer.querySelector(`[data-date="${startDate}"]`);
        const endCell = daysContainer.querySelector(`[data-date="${endDate}"]`);
        
        if (!startCell || !endCell) return;
        
        // Create the time block card
        const card = document.createElement('div');
        card.className = 'time-block-card';
        card.dataset.rowIndex = rowIndex;
        card.dataset.startDate = startDate;
        card.dataset.endDate = endDate;
        card.dataset.type = type;
        
        // Set project color
        const projectColor = this.state.projectColors[row.project] || '#3b82f6';
        card.style.setProperty('--project-color', projectColor);
        card.style.background = projectColor;
        card.style.borderColor = projectColor;
        
        // Calculate position
        const startRect = startCell.getBoundingClientRect();
        const endRect = endCell.getBoundingClientRect();
        const containerRect = daysContainer.getBoundingClientRect();
        
        const left = startRect.left - containerRect.left;
        const width = endRect.right - startRect.left;
        
        card.style.left = `${left}px`;
        card.style.width = `${width}px`;
        
        // Add styling based on span
        if (startDate === endDate) {
            card.classList.add('single-day');
        } else {
            card.classList.add('start-day');
            // We'll handle middle and end styling if needed
        }
        
        // Create card content
        const content = document.createElement('div');
        content.className = 'card-content';
        
        const hours = blockData.hours || 8;
        const startTime = blockData.start_time || '09:00';
        const endTime = blockData.end_time || '17:00';
        
        if (type === 'block') {
            const daysCount = this.calculateDaysBetween(startDate, endDate) + 1;
            content.innerHTML = `
                <div class="card-hours">${hours}h × ${daysCount}</div>
                <div class="card-time">${startTime}-${endTime}</div>
                ${row.resourceName ? `<div class="card-resource">${row.resourceName}</div>` : ''}
            `;
        } else {
            content.innerHTML = `
                <div class="card-hours">${hours}h</div>
                <div class="card-time">${startTime}-${endTime}</div>
                ${row.resourceName ? `<div class="card-resource">${row.resourceName}</div>` : ''}
            `;
        }
        
        card.appendChild(content);
        
        // Add resize handles
        const leftHandle = document.createElement('div');
        leftHandle.className = 'resize-handle left';
        leftHandle.addEventListener('mousedown', (e) => this.startResize(e, card, 'left', rowIndex, blockData));
        
        const rightHandle = document.createElement('div');
        rightHandle.className = 'resize-handle right';
        rightHandle.addEventListener('mousedown', (e) => this.startResize(e, card, 'right', rowIndex, blockData));
        
        card.appendChild(leftHandle);
        card.appendChild(rightHandle);
        
        // Add click handler (only on content area, not handles)
        content.addEventListener('click', (e) => {
            e.stopPropagation();
            this.editTimeBlock(rowIndex, blockData, type);
        });
        
        // Position the card
        daysContainer.style.position = 'relative';
        daysContainer.appendChild(card);
    }
    
    /**
     * Calculate days between two dates (inclusive)
     */
    calculateDaysBetween(startDate, endDate) {
        try {
            // Validate that inputs are actually date strings
            if (!startDate || !endDate || typeof startDate !== 'string' || typeof endDate !== 'string') {
                console.warn('Invalid date inputs in calculateDaysBetween:', startDate, endDate);
                return 0;
            }
            
            // Check if inputs look like dates (YYYY-MM-DD format)
            const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
            if (!dateRegex.test(startDate) || !dateRegex.test(endDate)) {
                console.warn('Date format invalid in calculateDaysBetween:', startDate, endDate);
                return 0;
            }
            
            const start = new Date(startDate);
            const end = new Date(endDate);
            
            // Check for invalid dates
            if (isNaN(start.getTime()) || isNaN(end.getTime())) {
                console.warn('Invalid date objects in calculateDaysBetween:', startDate, endDate);
                return 0;
            }
            
            return Math.floor((end - start) / (1000 * 60 * 60 * 24));
        } catch (error) {
            console.error('Error calculating days between dates:', error);
            return 0;
        }
    }
    
    /**
     * Edit a time block
     */
    editTimeBlock(rowIndex, blockData, type) {
        const row = this.state.scheduleRows[rowIndex];
        
        if (type === 'block') {
            const daysCount = this.calculateDaysBetween(blockData.start_date, blockData.end_date) + 1;
            const newHours = prompt(`Edit hours for ${daysCount}-day block (${blockData.start_date} to ${blockData.end_date}):`, blockData.hours);
            
            if (newHours !== null && !isNaN(newHours) && newHours > 0) {
                this.updateTimeBlock(rowIndex, blockData, { hours: parseFloat(newHours) });
            }
        } else {
            const newHours = prompt(`Edit hours for ${blockData.start_date}:`, blockData.hours);
            
            if (newHours !== null && !isNaN(newHours) && newHours > 0) {
                this.updateTimeBlock(rowIndex, blockData, { hours: parseFloat(newHours) });
            }
        }
    }
    
    /**
     * Update a time block
     */
    async updateTimeBlock(rowIndex, blockData, updates) {
        const row = this.state.scheduleRows[rowIndex];
        
        if (!row.scheduleRowId) {
            this.showToast('Schedule row not found', 'error');
            return;
        }
        
        try {
            // Get current entries in daily format for editing
            const response = await this.apiCall('erplite.scheduler.api.get_schedule_row_expanded', {
                schedule_row: row.scheduleRowId
            });
            
            if (response && response.success) {
                const dailyEntries = response.daily_entries;
                
                // Update the affected dates
                const startDate = new Date(blockData.start_date);
                const endDate = new Date(blockData.end_date);
                const currentDate = new Date(startDate);
                
                while (currentDate <= endDate) {
                    const dateStr = currentDate.toISOString().split('T')[0];
                    if (dailyEntries[dateStr]) {
                        Object.assign(dailyEntries[dateStr], updates);
                    }
                    currentDate.setDate(currentDate.getDate() + 1);
                }
                
                // Save the updated entries
                const updateResponse = await this.apiCall('erplite.scheduler.api.update_schedule_row_entries', {
                    schedule_row: row.scheduleRowId,
                    entries_json: JSON.stringify(dailyEntries)
                });
                
                if (updateResponse && updateResponse.success) {
                    // Update local state with optimized entries
                    row.dailyEntries = updateResponse.optimized_entries;
                    
                    this.showToast('Time block updated successfully!', 'success');
                    this.renderTimeBlockCards(); // Re-render cards
                } else {
                    this.showToast('Failed to update time block', 'error');
                }
            }
            
        } catch (error) {
            console.error('Error updating time block:', error);
            this.showToast('Error updating time block: ' + error.message, 'error');
        }
    }
    
    /**
     * Create a schedule row
     */
    createScheduleRow(row, index) {
        const rowElement = document.createElement('div');
        rowElement.className = 'schedule-row';
        rowElement.dataset.rowIndex = index;
        
        // Add row type classes
        if (row.type === 'project-header') {
            rowElement.classList.add('project-header');
            // Set a light shade of the project color as background if available
            if (row.project && this.state.projectColors[row.project]) {
                // Use a 10% opacity version of the project color
                rowElement.style.background = this.hexToRgba(this.state.projectColors[row.project], 0.10);
            }
        } else if (row.type === 'task-row') {
            rowElement.classList.add('task-row');
        }
        
        // Combined Project/Task cell
        const projectTaskCell = document.createElement('div');
        projectTaskCell.className = 'schedule-cell project-task-cell';
        projectTaskCell.dataset.type = 'project-task';
        projectTaskCell.dataset.rowIndex = index;
        
        if (row.type === 'project-header') {
            // Project header row
            if (row.project) {
                projectTaskCell.classList.add('filled');
                projectTaskCell.textContent = row.projectName;
                projectTaskCell.style.setProperty('--project-color', this.state.projectColors[row.project] || '#6b7280');
                projectTaskCell.style.borderLeft = `4px solid var(--project-color)`;
            } else {
                projectTaskCell.classList.add('empty');
                projectTaskCell.textContent = 'Select Project';
                projectTaskCell.addEventListener('click', () => this.showProjectDropdown(projectTaskCell, index));
            }
        } else {
            // Task row
            if (row.task) {
                projectTaskCell.classList.add('filled');
                projectTaskCell.textContent = row.taskName;
                projectTaskCell.style.position = 'relative';
                
                // Add row controls for task rows
                const rowControls = document.createElement('div');
                rowControls.className = 'row-controls';
                rowControls.innerHTML = `
                    <button class="row-control-btn copy-down-btn" title="Copy task down" onclick="copyTaskDown(${index})">
                        <i class="mdi mdi-content-copy"></i>
                    </button>
                    <button class="row-control-btn delete-row-btn" title="Delete task" onclick="deleteScheduleRow(${index})">
                        <i class="mdi mdi-delete"></i>
                    </button>
                `;
                projectTaskCell.appendChild(rowControls);
            } else if (row.project) {
                projectTaskCell.classList.add('empty');
                projectTaskCell.textContent = 'Select Task';
                projectTaskCell.addEventListener('click', () => this.showTaskDropdown(projectTaskCell, index));
            } else {
                projectTaskCell.classList.add('empty');
                projectTaskCell.textContent = 'Select Project First';
            }
        }
        
        // Person cell
        const personCell = document.createElement('div');
        personCell.className = 'schedule-cell person-cell';
        personCell.dataset.type = 'person';
        personCell.dataset.rowIndex = index;
        
        if (row.type === 'project-header') {
            // Project headers show resource count
            personCell.style.visibility = 'visible';
            personCell.style.cursor = 'default';
            personCell.classList.add('filled');
            
            // Calculate unique resources for this project
            const projectRows = this.state.scheduleRows.filter(r => 
                r.project === row.project && r.type === 'task-row' && r.resource
            );
            const uniqueResources = new Set(projectRows.map(r => r.resource));
            const resourceCount = uniqueResources.size;
            
            personCell.textContent = resourceCount > 0 ? `${resourceCount} Resources` : 'No Resources';
            personCell.style.fontSize = '0.875rem';
            personCell.style.color = '#6b7280';
        } else {
            // Task rows can have resources
            personCell.style.visibility = 'visible';
            personCell.style.fontSize = '';
            personCell.style.color = '';
            if (row.resource) {
                personCell.classList.add('filled');
                personCell.textContent = row.resourceName;
            } else {
                personCell.classList.add('empty');
                personCell.textContent = 'Select Resource';
            }
            personCell.addEventListener('click', () => this.showPersonDropdown(personCell, index));
        }
        
        // Day cells
        const daysContainer = document.createElement('div');
        daysContainer.className = 'schedule-days';
        
        for (let i = 0; i < this.state.dateRange; i++) {
            const date = this.addDays(this.state.currentStartDate, i);
            const dayCell = this.createDayCell(row, date, index);
            daysContainer.appendChild(dayCell);
        }
        
        rowElement.appendChild(projectTaskCell);
        rowElement.appendChild(personCell);
        rowElement.appendChild(daysContainer);
        
        return rowElement;
    }
    
    /**
     * Create a day cell
     */
    createDayCell(row, date, rowIndex) {
        const cell = document.createElement('div');
        cell.className = 'day-cell';
        cell.dataset.date = date;
        cell.dataset.rowIndex = rowIndex;
        
        // Check if it's a weekend (Saturday = 6, Sunday = 0)
        const dateObj = new Date(date);
        const dayOfWeek = dateObj.getDay();
        if (dayOfWeek === 0 || dayOfWeek === 6) {
            cell.classList.add('weekend');
        }
        
        // Add drag and drop attributes for both templates and entries
        cell.addEventListener('drop', (e) => this.handleCellDrop(e, rowIndex, date));
        cell.addEventListener('dragover', (e) => e.preventDefault());
        cell.addEventListener('dragenter', (e) => {
            e.preventDefault();
            if (row.project && row.task && row.type === 'task-row') {
                cell.classList.add('drop-zone');
            }
        });
        cell.addEventListener('dragleave', (e) => {
            e.preventDefault();
            cell.classList.remove('drop-zone');
        });
        
        const entriesContainer = document.createElement('div');
        entriesContainer.className = 'day-entries';
        
        if (row.type === 'project-header') {
            // Project header shows daily totals for the project
            if (row.project) {
                // Calculate total hours for this project on this date from Schedule Rows
                let totalHours = 0;
                
                // Get total from Schedule Rows if available
                const projectRows = this.state.scheduleRows.filter(r => 
                    r.project === row.project && r.type === 'task-row' && r.dailyEntries
                );
                
                projectRows.forEach(scheduleRow => {
                    if (scheduleRow.dailyEntries && scheduleRow.dailyEntries[date]) {
                        const entry = scheduleRow.dailyEntries[date];
                        const hours = typeof entry === 'object' ? entry.hours : entry;
                        totalHours += parseFloat(hours) || 0;
                    }
                });
                
                // Fallback to legacy schedule entries
                if (totalHours === 0) {
                    const projectEntries = this.state.scheduleEntries.filter(entry => 
                        entry.project === row.project && entry.schedule_date === date
                    );
                    totalHours = projectEntries.reduce((sum, entry) => sum + (parseFloat(entry.duration) || 0), 0);
                }
                
                // Always show total (including 0)
                const totalElement = document.createElement('div');
                totalElement.className = 'project-total';
                totalElement.textContent = totalHours > 0 ? `${totalHours}h` : '0';
                totalElement.style.fontSize = '0.75rem';
                totalElement.style.fontStyle = 'italic';
                totalElement.style.color = '#6b7280';
                totalElement.style.textAlign = 'center';
                totalElement.style.padding = '0.25rem';
                entriesContainer.appendChild(totalElement);
                
                if (totalHours > 0) {
                    cell.classList.add('has-entry');
                }
            }
            
            // Project headers are not clickable for entries
            cell.style.cursor = 'default';
            cell.classList.add('disabled');
        } else {
            // Task row logic - check for time entries in daily entries JSON
            let hasTimeEntry = false;
            
            // Check Schedule Row daily entries first
            if (row.dailyEntries && row.dailyEntries[date]) {
                const entry = row.dailyEntries[date];
                const hours = typeof entry === 'object' ? entry.hours : entry;
                
                if (hours > 0) {
                    hasTimeEntry = true;
                    const timeEntryElement = this.createTimeEntry(entry, date, row);
                    entriesContainer.appendChild(timeEntryElement);
                }
            }
            
            // Fallback to legacy schedule entries
            if (!hasTimeEntry) {
                const entries = row.entries.filter(entry => entry.schedule_date === date);
                
                entries.forEach(entry => {
                    const entryElement = this.createScheduleEntry(entry);
                    entriesContainer.appendChild(entryElement);
                });
                
                if (entries.length > 0) {
                    hasTimeEntry = true;
                }
            }
            
            if (hasTimeEntry) {
                cell.classList.add('has-entry');
            }
            
            // Add simple hover functionality for valid cells
            if (row.project && row.task) {
                cell.classList.add('valid-cell');
                cell.style.cursor = 'pointer';
                
                // Add simple hover effect
                cell.addEventListener('mouseenter', () => {
                    if (!hasTimeEntry) {
                        cell.classList.add('hover-landing-zone');
                    }
                });
                
                cell.addEventListener('mouseleave', () => {
                    cell.classList.remove('hover-landing-zone');
                });
                
            } else if (!hasTimeEntry) {
                cell.classList.add('disabled');
                cell.style.cursor = 'not-allowed';
                cell.title = 'Select project and task first';
            }
        }
        
        cell.appendChild(entriesContainer);
        
        return cell;
    }
    
    /**
     * Create a schedule entry element
     */
    createScheduleEntry(entry) {
        const element = document.createElement('div');
        element.className = 'schedule-entry';
        element.draggable = true;
        element.dataset.entryId = entry.name;
        
        // Set project color
        const projectColor = this.state.projectColors[entry.project] || '#6b7280';
        element.style.setProperty('--project-color', projectColor);
        
        element.innerHTML = `
            <div class="entry-duration">${entry.duration || 1}h</div>
            <div class="entry-controls">
                <button class="control-btn edit-btn" title="Edit entry" onclick="editScheduleEntry('${entry.name}')">
                    <i class="mdi mdi-pencil"></i>
                </button>
                <button class="control-btn delete-btn" title="Delete entry" onclick="deleteScheduleEntry('${entry.name}')">
                    <i class="mdi mdi-delete"></i>
                </button>
            </div>
        `;
        
        // Add drag event listeners
        element.addEventListener('dragstart', (e) => {
            element.classList.add('dragging');
            e.dataTransfer.setData('text/plain', JSON.stringify({
                entryId: entry.name,
                type: 'schedule-entry'
            }));
        });
        
        element.addEventListener('dragend', () => {
            element.classList.remove('dragging');
        });
        
        return element;
    }
    
    /**
     * Show project dropdown
     */
    showProjectDropdown(cell, rowIndex) {
        this.hideAllDropdowns();
        
        const dropdown = document.createElement('div');
        dropdown.className = 'cell-dropdown';
        dropdown.id = 'projectDropdown';
        
        this.state.projects.forEach(project => {
            const item = document.createElement('div');
            item.className = 'dropdown-item';
            item.textContent = project.project_name;
            item.addEventListener('click', () => {
                this.selectProject(rowIndex, project);
                this.hideAllDropdowns();
            });
            dropdown.appendChild(item);
        });
        
        cell.style.position = 'relative';
        cell.appendChild(dropdown);
        
        // Close dropdown when clicking outside
        setTimeout(() => {
            document.addEventListener('click', this.handleOutsideClick.bind(this), { once: true });
        }, 100);
    }
    
    /**
     * Show task dropdown
     */
    showTaskDropdown(cell, rowIndex) {
        const row = this.state.scheduleRows[rowIndex];
        if (!row.project) return;
        
        this.hideAllDropdowns();
        
        const dropdown = document.createElement('div');
        dropdown.className = 'cell-dropdown';
        dropdown.id = 'taskDropdown';
        
        const project = this.state.projects.find(p => p.name === row.project);
        if (project && project.tasks) {
            project.tasks.forEach(task => {
                const item = document.createElement('div');
                item.className = 'dropdown-item';
                item.textContent = task.task_name;
                item.addEventListener('click', () => {
                    this.selectTask(rowIndex, task);
                    this.hideAllDropdowns();
                });
                dropdown.appendChild(item);
            });
        }
        
        cell.style.position = 'relative';
        cell.appendChild(dropdown);
        
        // Close dropdown when clicking outside
        setTimeout(() => {
            document.addEventListener('click', this.handleOutsideClick.bind(this), { once: true });
        }, 100);
    }
    
    /**
     * Show person dropdown
     */
    showPersonDropdown(cell, rowIndex) {
        this.hideAllDropdowns();
        
        const dropdown = document.createElement('div');
        dropdown.className = 'cell-dropdown';
        dropdown.id = 'personDropdown';
        
        // Add "Unassigned" option
        const unassignedItem = document.createElement('div');
        unassignedItem.className = 'dropdown-item';
        unassignedItem.textContent = 'Unassigned';
        unassignedItem.addEventListener('click', () => {
            this.selectPerson(rowIndex, null);
            this.hideAllDropdowns();
        });
        dropdown.appendChild(unassignedItem);
        
        this.state.resources.forEach(resource => {
            const item = document.createElement('div');
            item.className = 'dropdown-item';
            item.textContent = resource.resource_name;
            item.addEventListener('click', () => {
                this.selectPerson(rowIndex, resource);
                this.hideAllDropdowns();
            });
            dropdown.appendChild(item);
        });
        
        cell.style.position = 'relative';
        cell.appendChild(dropdown);
        
        // Close dropdown when clicking outside
        setTimeout(() => {
            document.addEventListener('click', this.handleOutsideClick.bind(this), { once: true });
        }, 100);
    }
    
    /**
     * Hide all dropdowns
     */
    hideAllDropdowns() {
        const dropdowns = document.querySelectorAll('.cell-dropdown');
        dropdowns.forEach(dropdown => dropdown.remove());
    }
    
    /**
     * Handle outside click to close dropdowns
     */
    handleOutsideClick(event) {
        if (!event.target.closest('.cell-dropdown') && !event.target.closest('.schedule-cell')) {
            this.hideAllDropdowns();
        }
    }
    
    /**
     * Select project for a row
     */
    selectProject(rowIndex, project) {
        this.state.scheduleRows[rowIndex].project = project.name;
        this.state.scheduleRows[rowIndex].projectName = project.project_name;
        this.state.scheduleRows[rowIndex].task = null;
        this.state.scheduleRows[rowIndex].taskName = null;
        
        // Add a new blank row below when a project is selected
        this.addNewRow();
        
        this.renderScheduleRows();
    }
    
    /**
     * Select task for a row
     */
    async selectTask(rowIndex, task) {
        const row = this.state.scheduleRows[rowIndex];
        row.task = task.name;
        row.taskName = task.task_name;
        
        // Automatically create a Schedule Row when task is selected
        try {
            const response = await this.apiCall('erplite.scheduler.api.create_schedule_row_entry', {
                project: row.project,
                task: task.name,
                resource: null // No resource initially
            });
            
            if (response && response.success) {
                // Store the schedule row ID for future updates
                row.scheduleRowId = response.name;
                row.dailyEntries = {};
                console.log('Schedule Row created:', response.name);
                this.showToast('Schedule row created for task', 'success');
            } else {
                console.warn('Failed to create schedule row:', response.message);
                // Continue anyway - user can still work with the interface
            }
        } catch (error) {
            console.warn('Error creating schedule row:', error);
            // Continue anyway - fallback to old system
        }
        
        // When a task is selected, add a new row with the same project but no task
        this.state.scheduleRows.splice(rowIndex + 1, 0, {
            type: 'task-row',
            project: row.project,
            projectName: row.projectName,
            task: null,
            taskName: null,
            resource: null,
            resourceName: null,
            entries: [],
            dailyEntries: {}
        });
        
        this.renderScheduleRows();
    }
    
    /**
     * Select person for a row
     */
    async selectPerson(rowIndex, resource) {
        const row = this.state.scheduleRows[rowIndex];
        row.resource = resource ? resource.name : null;
        row.resourceName = resource ? resource.resource_name : 'Unassigned';
        
        // If we have a project and task, create/update Schedule Row with resource
        if (row.project && row.task) {
            try {
                if (row.scheduleRowId) {
                    // Update existing schedule row with resource
                    const updateResponse = await this.apiCall('erplite.scheduler.api.update_schedule_row_resource', {
                        schedule_row: row.scheduleRowId,
                        resource: resource ? resource.name : null
                    });
                    
                    if (updateResponse && updateResponse.success) {
                        console.log('Schedule Row updated with resource:', row.scheduleRowId);
                        this.showToast('Schedule row updated with resource', 'success');
                    } else {
                        console.warn('Failed to update schedule row with resource:', updateResponse.message);
                    }
                } else {
                    // Create new schedule row with resource
                    const response = await this.apiCall('erplite.scheduler.api.create_schedule_row_entry', {
                        project: row.project,
                        task: row.task,
                        resource: resource ? resource.name : null
                    });
                    
                    if (response && response.success) {
                        row.scheduleRowId = response.name;
                        row.dailyEntries = {};
                        console.log('Schedule Row created with resource:', response.name);
                        this.showToast('Schedule row created with resource', 'success');
                    }
                }
            } catch (error) {
                console.warn('Error updating schedule row with resource:', error);
                // Continue anyway - fallback to old system
            }
        }
        
        this.renderScheduleRows();
    }
    
    /**
     * Create entry for a specific cell
     */
    createEntryForCell(rowIndex, date) {
        const row = this.state.scheduleRows[rowIndex];
        
        if (!row.project || !row.task) {
            this.showToast('Please select project and task first', 'warning');
            return;
        }
        
        // Pre-fill modal with row data
        this.openEntryModal(null, {
            project: row.project,
            task: row.task,
            resource: row.resource,
            date: date
        });
    }
    
    /**
     * Add default projects to project groups
     */
    addDefaultProjects(projectGroups) {
        // Get all projects that have status "Active" or "Open"
        const openProjects = this.state.projects.filter(project => 
            project.status === 'Active' || project.status === 'Open'
        );
        
        // For each open project, ensure it exists in project groups
        openProjects.forEach(project => {
            const projectKey = project.name;
            if (!projectGroups[projectKey]) {
                projectGroups[projectKey] = {
                    project: project.name,
                    projectName: project.project_name,
                    tasks: {}
                };
            }
        });
    }
    
    /**
     * Add new project header
     */
    addNewProjectHeader() {
        this.state.scheduleRows.push({
            type: 'project-header',
            project: null,
            projectName: null,
            task: null,
            taskName: null,
            resource: null,
            resourceName: null,
            entries: []
        });
        
        this.renderScheduleRows();
    }
    
    /**
     * Add new empty row
     */
    addNewRow() {
        this.state.scheduleRows.push({
            project: null,
            projectName: null,
            task: null,
            taskName: null,
            resource: null,
            resourceName: null,
            entries: []
        });
        
        this.renderScheduleRows();
    }
    
    /**
     * Ensure there's always an empty row at the bottom
     */
    ensureEmptyRow() {
        // Check if the last row is empty
        const lastRow = this.state.scheduleRows[this.state.scheduleRows.length - 1];
        
        // If there's no last row or the last row has a project selected, add an empty row
        if (!lastRow || lastRow.project) {
            const emptyRow = {
                project: null,
                projectName: null,
                task: null,
                taskName: null,
                resource: null,
                resourceName: null,
                entries: []
            };
            
            this.state.scheduleRows.push(emptyRow);
            
            // Create and append the empty row element
            const container = document.getElementById('gridBody');
            if (container) {
                const rowElement = this.createScheduleRow(emptyRow, this.state.scheduleRows.length - 1);
                container.appendChild(rowElement);
            }
        }
    }
    
    // Event handlers for HTML template
    navigateDate(days) {
        const newDate = this.addDays(this.state.currentStartDate, days);
        this.state.currentStartDate = newDate;
        this.loadSchedulerData();
    }
    
    refreshData() {
        this.loadSchedulerData();
    }
    
    exportSchedule() {
        this.showToast('Export functionality coming soon!', 'info');
    }
    
    // Modal functions
    openEntryModal(entry = null, prefill = null) {
        const modal = document.getElementById('entryModal');
        const title = document.getElementById('modalTitle');
        const saveBtn = document.getElementById('saveEntryBtn');
        
        if (entry) {
            title.textContent = 'Edit Schedule Entry';
            saveBtn.textContent = 'Update Entry';
            this.populateModalWithEntry(entry);
        } else {
            title.textContent = 'Create Schedule Entry';
            saveBtn.textContent = 'Create Entry';
            this.clearModal();
            
            if (prefill) {
                this.prefillModal(prefill);
            }
        }
        
        this.populateModalSelectors();
        modal.style.display = 'block';
    }
    
    closeEntryModal() {
        const modal = document.getElementById('entryModal');
        modal.style.display = 'none';
    }
    
    populateModalSelectors() {
        // Populate resource selector
        const resourceSelect = document.getElementById('entryResource');
        resourceSelect.innerHTML = '<option value="">Unassigned</option>';
        this.state.resources.forEach(resource => {
            const option = document.createElement('option');
            option.value = resource.name;
            option.textContent = resource.resource_name;
            resourceSelect.appendChild(option);
        });
        
        // Set default date to today
        document.getElementById('entryDate').value = this.getTodayString();
    }
    
    populateModalWithEntry(entry) {
        document.getElementById('entryProject').value = entry.project || '';
        document.getElementById('entryTask').value = entry.task || '';
        document.getElementById('entryResource').value = entry.resource || '';
        document.getElementById('entryDate').value = entry.schedule_date || this.getTodayString();
        document.getElementById('entryDuration').value = entry.duration || 1;
        document.getElementById('entryPriority').value = entry.priority || 'Medium';
        document.getElementById('entryDescription').value = entry.description || '';
        
        // Update task options based on selected project
        this.updateEntryTaskOptions();
        
        // Store entry ID for updates
        this.currentEditingEntry = entry.name;
    }
    
    prefillModal(prefill) {
        if (prefill.project) {
            document.getElementById('entryProject').value = prefill.project;
            const project = this.state.projects.find(p => p.name === prefill.project);
            document.getElementById('entryProjectDisplay').textContent = project ? project.project_name : prefill.project;
        }
        
        if (prefill.task) {
            document.getElementById('entryTask').value = prefill.task;
            const project = this.state.projects.find(p => p.name === prefill.project);
            if (project && project.tasks) {
                const task = project.tasks.find(t => t.name === prefill.task);
                document.getElementById('entryTaskDisplay').textContent = task ? task.task_name : prefill.task;
            }
        }
        
        if (prefill.resource) document.getElementById('entryResource').value = prefill.resource;
        if (prefill.date) document.getElementById('entryDate').value = prefill.date;
    }
    
    updateEntryTaskOptions() {
        const projectSelect = document.getElementById('entryProject');
        const taskSelect = document.getElementById('entryTask');
        
        taskSelect.innerHTML = '<option value="">Select Task</option>';
        
        if (projectSelect.value) {
            const project = this.state.projects.find(p => p.name === projectSelect.value);
            if (project && project.tasks) {
                project.tasks.forEach(task => {
                    const option = document.createElement('option');
                    option.value = task.name;
                    option.textContent = task.task_name;
                    taskSelect.appendChild(option);
                });
            }
        }
    }
    
    clearModal() {
        document.getElementById('entryProject').value = '';
        document.getElementById('entryTask').value = '';
        document.getElementById('entryResource').value = '';
        document.getElementById('entryDate').value = this.getTodayString();
        document.getElementById('entryDuration').value = '1';
        document.getElementById('entryPriority').value = 'Medium';
        document.getElementById('entryDescription').value = '';
    }
    
    async saveEntry() {
        const formData = {
            project: document.getElementById('entryProject').value,
            task: document.getElementById('entryTask').value,
            resource: document.getElementById('entryResource').value || null,
            schedule_date: document.getElementById('entryDate').value,
            duration: parseFloat(document.getElementById('entryDuration').value),
            priority: document.getElementById('entryPriority').value,
            description: document.getElementById('entryDescription').value
        };
        
        if (!formData.project || !formData.task || !formData.schedule_date) {
            this.showToast('Please fill in all required fields', 'error');
            return;
        }
        
        try {
            this.setLoading(true);
            
            const response = await this.apiCall('erplite.scheduler.api.create_schedule_entry', {
                data: JSON.stringify(formData)
            });
            
            if (response && response.success) {
                this.showToast('Schedule entry created successfully!', 'success');
                this.closeEntryModal();
                this.loadSchedulerData();
            } else {
                this.showToast(response.message || 'Failed to create entry', 'error');
            }
        } catch (error) {
            console.error('Error saving entry:', error);
            this.showToast('Error saving entry: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }
    
    // Drag and drop handler
    handleDrop(event) {
        try {
            const data = JSON.parse(event.dataTransfer.getData('text/plain'));
            if (data.type === 'schedule-entry') {
                const cell = event.target.closest('.day-cell');
                if (cell) {
                    const newDate = cell.dataset.date;
                    const newRowIndex = parseInt(cell.dataset.rowIndex);
                    this.moveEntry(data.entryId, newRowIndex, newDate);
                }
            }
        } catch (error) {
            console.error('Error handling drop:', error);
        }
    }
    
    async moveEntry(entryId, newRowIndex, newDate) {
        const newRow = this.state.scheduleRows[newRowIndex];
        
        if (!newRow.project || !newRow.task) {
            this.showToast('Cannot move entry to incomplete row', 'error');
            return;
        }
        
        try {
            this.setLoading(true);
            
            const response = await this.apiCall('erplite.scheduler.api.update_schedule_entry', {
                name: entryId,
                data: JSON.stringify({
                    project: newRow.project,
                    task: newRow.task,
                    resource: newRow.resource,
                    schedule_date: newDate
                })
            });
            
            if (response && response.success) {
                this.showToast('Entry moved successfully!', 'success');
                this.loadSchedulerData();
            } else {
                this.showToast(response.message || 'Failed to move entry', 'error');
            }
        } catch (error) {
            console.error('Error moving entry:', error);
            this.showToast('Error moving entry: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }
    
    async deleteEntry(entryId) {
        try {
            this.setLoading(true);
            
            const response = await this.apiCall('erplite.scheduler.api.delete_schedule_entry', {
                name: entryId
            });
            
            if (response && response.success) {
                this.showToast('Schedule entry deleted successfully!', 'success');
                this.loadSchedulerData();
            } else {
                this.showToast(response.message || 'Failed to delete entry', 'error');
            }
        } catch (error) {
            console.error('Error deleting entry:', error);
            this.showToast('Error deleting entry: ' + error.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }
    
    /**
     * Delete a schedule row
     */
    deleteRow(rowIndex) {
        if (rowIndex >= 0 && rowIndex < this.state.scheduleRows.length) {
            this.state.scheduleRows.splice(rowIndex, 1);
            this.renderScheduleRows();
            this.showToast('Row deleted successfully!', 'success');
        }
    }
    
    /**
     * Copy task down - creates a duplicate task row below the current one
     */
    copyTaskDown(rowIndex) {
        if (rowIndex >= 0 && rowIndex < this.state.scheduleRows.length) {
            const sourceRow = this.state.scheduleRows[rowIndex];
            
            // Create a copy of the task row
            const newRow = {
                type: 'task-row',
                project: sourceRow.project,
                projectName: sourceRow.projectName,
                task: sourceRow.task,
                taskName: sourceRow.taskName,
                resource: sourceRow.resource,
                resourceName: sourceRow.resourceName,
                entries: [] // New row starts with no entries
            };
            
            // Insert the new row right after the current one
            this.state.scheduleRows.splice(rowIndex + 1, 0, newRow);
            
            // Add another blank row after the copied row
            this.state.scheduleRows.splice(rowIndex + 2, 0, {
                type: 'task-row',
                project: sourceRow.project,
                projectName: sourceRow.projectName,
                task: null,
                taskName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
            
            this.renderScheduleRows();
            this.showToast('Task copied down successfully!', 'success');
        }
    }
    
    /**
     * Create a time entry element for Schedule Row daily entries
     */
    createTimeEntry(entry, date, row) {
        const element = document.createElement('div');
        element.className = 'time-entry';
        element.dataset.date = date;
        element.dataset.rowIndex = row.scheduleRowId;
        
        // Set project color
        const projectColor = this.state.projectColors[row.project] || '#3b82f6';
        element.style.setProperty('--project-color', projectColor);
        
        const hours = typeof entry === 'object' ? entry.hours : entry;
        const description = typeof entry === 'object' ? entry.description : '';
        
        element.innerHTML = `
            <div class="time-entry-hours">${hours}h</div>
            <div class="time-entry-time">9:00 - 17:00</div>
        `;
        
        // Add click handler for editing
        element.addEventListener('click', () => {
            this.editTimeEntry(row.scheduleRowId, date, entry);
        });
        
        return element;
    }
    
    /**
     * Add a single time entry (8 hours, 9-5)
     */
    async addSingleTimeEntry(rowIndex, date) {
        const row = this.state.scheduleRows[rowIndex];
        
        if (!row.scheduleRowId) {
            this.showToast('Schedule row not created yet', 'error');
            return;
        }
        
        try {
            // Create time entry in Schedule Row
            const timeEntry = {
                hours: 8,
                start_time: "09:00",
                end_time: "17:00",
                description: "",
                status: "planned"
            };
            
            // Update the row's daily entries
            if (!row.dailyEntries) {
                row.dailyEntries = {};
            }
            row.dailyEntries[date] = timeEntry;
            
            // Update the Schedule Row in database
            const response = await this.apiCall('erplite.scheduler.api.update_schedule_row_entries', {
                schedule_row: row.scheduleRowId,
                entries_json: JSON.stringify(row.dailyEntries)
            });
            
            if (response && response.success) {
                this.showToast('Time entry added successfully!', 'success');
                this.renderScheduleRows();
            } else {
                this.showToast('Failed to add time entry', 'error');
            }
            
        } catch (error) {
            console.error('Error adding time entry:', error);
            this.showToast('Error adding time entry: ' + error.message, 'error');
        }
    }
    
    /**
     * Start drag selection for multiple days
     */
    startDragSelection(event, rowIndex, startDate) {
        event.preventDefault();
        event.stopPropagation();
        
        this.dragSelection = {
            active: true,
            rowIndex: rowIndex,
            startDate: startDate,
            currentDate: startDate,
            selectedDates: [startDate]
        };
        
        // Bind the event handlers to maintain 'this' context
        this.boundHandleDragSelection = this.handleDragSelection.bind(this);
        this.boundEndDragSelection = this.endDragSelection.bind(this);
        
        // Add mouse move and mouse up listeners to document
        document.addEventListener('mousemove', this.boundHandleDragSelection);
        document.addEventListener('mouseup', this.boundEndDragSelection);
        
        // Prevent text selection during drag
        document.body.style.userSelect = 'none';
        
        // Mark the starting cell
        const startCell = event.target.closest('.day-cell');
        if (startCell) {
            startCell.classList.add('drag-selecting');
        }
        
        console.log('Started drag selection from:', startDate);
    }
    
    /**
     * Handle drag selection movement
     */
    handleDragSelection(event) {
        if (!this.dragSelection || !this.dragSelection.active) return;
        
        // Find the day cell under the mouse
        const elementUnderMouse = document.elementFromPoint(event.clientX, event.clientY);
        const cell = elementUnderMouse ? elementUnderMouse.closest('.day-cell') : null;
        
        if (!cell || !cell.dataset.date || !cell.dataset.rowIndex) return;
        
        const rowIndex = parseInt(cell.dataset.rowIndex);
        const date = cell.dataset.date;
        
        // Only allow selection within the same row
        if (rowIndex !== this.dragSelection.rowIndex) return;
        
        // Update current date
        this.dragSelection.currentDate = date;
        
        // Clear previous selection styling
        document.querySelectorAll('.day-cell.drag-selected, .day-cell.drag-selecting').forEach(cell => {
            cell.classList.remove('drag-selected', 'drag-selecting');
        });
        
        // Calculate date range between start and current
        const startDate = new Date(this.dragSelection.startDate);
        const currentDate = new Date(date);
        const minDate = startDate < currentDate ? startDate : currentDate;
        const maxDate = startDate > currentDate ? startDate : currentDate;
        
        // Update selected dates array
        this.dragSelection.selectedDates = [];
        const iterDate = new Date(minDate);
        
        while (iterDate <= maxDate) {
            const dateStr = iterDate.toISOString().split('T')[0];
            this.dragSelection.selectedDates.push(dateStr);
            iterDate.setDate(iterDate.getDate() + 1);
        }
        
        // Mark all cells in range as selected
        this.dragSelection.selectedDates.forEach(dateStr => {
            const dayCell = document.querySelector(`[data-date="${dateStr}"][data-row-index="${rowIndex}"]`);
            if (dayCell && dayCell.classList.contains('interactive')) {
                dayCell.classList.add('drag-selected');
            }
        });
        
        console.log('Drag selection updated:', this.dragSelection.selectedDates);
    }
    
    /**
     * End drag selection and add time entries
     */
    async endDragSelection(event) {
        if (!this.dragSelection || !this.dragSelection.active) return;
        
        console.log('Ending drag selection with dates:', this.dragSelection.selectedDates);
        
        // Clean up event listeners
        document.removeEventListener('mousemove', this.boundHandleDragSelection);
        document.removeEventListener('mouseup', this.boundEndDragSelection);
        
        // Restore text selection
        document.body.style.userSelect = '';
        
        // Clear selection styling
        document.querySelectorAll('.day-cell.drag-selected, .day-cell.drag-selecting').forEach(cell => {
            cell.classList.remove('drag-selected', 'drag-selecting');
        });
        
        const selectedDates = this.dragSelection.selectedDates;
        const rowIndex = this.dragSelection.rowIndex;
        
        // Reset drag selection
        this.dragSelection = null;
        
        if (selectedDates.length > 1) {
            // Add time entries for all selected dates
            console.log('Adding time entries for', selectedDates.length, 'days');
            await this.addMultipleTimeEntries(rowIndex, selectedDates);
        } else if (selectedDates.length === 1) {
            // Single day selection - treat as single click
            console.log('Single day selected, adding single entry');
            await this.addSingleTimeEntry(rowIndex, selectedDates[0]);
        }
    }
    
    /**
     * Add time entries for multiple dates
     */
    async addMultipleTimeEntries(rowIndex, dates) {
        const row = this.state.scheduleRows[rowIndex];
        
        if (!row.scheduleRowId) {
            this.showToast('Schedule row not created yet', 'error');
            return;
        }
        
        try {
            // Create time entries for all dates
            if (!row.dailyEntries) {
                row.dailyEntries = {};
            }
            
            dates.forEach(date => {
                row.dailyEntries[date] = {
                    hours: 8,
                    start_time: "09:00",
                    end_time: "17:00",
                    description: "",
                    status: "planned"
                };
            });
            
            // Update the Schedule Row in database
            const response = await this.apiCall('erplite.scheduler.api.update_schedule_row_entries', {
                schedule_row: row.scheduleRowId,
                entries_json: JSON.stringify(row.dailyEntries)
            });
            
            if (response && response.success) {
                this.showToast(`Time entries added for ${dates.length} days!`, 'success');
                this.renderScheduleRows();
            } else {
                this.showToast('Failed to add time entries', 'error');
            }
            
        } catch (error) {
            console.error('Error adding time entries:', error);
            this.showToast('Error adding time entries: ' + error.message, 'error');
        }
    }
    
    /**
     * Edit a time entry
     */
    editTimeEntry(scheduleRowId, date, entry) {
        // For now, just show a simple prompt - can be enhanced with a modal later
        const hours = typeof entry === 'object' ? entry.hours : entry;
        const newHours = prompt(`Edit hours for ${date}:`, hours);
        
        if (newHours !== null && !isNaN(newHours) && newHours > 0) {
            this.updateTimeEntry(scheduleRowId, date, parseFloat(newHours));
        }
    }
    
    /**
     * Update a time entry
     */
    async updateTimeEntry(scheduleRowId, date, hours) {
        try {
            // Find the row
            const row = this.state.scheduleRows.find(r => r.scheduleRowId === scheduleRowId);
            if (!row) return;
            
            // Update the entry
            if (!row.dailyEntries) {
                row.dailyEntries = {};
            }
            
            row.dailyEntries[date] = {
                hours: hours,
                start_time: "09:00",
                end_time: "17:00",
                description: "",
                status: "planned"
            };
            
            // Update in database
            const response = await this.apiCall('erplite.scheduler.api.update_schedule_row_entries', {
                schedule_row: scheduleRowId,
                entries_json: JSON.stringify(row.dailyEntries)
            });
            
            if (response && response.success) {
                this.showToast('Time entry updated successfully!', 'success');
                this.renderScheduleRows();
            } else {
                this.showToast('Failed to update time entry', 'error');
            }
            
        } catch (error) {
            console.error('Error updating time entry:', error);
            this.showToast('Error updating time entry: ' + error.message, 'error');
        }
    }
    
    // Utility functions
    getTodayString() {
        return new Date().toISOString().split('T')[0];
    }
    
    addDays(dateString, days) {
        const date = new Date(dateString);
        date.setDate(date.getDate() + days);
        return date.toISOString().split('T')[0];
    }
    
    setLoading(loading) {
        this.state.isLoading = loading;
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.style.display = loading ? 'flex' : 'none';
        }
    }
    
    showToast(message, type = 'info') {
        if (window.showToast) {
            window.showToast(message, type);
        }
    }
    
    async apiCall(method, args = {}) {
        if (typeof frappe !== 'undefined' && frappe.call) {
            return new Promise((resolve, reject) => {
                frappe.call({
                    method: method,
                    args: args,
                    callback: (response) => {
                        resolve(response.message);
                    },
                    error: (error) => {
                        reject(error);
                    }
                });
            });
        } else {
            throw new Error('Frappe framework not available');
        }
    }
    
    // Cleanup
    cleanup() {
        this.hideAllDropdowns();
        console.log('Scheduler cleanup completed');
    }
    
    // Handle window resize
    handleResize() {
        console.log('Scheduler handling resize');
    }

    /**
     * Initialize drag and drop for template cards
     */
    initializeTemplateDragDrop() {
        // Add drag event listeners to template cards
        document.querySelectorAll('.template-card').forEach(card => {
            card.addEventListener('dragstart', (e) => {
                const template = card.dataset.template;
                e.dataTransfer.setData('text/plain', JSON.stringify({
                    type: 'template',
                    template: template
                }));
                card.classList.add('dragging');
            });
            
            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
            });
        });
    }

    /**
     * Handle template drop on day cell (Frontend only)
     */
    handleTemplateDrop(template, rowIndex, date) {
        const row = this.state.scheduleRows[rowIndex];
        
        if (!row.project || !row.task) {
            this.showToast('Please select project and task first', 'warning');
            return;
        }
        
        // Get template configuration
        const templateConfig = this.getTemplateConfig(template);
        
        // Initialize dailyEntries if not exists
        if (!row.dailyEntries) {
            row.dailyEntries = {};
        }
        
        // Add the new entry to frontend state
        row.dailyEntries[date] = {
            hours: templateConfig.hours,
            start_time: templateConfig.start_time,
            end_time: templateConfig.end_time,
            description: templateConfig.description,
            status: templateConfig.status,
            id: this.generateEntryId() // Generate unique ID for frontend tracking
        };
        
        this.showToast(`${templateConfig.name} template added!`, 'success');
        
        // Re-render the schedule to show the new entry
        this.renderScheduleRows();
        this.renderTimeBlockCards();
    }

    /**
     * Get template configuration
     */
    getTemplateConfig(template) {
        const configs = {
            '8h': {
                name: '8 Hour Shift',
                hours: 8,
                start_time: '09:00',
                end_time: '17:00',
                description: 'Standard 8-hour work day',
                status: 'planned'
            },
            '12h': {
                name: '12 Hour Shift',
                hours: 12,
                start_time: '07:00',
                end_time: '19:00',
                description: 'Extended 12-hour shift',
                status: 'planned'
            },
            'leave': {
                name: 'Leave',
                hours: 8,
                start_time: '00:00',
                end_time: '23:59',
                description: 'Time off / Leave',
                status: 'leave'
            }
        };
        
        return configs[template] || configs['8h'];
    }

    /**
     * Handle drop on day cell (templates or entries)
     */
    async handleCellDrop(event, rowIndex, date) {
        event.preventDefault();
        event.stopPropagation();
        
        // Remove drop zone styling
        event.target.classList.remove('drop-zone');
        
        try {
            const data = JSON.parse(event.dataTransfer.getData('text/plain'));
            
            if (data.type === 'template') {
                // Handle template drop
                await this.handleTemplateDrop(data.template, rowIndex, date);
            } else if (data.type === 'schedule-entry') {
                // Handle existing entry move
                this.moveEntry(data.entryId, rowIndex, date);
            }
        } catch (error) {
            console.error('Error handling cell drop:', error);
            this.showToast('Error processing drop: ' + error.message, 'error');
        }
    }

    /**
     * Generate unique entry ID for frontend tracking
     */
    generateEntryId() {
        return 'entry_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Start resizing a time block card
     */
    startResize(event, card, direction, rowIndex, blockData) {
        event.preventDefault();
        event.stopPropagation();
        
        // Store resize state
        this.resizeState = {
            active: true,
            card: card,
            direction: direction,
            rowIndex: rowIndex,
            blockData: blockData,
            originalStartDate: blockData.start_date,
            originalEndDate: blockData.end_date,
            startX: event.clientX
        };
        
        // Add resizing class
        card.classList.add('resizing');
        
        // Bind event handlers
        this.boundHandleResize = this.handleResize.bind(this);
        this.boundEndResize = this.endResize.bind(this);
        
        document.addEventListener('mousemove', this.boundHandleResize);
        document.addEventListener('mouseup', this.boundEndResize);
        
        // Prevent text selection
        document.body.style.userSelect = 'none';
        
        console.log(`Started resizing ${direction} for block:`, blockData);
    }
    
    /**
     * Handle resize movement
     */
    handleResize(event) {
        if (!this.resizeState || !this.resizeState.active) return;
        
        const { card, direction, rowIndex } = this.resizeState;
        const row = this.state.scheduleRows[rowIndex];
        
        // Find the row element and days container
        const rowElement = document.querySelector(`[data-row-index="${rowIndex}"]`);
        if (!rowElement) return;
        
        const daysContainer = rowElement.querySelector('.schedule-days');
        if (!daysContainer) return;
        
        // Find the day cell under the mouse
        const elementUnderMouse = document.elementFromPoint(event.clientX, event.clientY);
        const targetCell = elementUnderMouse ? elementUnderMouse.closest('.day-cell') : null;
        
        if (!targetCell || !targetCell.dataset.date) return;
        
        const targetDate = targetCell.dataset.date;
        
        // Clear previous resize targets
        document.querySelectorAll('.day-cell.resize-target').forEach(cell => {
            cell.classList.remove('resize-target');
        });
        
        // Calculate new date range based on resize direction
        let newStartDate, newEndDate;
        
        if (direction === 'left') {
            // Resizing from the left - change start date
            newStartDate = targetDate;
            newEndDate = this.resizeState.originalEndDate;
            
            // Ensure start is not after end
            if (new Date(newStartDate) > new Date(newEndDate)) {
                newStartDate = newEndDate;
            }
        } else {
            // Resizing from the right - change end date
            newStartDate = this.resizeState.originalStartDate;
            newEndDate = targetDate;
            
            // Ensure end is not before start
            if (new Date(newEndDate) < new Date(newStartDate)) {
                newEndDate = newStartDate;
            }
        }
        
        // Highlight the new range
        this.highlightDateRange(rowIndex, newStartDate, newEndDate);
        
        // Update the card visually
        this.updateCardVisualDuringResize(card, daysContainer, newStartDate, newEndDate);
        
        // Store the new dates for when resize ends
        this.resizeState.newStartDate = newStartDate;
        this.resizeState.newEndDate = newEndDate;
    }
    
    /**
     * End resize operation
     */
    endResize(event) {
        if (!this.resizeState || !this.resizeState.active) return;
        
        const { card, rowIndex, blockData, newStartDate, newEndDate } = this.resizeState;
        
        // Clean up event listeners
        document.removeEventListener('mousemove', this.boundHandleResize);
        document.removeEventListener('mouseup', this.boundEndResize);
        
        // Restore text selection
        document.body.style.userSelect = '';
        
        // Remove resizing class
        card.classList.remove('resizing');
        
        // Clear resize targets
        document.querySelectorAll('.day-cell.resize-target').forEach(cell => {
            cell.classList.remove('resize-target');
        });
        
        // Apply the resize if dates changed
        if (newStartDate && newEndDate && 
            (newStartDate !== blockData.start_date || newEndDate !== blockData.end_date)) {
            
            this.applyResize(rowIndex, blockData, newStartDate, newEndDate);
        }
        
        // Reset resize state
        this.resizeState = null;
        
        console.log('Resize ended');
    }
    
    /**
     * Highlight date range during resize
     */
    highlightDateRange(rowIndex, startDate, endDate) {
        // Clear previous highlights
        document.querySelectorAll('.day-cell.resize-target').forEach(cell => {
            cell.classList.remove('resize-target');
        });
        
        // Highlight the new range
        const start = new Date(startDate);
        const end = new Date(endDate);
        const currentDate = new Date(start);
        
        while (currentDate <= end) {
            const dateStr = currentDate.toISOString().split('T')[0];
            const cell = document.querySelector(`[data-date="${dateStr}"][data-row-index="${rowIndex}"]`);
            if (cell) {
                cell.classList.add('resize-target');
            }
            currentDate.setDate(currentDate.getDate() + 1);
        }
    }
    
    /**
     * Update card visual appearance during resize
     */
    updateCardVisualDuringResize(card, daysContainer, startDate, endDate) {
        const startCell = daysContainer.querySelector(`[data-date="${startDate}"]`);
        const endCell = daysContainer.querySelector(`[data-date="${endDate}"]`);
        
        if (!startCell || !endCell) return;
        
        // Calculate new position and width
        const startRect = startCell.getBoundingClientRect();
        const endRect = endCell.getBoundingClientRect();
        const containerRect = daysContainer.getBoundingClientRect();
        
        const left = startRect.left - containerRect.left;
        const width = endRect.right - startRect.left;
        
        // Update card position and width
        card.style.left = `${left}px`;
        card.style.width = `${width}px`;
        
        // Update content to show new day count
        const content = card.querySelector('.card-content');
        if (content) {
            const daysCount = this.calculateDaysBetween(startDate, endDate) + 1;
            const hours = this.resizeState.blockData.hours || 8;
            const startTime = this.resizeState.blockData.start_time || '09:00';
            const endTime = this.resizeState.blockData.end_time || '17:00';
            
            if (daysCount > 1) {
                content.innerHTML = `
                    <div class="card-hours">${hours}h × ${daysCount}</div>
                    <div class="card-time">${startTime}-${endTime}</div>
                `;
            } else {
                content.innerHTML = `
                    <div class="card-hours">${hours}h</div>
                    <div class="card-time">${startTime}-${endTime}</div>
                `;
            }
        }
    }
    
    /**
     * Apply the resize to the data model
     */
    applyResize(rowIndex, originalBlockData, newStartDate, newEndDate) {
        const row = this.state.scheduleRows[rowIndex];
        
        if (!row.dailyEntries) {
            row.dailyEntries = {};
        }
        
        // Remove entries from the original date range
        const originalStart = new Date(originalBlockData.start_date);
        const originalEnd = new Date(originalBlockData.end_date);
        const currentDate = new Date(originalStart);
        
        while (currentDate <= originalEnd) {
            const dateStr = currentDate.toISOString().split('T')[0];
            delete row.dailyEntries[dateStr];
            currentDate.setDate(currentDate.getDate() + 1);
        }
        
        // Add entries for the new date range
        const newStart = new Date(newStartDate);
        const newEnd = new Date(newEndDate);
        const newCurrentDate = new Date(newStart);
        
        while (newCurrentDate <= newEnd) {
            const dateStr = newCurrentDate.toISOString().split('T')[0];
            row.dailyEntries[dateStr] = {
                hours: originalBlockData.hours || 8,
                start_time: originalBlockData.start_time || '09:00',
                end_time: originalBlockData.end_time || '17:00',
                description: originalBlockData.description || '',
                status: originalBlockData.status || 'planned',
                id: this.generateEntryId()
            };
            newCurrentDate.setDate(newCurrentDate.getDate() + 1);
        }
        
        // Re-render to show the changes
        this.renderScheduleRows();
        this.renderTimeBlockCards();
        
        const daysCount = this.calculateDaysBetween(newStartDate, newEndDate) + 1;
        this.showToast(`Time block resized to ${daysCount} day${daysCount > 1 ? 's' : ''}!`, 'success');
    }

    /**
     * Group consecutive entries with identical properties into blocks
     */
    groupConsecutiveEntries(entries) {
        const sortedDates = Object.keys(entries).sort();
        const blocks = [];
        
        if (sortedDates.length === 0) return blocks;
        
        let currentBlock = null;
        
        for (const date of sortedDates) {
            const entry = entries[date];
            
            if (!currentBlock) {
                // Start new block
                currentBlock = {
                    start_date: date,
                    end_date: date,
                    hours: entry.hours || 8,
                    start_time: entry.start_time || '09:00',
                    end_time: entry.end_time || '17:00',
                    description: entry.description || '',
                    status: entry.status || 'planned'
                };
            } else {
                // Check if this entry can extend the current block
                const canExtend = this.canEntriesBeGrouped(currentBlock, entry) &&
                                this.isConsecutiveDate(currentBlock.end_date, date);
                
                if (canExtend) {
                    // Extend current block
                    currentBlock.end_date = date;
                } else {
                    // Finalize current block and start new one
                    blocks.push(currentBlock);
                    currentBlock = {
                        start_date: date,
                        end_date: date,
                        hours: entry.hours || 8,
                        start_time: entry.start_time || '09:00',
                        end_time: entry.end_time || '17:00',
                        description: entry.description || '',
                        status: entry.status || 'planned'
                    };
                }
            }
        }
        
        // Add the last block
        if (currentBlock) {
            blocks.push(currentBlock);
        }
        
        return blocks;
    }
    
    /**
     * Check if two entries can be grouped together
     */
    canEntriesBeGrouped(block, entry) {
        return (
            (entry.hours || 8) === block.hours &&
            (entry.start_time || '09:00') === block.start_time &&
            (entry.end_time || '17:00') === block.end_time &&
            (entry.status || 'planned') === block.status
        );
    }
    
    /**
     * Check if two dates are consecutive
     */
    isConsecutiveDate(date1, date2) {
        const d1 = new Date(date1);
        const d2 = new Date(date2);
        const diffTime = d2.getTime() - d1.getTime();
        const diffDays = diffTime / (1000 * 60 * 60 * 24);
        return diffDays === 1;
    }

    /**
     * Convert hex color to rgba with alpha
     */
    hexToRgba(hex, alpha = 1) {
        let c = hex.replace('#', '');
        if (c.length === 3) {
            c = c.split('').map(x => x + x).join('');
        }
        const num = parseInt(c, 16);
        const r = (num >> 16) & 255;
        const g = (num >> 8) & 255;
        const b = num & 255;
        return `rgba(${r},${g},${b},${alpha})`;
    }
}

// Export to global scope for HTML compatibility
window.SchedulerApp = SchedulerApp;

// Global functions for entry management (called from HTML)
window.editScheduleEntry = function(entryId) {
    if (window.scheduler) {
        const entry = window.scheduler.state.scheduleEntries.find(e => e.name === entryId);
        if (entry) {
            window.scheduler.openEntryModal(entry);
        }
    }
};

window.deleteScheduleEntry = function(entryId) {
    if (window.scheduler && confirm('Are you sure you want to delete this schedule entry?')) {
        window.scheduler.deleteEntry(entryId);
    }
};

window.deleteScheduleRow = function(rowIndex) {
    if (window.scheduler && confirm('Are you sure you want to delete this row?')) {
        window.scheduler.deleteRow(rowIndex);
    }
};

window.copyTaskDown = function(rowIndex) {
    if (window.scheduler) {
        window.scheduler.copyTaskDown(rowIndex);
    }
};
