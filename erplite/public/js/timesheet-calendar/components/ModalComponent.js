/**
 * Modal component for editing time blocks
 */
class ModalComponent {
    constructor(app) {
        this.app = app;
        this.currentEditingBlock = null;
        this.init();
    }
    
    /**
     * Initialize modal functionality
     */
    init() {
        this.setupModalEvents();
    }
    
    /**
     * Setup modal event listeners
     */
    setupModalEvents() {
        // Close modal when clicking outside
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeEditModal();
            }
        });
        
        // Close modal on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isModalOpen()) {
                this.closeEditModal();
            }
        });
        
        // Setup project change handler
        const projectSelect = document.getElementById('editProject');
        if (projectSelect) {
            projectSelect.addEventListener('change', () => this.updateActivityOptions());
        }
    }
    
    /**
     * Open edit modal for a time block
     */
    openEditModal(timeBlock) {
        this.currentEditingBlock = timeBlock;
        this.populateEditModal(timeBlock);
        
        const modal = document.getElementById('editTimeBlockModal');
        if (modal) {
            modal.style.display = 'block';
            
            // Focus first input
            const firstInput = modal.querySelector('input, select, textarea');
            if (firstInput) {
                setTimeout(() => firstInput.focus(), 100);
            }
        }
    }
    
    /**
     * Close edit modal
     */
    closeEditModal() {
        const modal = document.getElementById('editTimeBlockModal');
        if (modal) {
            modal.style.display = 'none';
        }
        this.currentEditingBlock = null;
    }
    
    /**
     * Check if modal is currently open
     */
    isModalOpen() {
        const modal = document.getElementById('editTimeBlockModal');
        return modal && modal.style.display === 'block';
    }
    
    /**
     * Populate edit modal with time block data
     */
    populateEditModal(timeBlock) {
        const dayColumn = timeBlock.closest('.day-column');
        const date = dayColumn.dataset.date;
        const startHour = parseInt(timeBlock.dataset.startHour);
        const startMinute = parseInt(timeBlock.dataset.startMinute || 0);
        const duration = parseFloat(timeBlock.dataset.duration);
        
        // Calculate end time properly
        const totalStartMinutes = startHour * 60 + startMinute;
        const totalDurationMinutes = duration * 60;
        const totalEndMinutes = totalStartMinutes + totalDurationMinutes;
        
        const endHour = Math.floor(totalEndMinutes / 60);
        const endMinute = totalEndMinutes % 60;
        
        // Handle timesheet entry link
        this.setupTimesheetEntryLink(timeBlock);
        
        // Populate project dropdown
        this.populateProjectDropdown(timeBlock.dataset.project);
        
        // Update activity options based on selected project
        this.updateActivityOptions();
        
        // Set current activity
        const activitySelect = document.getElementById('editActivity');
        if (activitySelect) {
            activitySelect.value = timeBlock.dataset.activity;
        }
        
        // Set times
        const startTimeInput = document.getElementById('editStartTime');
        const endTimeInput = document.getElementById('editEndTime');
        
        if (startTimeInput) {
            startTimeInput.value = TimeUtils.formatTime(startHour, startMinute);
        }
        
        if (endTimeInput) {
            endTimeInput.value = TimeUtils.formatTime(endHour, endMinute);
        }
        
        // Set description
        const descriptionInput = document.getElementById('editDescription');
        if (descriptionInput) {
            descriptionInput.value = timeBlock.dataset.description || '';
        }
    }
    
    /**
     * Setup timesheet entry link
     */
    setupTimesheetEntryLink(timeBlock) {
        const timesheetEntryLink = document.getElementById('timesheetEntryLink');
        const openTimesheetEntry = document.getElementById('openTimesheetEntry');
        const entryId = timeBlock.dataset.id;
        
        if (timesheetEntryLink && openTimesheetEntry) {
            if (entryId && entryId !== 'null') {
                // Show link for existing entries
                timesheetEntryLink.style.display = 'block';
                openTimesheetEntry.href = `/app/timesheet-entry/${entryId}`;
            } else {
                // Hide link for new entries
                timesheetEntryLink.style.display = 'none';
            }
        }
    }
    
    /**
     * Populate project dropdown
     */
    populateProjectDropdown(selectedProject = null) {
        const projectSelect = document.getElementById('editProject');
        if (!projectSelect) return;
        
        projectSelect.innerHTML = '<option value="">Select Project</option>';
        
        // Get projects from sidebar
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const projectId = projectGroup.dataset.project;
            const projectName = projectGroup.querySelector('.project-name').textContent;
            const option = document.createElement('option');
            option.value = projectId;
            option.textContent = projectName;
            if (projectId === selectedProject) {
                option.selected = true;
            }
            projectSelect.appendChild(option);
        });
    }
    
    /**
     * Update activity options based on selected project
     */
    updateActivityOptions() {
        const projectSelect = document.getElementById('editProject');
        const activitySelect = document.getElementById('editActivity');
        
        if (!projectSelect || !activitySelect) return;
        
        const selectedProject = projectSelect.value;
        
        activitySelect.innerHTML = '<option value="">Select Activity</option>';
        
        if (selectedProject && this.app.state.projectsData) {
            // Use API data instead of DOM elements
            const projectData = this.app.state.projectsData[selectedProject];
            if (projectData && projectData.activities) {
                projectData.activities.forEach(activity => {
                    const option = document.createElement('option');
                    option.value = activity.name;
                    option.textContent = activity.activity_name || activity.name;
                    activitySelect.appendChild(option);
                });
            }
        }
    }
    
    /**
     * Save time block edit
     */
    saveTimeBlockEdit() {
        if (!this.currentEditingBlock) return;
        
        const formData = this.getFormData();
        const validation = this.validateFormData(formData);
        
        if (!validation.isValid) {
            this.app.components.toast.error(validation.errors.join(', '));
            return;
        }
        
        // Check for conflicts
        const conflicts = this.checkTimeConflicts(formData);
        if (conflicts.length > 0) {
            this.app.components.toast.error('Time conflicts with existing entries');
            return;
        }
        
        // Update the time block
        this.updateTimeBlockFromForm(formData);
        
        // Close modal and update summaries
        this.closeEditModal();
        this.app.updateDaySummaries();
        
        // Auto-save
        this.app.managers.storage.autoSave();
        
        this.app.components.toast.success('Time entry updated successfully!');
    }
    
    /**
     * Get form data
     */
    getFormData() {
        const projectSelect = document.getElementById('editProject');
        const activitySelect = document.getElementById('editActivity');
        const startTimeInput = document.getElementById('editStartTime');
        const endTimeInput = document.getElementById('editEndTime');
        const descriptionInput = document.getElementById('editDescription');
        
        const startTime = TimeUtils.parseTime(startTimeInput.value);
        const endTime = TimeUtils.parseTime(endTimeInput.value);
        const duration = TimeUtils.calculateDuration(startTime.hour, startTime.minute, endTime.hour, endTime.minute);
        
        return {
            project: projectSelect.value,
            activity: activitySelect.value,
            projectName: projectSelect.options[projectSelect.selectedIndex]?.text || '',
            activityName: activitySelect.options[activitySelect.selectedIndex]?.text || '',
            startHour: startTime.hour,
            startMinute: startTime.minute,
            duration: duration,
            description: descriptionInput.value
        };
    }
    
    /**
     * Validate form data
     */
    validateFormData(data) {
        const errors = [];
        
        if (!data.project) errors.push('Please select a project');
        if (!data.activity) errors.push('Please select a activity');
        if (data.duration <= 0) errors.push('End time must be after start time');
        if (data.startHour < 0 || data.startHour > 23) errors.push('Invalid start time');
        if (data.startMinute < 0 || data.startMinute > 59) errors.push('Invalid start time');
        
        return {
            isValid: errors.length === 0,
            errors: errors
        };
    }
    
    /**
     * Check for time conflicts
     */
    checkTimeConflicts(data) {
        const dayColumn = this.currentEditingBlock.closest('.day-column');
        if (!dayColumn) return [];
        
        return TimeUtils.checkTimeOverlap(
            dayColumn, 
            data.startHour, 
            data.startMinute, 
            data.duration, 
            this.currentEditingBlock
        ) ? ['Time conflict detected'] : [];
    }
    
    /**
     * Update time block from form data
     */
    updateTimeBlockFromForm(data) {
        // Get project color
        const projectGroup = document.querySelector(`[data-project="${data.project}"]`);
        const projectColor = projectGroup ? 
            getComputedStyle(projectGroup.querySelector('.project-color')).backgroundColor : 
            '#6b7280';
        
        // Update data attributes
        this.currentEditingBlock.dataset.project = data.project;
        this.currentEditingBlock.dataset.activity = data.activity;
        this.currentEditingBlock.dataset.startHour = data.startHour;
        this.currentEditingBlock.dataset.startMinute = data.startMinute;
        this.currentEditingBlock.dataset.duration = data.duration;
        this.currentEditingBlock.dataset.description = data.description;
        
        // Update visual appearance using TimeBlockManager
        this.app.managers.timeBlock.updateTimeBlock(this.currentEditingBlock, {
            projectName: data.projectName,
            activityName: data.activityName,
            duration: data.duration,
            description: data.description,
            color: projectColor,
            startHour: data.startHour,
            startMinute: data.startMinute
        });
    }
    
    /**
     * Delete time block from modal
     */
    deleteTimeBlock() {
        if (!this.currentEditingBlock) return;
        
        if (confirm('Are you sure you want to delete this time entry?')) {
            this.app.managers.timeBlock.deleteTimeBlock(this.currentEditingBlock);
            this.closeEditModal();
        }
    }
    
    /**
     * Show modal with custom content
     */
    showCustomModal(title, content, actions = []) {
        // Create modal if it doesn't exist
        let modal = document.getElementById('customModal');
        if (!modal) {
            modal = this.createCustomModal();
        }
        
        // Set title
        const titleElement = modal.querySelector('.modal-title');
        if (titleElement) titleElement.textContent = title;
        
        // Set content
        const bodyElement = modal.querySelector('.modal-body');
        if (bodyElement) {
            if (typeof content === 'string') {
                bodyElement.innerHTML = content;
            } else {
                bodyElement.innerHTML = '';
                bodyElement.appendChild(content);
            }
        }
        
        // Set actions
        const footerElement = modal.querySelector('.modal-footer');
        if (footerElement) {
            footerElement.innerHTML = '';
            actions.forEach(action => {
                const button = DOMUtils.createElement('button', {
                    className: `btn ${action.class || 'btn-secondary'}`,
                    onclick: action.onclick
                }, action.text);
                
                if (action.handler) {
                    button.addEventListener('click', action.handler);
                }
                
                footerElement.appendChild(button);
            });
        }
        
        // Show modal
        modal.style.display = 'block';
        
        return modal;
    }
    
    /**
     * Create custom modal element
     */
    createCustomModal() {
        const modal = DOMUtils.createElement('div', {
            id: 'customModal',
            className: 'modal',
            style: { display: 'none' }
        });
        
        const modalContent = DOMUtils.createElement('div', {
            className: 'modal-content'
        });
        
        const modalHeader = DOMUtils.createElement('div', {
            className: 'modal-header'
        }, `
            <h3 class="modal-title"></h3>
            <span class="close">&times;</span>
        `);
        
        const modalBody = DOMUtils.createElement('div', {
            className: 'modal-body'
        });
        
        const modalFooter = DOMUtils.createElement('div', {
            className: 'modal-footer'
        });
        
        modalContent.appendChild(modalHeader);
        modalContent.appendChild(modalBody);
        modalContent.appendChild(modalFooter);
        modal.appendChild(modalContent);
        
        // Setup close functionality
        const closeBtn = modal.querySelector('.close');
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });
        
        document.body.appendChild(modal);
        
        return modal;
    }
    
    /**
     * Hide custom modal
     */
    hideCustomModal() {
        const modal = document.getElementById('customModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
}

// Export to global scope
window.ModalComponent = ModalComponent;

// Setup global functions for HTML compatibility
window.closeEditModal = function() {
    if (window.app && window.app.components.modal) {
        window.app.components.modal.closeEditModal();
    }
};

window.updateActivityOptions = function() {
    if (window.app && window.app.components.modal) {
        window.app.components.modal.updateActivityOptions();
    }
};

window.saveTimeBlockEdit = function() {
    if (window.app && window.app.components.modal) {
        window.app.components.modal.saveTimeBlockEdit();
    }
};

window.deleteTimeBlock = function() {
    if (window.app && window.app.components.modal) {
        window.app.components.modal.deleteTimeBlock();
    }
};
