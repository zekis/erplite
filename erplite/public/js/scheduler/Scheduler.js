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
            roles: [], // Add roles to state
            scheduleEntries: [],
            projectColors: {},
            scheduleRows: [], // Array of {project, activity, person, entries}
            dateRange: 30,
            isLoading: false
        };
        
        // Initialize managers
        this.dataManager = new DataManager(this);
        this.rowManager = new ScheduleRowManager(this);
        this.dropdownManager = new DropdownManager(this);
        this.rowRenderer = new RowRenderer(this);
        this.timeBlockManager = new TimeBlockManager(this);
        this.toolbarManager = new ToolbarManager(this);
        
        this.init();
    }
    
    /**
     * Initialize the application
     */
    init() {
        console.log('Initializing Scheduler...');
        
        // Load initial data from window object (set by template)
        this.loadInitialData();
        
        // Initialize toolbar manager
        this.toolbarManager.init();
        
        // Load and render initial data
        this.loadSchedulerData();
        
        console.log('Scheduler initialized successfully');
    }
    
    /**
     * Load initial data from window object (set by template) - delegated to DataManager
     */
    loadInitialData() {
        this.dataManager.loadInitialData();
    }
    
    /**
     * Load scheduler data from API - delegated to DataManager
     */
    async loadSchedulerData() {
        const result = await this.dataManager.loadSchedulerData();
        if (result.success) {
            this.renderAll();
        }
        return result;
    }
    
    // Data processing methods moved to DataManager class
    
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
        const fixedLeftContainer = document.getElementById('fixedLeftBody');
        const scrollableRightContainer = document.getElementById('gridBody');
        
        if (!fixedLeftContainer || !scrollableRightContainer) return;
        
        fixedLeftContainer.innerHTML = '';
        scrollableRightContainer.innerHTML = '';
        
        this.state.scheduleRows.forEach((row, index) => {
            const { fixedColumns, dayColumns } = this.rowRenderer.createScheduleRow(row, index);
            fixedLeftContainer.appendChild(fixedColumns);
            scrollableRightContainer.appendChild(dayColumns);
        });
        
        // Setup scroll synchronization between left and right sections
        this.setupScrollSynchronization();
        
        // Render time block cards after all rows are created
        this.timeBlockManager.renderTimeBlockCards();
    }
    
    // Time block methods moved to TimeBlockManager class
    
    /**
     * Calculate days between two dates (inclusive) - delegated to SchedulerUtils
     */
    calculateDaysBetween(startDate, endDate) {
        return SchedulerUtils.calculateDaysBetween(startDate, endDate);
    }
    
    /**
     * Edit a time block - delegated to TimeBlockManager
     */
    editTimeBlock(rowIndex, blockData, type) {
        this.timeBlockManager.editTimeBlock(rowIndex, blockData, type);
    }
    
    /**
     * Update a time block - delegated to TimeBlockManager
     */
    async updateTimeBlock(rowIndex, blockData, updates) {
        await this.timeBlockManager.updateTimeBlock(rowIndex, blockData, updates);
    }
    
    // Row creation methods moved to RowRenderer class
    
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
            if (row.project && row.activity && row.type === 'activity-row') {
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
                    r.project === row.project && r.type === 'activity-row' && r.dailyEntries
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
            // Activity row logic - check for time entries in daily entries JSON
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
            if (row.project && row.activity) {
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
                cell.title = 'Select project and activity first';
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
        this.dropdownManager.showProjectDropdown(cell, rowIndex);
    }
    
    /**
     * Show activity dropdown
     */
    showActivityDropdown(cell, rowIndex) {
        this.dropdownManager.showActivityDropdown(cell, rowIndex);
    }

    
    /**
     * Show role dropdown
     */
    showRoleDropdown(cell, rowIndex) {
        this.dropdownManager.showRoleDropdown(cell, rowIndex);
    }

    /**
     * Show person dropdown
     */
    showPersonDropdown(cell, rowIndex) {
        this.dropdownManager.showResourceDropdown(cell, rowIndex);
    }
    
    /**
     * Hide all dropdowns
     */
    hideAllDropdowns() {
        this.dropdownManager.hideAllDropdowns();
    }
    
    /**
     * Handle outside click to close dropdowns
     */
    handleOutsideClick(event) {
        // Check if the click is outside both the dropdown and the cell that triggered it
        if (!event.target.closest('.cell-dropdown') && !event.target.closest('.schedule-cell')) {
            this.hideAllDropdowns();
            // Remove the event listener after handling
            document.removeEventListener('click', this.boundHandleOutsideClick);
            this.boundHandleOutsideClick = null;
        }
    }
    
    /**
     * Select project for a row
     */
    selectProject(rowIndex, project) {
        this.rowManager.selectProject(rowIndex, project);
    }
    
    /**
     * Select activity for a row
     */
    async selectActivity(rowIndex, activity) {
        await this.rowManager.selectActivity(rowIndex, activity);
    }
    
    /**
     * Select role for a row
     */
    async selectRole(rowIndex, role) {
        await this.rowManager.selectRole(rowIndex, role);
    }

    /**
     * Select person for a row
     */
    async selectPerson(rowIndex, resource) {
        await this.rowManager.selectResource(rowIndex, resource);
    }
    
    /**
     * Create entry for a specific cell
     */
    createEntryForCell(rowIndex, date) {
        const row = this.state.scheduleRows[rowIndex];
        
        if (!row.project || !row.activity) {
            this.showToast('Please select project and activity first', 'warning');
            return;
        }
        
        // Pre-fill modal with row data
        this.openEntryModal(null, {
            project: row.project,
            activity: row.activity,
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
                    activities: {}
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
            activity: null,
            activityName: null,
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
            activity: null,
            activityName: null,
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
                activity: null,
                activityName: null,
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
        document.getElementById('entryActivity').value = entry.activity || '';
        document.getElementById('entryResource').value = entry.resource || '';
        document.getElementById('entryDate').value = entry.schedule_date || this.getTodayString();
        document.getElementById('entryDuration').value = entry.duration || 1;
        document.getElementById('entryPriority').value = entry.priority || 'Medium';
        document.getElementById('entryDescription').value = entry.description || '';
        
        // Update activity options based on selected project
        this.updateEntryActivityOptions();
        
        // Store entry ID for updates
        this.currentEditingEntry = entry.name;
    }
    
    prefillModal(prefill) {
        if (prefill.project) {
            document.getElementById('entryProject').value = prefill.project;
            const project = this.state.projects.find(p => p.name === prefill.project);
            document.getElementById('entryProjectDisplay').textContent = project ? project.project_name : prefill.project;
        }
        
        if (prefill.activity) {
            document.getElementById('entryActivity').value = prefill.activity;
            const project = this.state.projects.find(p => p.name === prefill.project);
            if (project && project.activities) {
                const activity = project.activities.find(t => t.name === prefill.activity);
                document.getElementById('entryActivityDisplay').textContent = activity ? activity.activity_name : prefill.activity;
            }
        }
        
        if (prefill.resource) document.getElementById('entryResource').value = prefill.resource;
        if (prefill.date) document.getElementById('entryDate').value = prefill.date;
    }
    
    updateEntryActivityOptions() {
        const projectSelect = document.getElementById('entryProject');
        const activitySelect = document.getElementById('entryActivity');
        
        activitySelect.innerHTML = '<option value="">Select Activity</option>';
        
        if (projectSelect.value) {
            const project = this.state.projects.find(p => p.name === projectSelect.value);
            if (project && project.activities) {
                project.activities.forEach(activity => {
                    const option = document.createElement('option');
                    option.value = activity.name;
                    option.textContent = activity.activity_name;
                    activitySelect.appendChild(option);
                });
            }
        }
    }
    
    clearModal() {
        document.getElementById('entryProject').value = '';
        document.getElementById('entryActivity').value = '';
        document.getElementById('entryResource').value = '';
        document.getElementById('entryDate').value = this.getTodayString();
        document.getElementById('entryDuration').value = '1';
        document.getElementById('entryPriority').value = 'Medium';
        document.getElementById('entryDescription').value = '';
    }
    
    async saveEntry() {
        const formData = {
            project: document.getElementById('entryProject').value,
            activity: document.getElementById('entryActivity').value,
            resource: document.getElementById('entryResource').value || null,
            schedule_date: document.getElementById('entryDate').value,
            duration: parseFloat(document.getElementById('entryDuration').value),
            priority: document.getElementById('entryPriority').value,
            description: document.getElementById('entryDescription').value
        };
        
        if (!formData.project || !formData.activity || !formData.schedule_date) {
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
        
        if (!newRow.project || !newRow.activity) {
            this.showToast('Cannot move entry to incomplete row', 'error');
            return;
        }
        
        try {
            this.setLoading(true);
            
            const response = await this.apiCall('erplite.scheduler.api.update_schedule_entry', {
                name: entryId,
                data: JSON.stringify({
                    project: newRow.project,
                    activity: newRow.activity,
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
     * Copy activity down - creates a duplicate activity row below the current one
     */
    copyActivityDown(rowIndex) {
        if (rowIndex >= 0 && rowIndex < this.state.scheduleRows.length) {
            const sourceRow = this.state.scheduleRows[rowIndex];
            
            // Create a copy of the activity row
            const newRow = {
                type: 'activity-row',
                project: sourceRow.project,
                projectName: sourceRow.projectName,
                activity: sourceRow.activity,
                activityName: sourceRow.activityName,
                resource: sourceRow.resource,
                resourceName: sourceRow.resourceName,
                entries: [] // New row starts with no entries
            };
            
            // Insert the new row right after the current one
            this.state.scheduleRows.splice(rowIndex + 1, 0, newRow);
            
            // Add another blank row after the copied row
            this.state.scheduleRows.splice(rowIndex + 2, 0, {
                type: 'activity-row',
                project: sourceRow.project,
                projectName: sourceRow.projectName,
                activity: null,
                activityName: null,
                resource: null,
                resourceName: null,
                entries: []
            });
            
            this.renderScheduleRows();
            this.showToast('Activity copied down successfully!', 'success');
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
    
    /**
     * Get today's date string - delegates to SchedulerUtils
     */
    getTodayString() {
        return SchedulerUtils.getTodayString();
    }
    
    /**
     * Add days to date string - delegates to SchedulerUtils
     */
    addDays(dateString, days) {
        return SchedulerUtils.addDays(dateString, days);
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
    
    /**
     * Make API call - delegates to DataManager
     */
    async apiCall(method, args = {}) {
        return await this.dataManager.apiCall(method, args);
    }
    
    // Cleanup
    cleanup() {
        this.dropdownManager.cleanup();
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
        
        if (!row.project || !row.activity) {
            this.showToast('Please select project and activity first', 'warning');
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
     * Get template configuration - delegates to SchedulerUtils
     */
    getTemplateConfig(template) {
        return SchedulerUtils.getTemplateConfig(template);
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

    // Time block resize methods moved to TimeBlockManager class
    
    /**
     * Start resizing a time block card - delegated to TimeBlockManager
     */
    startResize(event, card, direction, rowIndex, blockData) {
        this.timeBlockManager.startResize(event, card, direction, rowIndex, blockData);
    }
    
    /**
     * Group consecutive entries - delegates to SchedulerUtils
     */
    groupConsecutiveEntries(entries) {
        return SchedulerUtils.groupConsecutiveEntries(entries);
    }
    
    /**
     * Check if entries can be grouped - delegates to SchedulerUtils
     */
    canEntriesBeGrouped(block, entry) {
        return SchedulerUtils.canEntriesBeGrouped(block, entry);
    }
    
    /**
     * Check if dates are consecutive - delegates to SchedulerUtils
     */
    isConsecutiveDate(date1, date2) {
        return SchedulerUtils.isConsecutiveDate(date1, date2);
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

    /**
     * Create resource avatar - delegates to ResourceUtils
     */
    createResourceAvatar(resource) {
        return ResourceUtils.createResourceAvatar(resource);
    }

    /**
     * Get resource color - delegates to ResourceUtils
     */
    getResourceColor(name) {
        return ResourceUtils.getResourceColor(name);
    }

    /**
     * Get resource type icon - delegates to ResourceUtils
     */
    getResourceTypeIcon(resourceType) {
        return ResourceUtils.getResourceTypeIcon(resourceType);
    }

    /**
     * Setup scroll synchronization between left and right sections
     */
    setupScrollSynchronization() {
        const fixedLeftBody = document.getElementById('fixedLeftBody');
        const scrollableRightBody = document.getElementById('gridBody');
        
        if (!fixedLeftBody || !scrollableRightBody) return;
        
        // Remove any existing scroll listeners to prevent duplicates
        if (this.leftScrollHandler) {
            fixedLeftBody.removeEventListener('scroll', this.leftScrollHandler);
        }
        if (this.rightScrollHandler) {
            scrollableRightBody.removeEventListener('scroll', this.rightScrollHandler);
        }
        
        // Flag to prevent infinite scroll loops
        let isScrolling = false;
        
        // Sync right section when left section scrolls
        this.leftScrollHandler = () => {
            if (isScrolling) return;
            isScrolling = true;
            scrollableRightBody.scrollTop = fixedLeftBody.scrollTop;
            setTimeout(() => { isScrolling = false; }, 10);
        };
        
        // Sync left section when right section scrolls
        this.rightScrollHandler = () => {
            if (isScrolling) return;
            isScrolling = true;
            fixedLeftBody.scrollTop = scrollableRightBody.scrollTop;
            setTimeout(() => { isScrolling = false; }, 10);
        };
        
        // Add scroll event listeners
        fixedLeftBody.addEventListener('scroll', this.leftScrollHandler);
        scrollableRightBody.addEventListener('scroll', this.rightScrollHandler);
        
        console.log('Scroll synchronization setup complete');
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

window.copyActivityDown = function(rowIndex) {
    if (window.scheduler) {
        window.scheduler.copyActivityDown(rowIndex);
    }
};
