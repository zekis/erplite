// Global variables
let draggedElement = null;
let timeBlocks = [];
let currentWeekStart = null;
let existingTimesheets = [];
let projectColors = {};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get data from window object (set by template)
    if (window.timesheetData) {
        currentWeekStart = window.timesheetData.currentWeekStart;
        existingTimesheets = window.timesheetData.existingTimesheets;
        projectColors = window.timesheetData.projectColors;
    }
    
    initializeExistingTimeBlocks();
    setupDragAndDrop();
    updateDaySummaries();
});

function initializeExistingTimeBlocks() {
    existingTimesheets.forEach(timesheet => {
        if (timesheet.check_in_time && timesheet.check_out_time) {
            const startTime = new Date(timesheet.check_in_time);
            const endTime = new Date(timesheet.check_out_time);
            
            createTimeBlock({
                project: timesheet.project,
                activity: timesheet.activity,
                projectName: timesheet.project,
                activityName: timesheet.activity,
                color: projectColors[timesheet.project] || '#6b7280',
                date: timesheet.date,
                startHour: startTime.getHours(),
                startMinute: startTime.getMinutes(),
                duration: timesheet.duration_hours || 1,
                id: timesheet.name
            });
        }
    });
}

function setupDragAndDrop() {
    // Setup drag start for activity blocks
    document.querySelectorAll('.activity-block').forEach(block => {
        block.addEventListener('dragstart', function(e) {
            draggedElement = this;
            this.classList.add('dragging');
            
            e.dataTransfer.setData('text/plain', JSON.stringify({
                project: this.dataset.project,
                activity: this.dataset.activity,
                projectName: this.dataset.projectName,
                activityName: this.dataset.activityName,
                color: this.dataset.color
            }));
        });
        
        block.addEventListener('dragend', function() {
            this.classList.remove('dragging');
            draggedElement = null;
        });
    });
}

function allowDrop(event) {
    event.preventDefault();
}

function dragEnter(event) {
    event.preventDefault();
    event.currentTarget.classList.add('drop-zone');
}

function dragLeave(event) {
    event.currentTarget.classList.remove('drop-zone');
}

function dropTimeBlock(event) {
    event.preventDefault();
    event.currentTarget.classList.remove('drop-zone');
    
    if (!draggedElement) return;
    
    const timeSlot = event.currentTarget;
    const dayColumn = timeSlot.closest('.day-column');
    const date = dayColumn.dataset.date;
    const hour = parseInt(timeSlot.dataset.hour);
    
    const activityData = JSON.parse(event.dataTransfer.getData('text/plain'));
    
    // Create time block
    createTimeBlock({
        ...activityData,
        date: date,
        startHour: hour,
        startMinute: 0,
        duration: 1 // Default 1 hour
    });
    
    updateDaySummaries();
}

function createTimeBlock(data) {
    const dayColumn = document.querySelector(`[data-date="${data.date}"]`);
    if (!dayColumn) return;
    
    const template = document.getElementById('time-block-template');
    const timeBlock = template.content.cloneNode(true).querySelector('.time-block');
    
    // Set content
    timeBlock.querySelector('.time-block-header').textContent = data.projectName;
    timeBlock.querySelector('.time-block-activity').textContent = data.activityName;
    timeBlock.querySelector('.time-block-duration').textContent = `${data.duration}h`;
    
    // Set style
    timeBlock.style.backgroundColor = data.color;
    timeBlock.style.top = `${(data.startHour - 8) * 60 + (data.startMinute || 0)}px`;
    timeBlock.style.height = `${data.duration * 60}px`;
    
    // Add data attributes
    timeBlock.dataset.project = data.project;
    timeBlock.dataset.activity = data.activity;
    timeBlock.dataset.duration = data.duration;
    timeBlock.dataset.startHour = data.startHour;
    timeBlock.dataset.startMinute = data.startMinute || 0;
    if (data.id) timeBlock.dataset.id = data.id;
    
    // Add event listeners
    timeBlock.addEventListener('click', editTimeBlock);
    timeBlock.addEventListener('contextmenu', showTimeBlockMenu);
    
    // Setup resize handles
    setupResizeHandles(timeBlock);
    
    dayColumn.appendChild(timeBlock);
    timeBlocks.push(timeBlock);
}

function setupResizeHandles(timeBlock) {
    const topHandle = timeBlock.querySelector('.resize-handle.top');
    const bottomHandle = timeBlock.querySelector('.resize-handle.bottom');
    
    let isResizing = false;
    let startY = 0;
    let startHeight = 0;
    let startTop = 0;
    let activeHandle = null;
    
    function startResize(e, handle) {
        isResizing = true;
        activeHandle = handle;
        startY = e.clientY;
        startHeight = timeBlock.offsetHeight;
        startTop = timeBlock.offsetTop;
        
        document.addEventListener('mousemove', resize);
        document.addEventListener('mouseup', stopResize);
        e.preventDefault();
        e.stopPropagation();
    }
    
    function resize(e) {
        if (!isResizing) return;
        
        const deltaY = e.clientY - startY;
        let newHeight = startHeight;
        let newTop = startTop;
        
        if (activeHandle === bottomHandle) {
            newHeight = Math.max(30, startHeight + deltaY);
        } else if (activeHandle === topHandle) {
            newHeight = Math.max(30, startHeight - deltaY);
            newTop = startTop + deltaY;
        }
        
        // Snap to 30-minute intervals
        newHeight = Math.round(newHeight / 30) * 30;
        newTop = Math.round(newTop / 30) * 30;
        
        timeBlock.style.height = `${newHeight}px`;
        timeBlock.style.top = `${newTop}px`;
        
        // Update duration
        const duration = newHeight / 60;
        timeBlock.dataset.duration = duration;
        timeBlock.querySelector('.time-block-duration').textContent = `${duration}h`;
    }
    
    function stopResize() {
        isResizing = false;
        activeHandle = null;
        document.removeEventListener('mousemove', resize);
        document.removeEventListener('mouseup', stopResize);
        updateDaySummaries();
    }
    
    topHandle.addEventListener('mousedown', (e) => startResize(e, topHandle));
    bottomHandle.addEventListener('mousedown', (e) => startResize(e, bottomHandle));
}

function editTimeBlock(event) {
    const timeBlock = event.currentTarget;
    
    // Create edit dialog
    const dialog = new frappe.ui.Dialog({
        title: 'Edit Time Entry',
        fields: [
            {
                label: 'Project',
                fieldname: 'project',
                fieldtype: 'Link',
                options: 'Project',
                default: timeBlock.dataset.project,
                reqd: 1
            },
            {
                label: 'Activity',
                fieldname: 'activity',
                fieldtype: 'Link',
                options: 'Activity',
                default: timeBlock.dataset.activity,
                reqd: 1
            },
            {
                label: 'Duration (hours)',
                fieldname: 'duration',
                fieldtype: 'Float',
                default: parseFloat(timeBlock.dataset.duration),
                reqd: 1
            },
            {
                label: 'Description',
                fieldname: 'description',
                fieldtype: 'Text',
                default: ''
            }
        ],
        primary_action_label: 'Update',
        primary_action: function() {
            const values = dialog.get_values();
            
            // Update time block
            timeBlock.dataset.duration = values.duration;
            timeBlock.style.height = `${values.duration * 60}px`;
            timeBlock.querySelector('.time-block-duration').textContent = `${values.duration}h`;
            
            updateDaySummaries();
            dialog.hide();
        }
    });
    
    dialog.show();
}

function showTimeBlockMenu(event) {
    event.preventDefault();
    const timeBlock = event.currentTarget;
    
    if (confirm('Delete this time entry?')) {
        timeBlock.remove();
        timeBlocks = timeBlocks.filter(block => block !== timeBlock);
        updateDaySummaries();
    }
}

function updateDaySummaries() {
    document.querySelectorAll('.day-column').forEach(dayColumn => {
        const blocks = dayColumn.querySelectorAll('.time-block');
        let totalHours = 0;
        
        blocks.forEach(block => {
            totalHours += parseFloat(block.dataset.duration || 0);
        });
        
        const summary = dayColumn.querySelector('.total-hours');
        if (summary) {
            summary.textContent = `${totalHours.toFixed(1)}h`;
        }
    });
}

function toggleProject(projectName) {
    const projectGroup = document.querySelector(`[data-project="${projectName}"]`);
    if (projectGroup) {
        projectGroup.classList.toggle('collapsed');
    }
}

function changeWeek(direction) {
    const currentDate = new Date(currentWeekStart);
    currentDate.setDate(currentDate.getDate() + (direction * 7));
    
    const newWeekStart = currentDate.toISOString().split('T')[0];
    window.location.href = `/timesheet-calendar?week=${newWeekStart}`;
}

function clearWeek() {
    if (confirm('Clear all time entries for this week?')) {
        timeBlocks.forEach(block => block.remove());
        timeBlocks = [];
        updateDaySummaries();
    }
}

function saveTimesheet() {
    const entries = [];
    
    timeBlocks.forEach(block => {
        const dayColumn = block.closest('.day-column');
        const date = dayColumn.dataset.date;
        const startHour = parseInt(block.dataset.startHour);
        const startMinute = parseInt(block.dataset.startMinute || 0);
        const duration = parseFloat(block.dataset.duration);
        
        entries.push({
            id: block.dataset.id || null,
            project: block.dataset.project,
            activity: block.dataset.activity,
            date: date,
            start_time: `${String(startHour).padStart(2, '0')}:${String(startMinute).padStart(2, '0')}`,
            duration: duration
        });
    });
    
    frappe.call({
        method: 'erplite.projects.api.save_timesheet_entries',
        args: { entries: entries },
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.msgprint('Timesheet saved successfully!');
            } else {
                frappe.msgprint('Error saving timesheet: ' + (r.message.message || 'Unknown error'));
            }
        }
    });
}

// Quick time entry functions
function addQuickTime(hours) {
    // Add a quick time entry for the specified hours
    const today = new Date().toISOString().split('T')[0];
    const currentHour = new Date().getHours();
    
    // Find first available project/activity
    const firstActivityBlock = document.querySelector('.activity-block');
    if (!firstActivityBlock) {
        frappe.msgprint('No activities available. Please create a project and activity first.');
        return;
    }
    
    const activityData = {
        project: firstActivityBlock.dataset.project,
        activity: firstActivityBlock.dataset.activity,
        projectName: firstActivityBlock.dataset.projectName,
        activityName: firstActivityBlock.dataset.activityName,
        color: firstActivityBlock.dataset.color,
        date: today,
        startHour: Math.max(8, currentHour),
        startMinute: 0,
        duration: hours
    };
    
    createTimeBlock(activityData);
    updateDaySummaries();
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + S to save
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveTimesheet();
    }
    
    // Ctrl/Cmd + 1-4 for quick time entries
    if ((e.ctrlKey || e.metaKey) && ['1', '2', '3', '4'].includes(e.key)) {
        e.preventDefault();
        const hours = parseInt(e.key);
        addQuickTime(hours);
    }
});

// Export functions to global scope for HTML onclick handlers
window.toggleProject = toggleProject;
window.changeWeek = changeWeek;
window.clearWeek = clearWeek;
window.saveTimesheet = saveTimesheet;
window.allowDrop = allowDrop;
window.dragEnter = dragEnter;
window.dragLeave = dragLeave;
window.dropTimeBlock = dropTimeBlock;
