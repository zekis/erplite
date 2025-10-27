/**
 * Row Renderer
 * Handles the creation and rendering of schedule rows, cells, and entries
 */
class RowRenderer {
    constructor(app) {
        this.app = app;
    }

    /**
     * Create a schedule row - returns separate fixed columns and day columns
     */
    createScheduleRow(row, index) {
        // Create fixed columns row
        const fixedColumnsRow = document.createElement('div');
        fixedColumnsRow.className = 'schedule-row';
        fixedColumnsRow.dataset.rowIndex = index;
        
        // Create day columns row
        const dayColumnsRow = document.createElement('div');
        dayColumnsRow.className = 'schedule-row';
        dayColumnsRow.dataset.rowIndex = index;
        
        // Add row type classes to both
        if (row.type === 'project-header') {
            fixedColumnsRow.classList.add('project-header');
            dayColumnsRow.classList.add('project-header');
            // Set a light shade of the project color as background if available
            if (row.project && this.app.state.projectColors[row.project]) {
                const bgColor = SchedulerUtils.hexToRgba(this.app.state.projectColors[row.project], 0.10);
                fixedColumnsRow.style.background = bgColor;
                dayColumnsRow.style.background = bgColor;
            }
        } else if (row.type === 'activity-row') {
            fixedColumnsRow.classList.add('activity-row');
            dayColumnsRow.classList.add('activity-row');
        }
        
        // Create the three fixed columns
        const projectActivityCell = this.createProjectActivityCell(row, index);
        const roleCell = this.createRoleCell(row, index);
        const resourceCell = this.createResourceCell(row, index);
        
        // Add cells to fixed columns row
        fixedColumnsRow.appendChild(projectActivityCell);
        fixedColumnsRow.appendChild(roleCell);
        fixedColumnsRow.appendChild(resourceCell);
        
        // Create day cells for the scrollable section
        const daysContainer = document.createElement('div');
        daysContainer.className = 'schedule-days';
        
        for (let i = 0; i < this.app.state.dateRange; i++) {
            const date = SchedulerUtils.addDays(this.app.state.currentStartDate, i);
            const dayCell = this.createDayCell(row, date, index);
            daysContainer.appendChild(dayCell);
        }
        
        // Add days container to day columns row
        dayColumnsRow.appendChild(daysContainer);
        
        return {
            fixedColumns: fixedColumnsRow,
            dayColumns: dayColumnsRow
        };
    }

    /**
     * Create project/activity cell
     */
    createProjectActivityCell(row, index) {
        const projectActivityCell = document.createElement('div');
        projectActivityCell.className = 'schedule-cell project-activity-cell';
        projectActivityCell.dataset.type = 'project-activity';
        projectActivityCell.dataset.rowIndex = index;
        
        if (row.type === 'project-header') {
            // Project header row
            if (row.project) {
                projectActivityCell.classList.add('filled');
                
                // Create project header content with work type
                const projectContent = document.createElement('div');
                projectContent.style.display = 'flex';
                projectContent.style.flexDirection = 'column';
                projectContent.style.alignItems = 'center';
                
                const projectName = document.createElement('div');
                projectName.textContent = row.projectName;
                projectName.style.fontWeight = '600';
                projectName.style.fontSize = '0.875rem';
                
                projectContent.appendChild(projectName);
                
                // Add work type if available
                if (row.workType) {
                    const workType = document.createElement('div');
                    workType.textContent = row.workType;
                    workType.style.fontSize = '0.75rem';
                    workType.style.color = '#6b7280';
                    workType.style.fontStyle = 'italic';
                    workType.style.marginTop = '0.125rem';
                    projectContent.appendChild(workType);
                }
                
                projectActivityCell.appendChild(projectContent);
                projectActivityCell.style.setProperty('--project-color', this.app.state.projectColors[row.project] || '#6b7280');
                projectActivityCell.style.borderLeft = `4px solid var(--project-color)`;
            } else {
                projectActivityCell.classList.add('empty');
                projectActivityCell.textContent = 'Select Project';
                projectActivityCell.addEventListener('click', () => this.app.showProjectDropdown(projectActivityCell, index));
            }
        } else {
            // Activity row
            if (row.activity) {
                projectActivityCell.classList.add('filled');
                projectActivityCell.textContent = row.activityName;
                projectActivityCell.style.position = 'relative';
                
                // Add row controls for activity rows
                const rowControls = document.createElement('div');
                rowControls.className = 'row-controls';
                
                // Create copy button
                const copyBtn = document.createElement('button');
                copyBtn.className = 'row-control-btn copy-down-btn';
                copyBtn.title = 'Copy activity down';
                copyBtn.innerHTML = '<i class="mdi mdi-content-copy"></i>';
                copyBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.app.rowManager.copyActivityDown(index);
                });
                
                // Create delete button
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'row-control-btn delete-row-btn';
                deleteBtn.title = 'Delete activity';
                deleteBtn.innerHTML = '<i class="mdi mdi-delete"></i>';
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (confirm('Are you sure you want to delete this activity row?')) {
                        this.app.rowManager.deleteRow(index);
                    }
                });
                
                rowControls.appendChild(copyBtn);
                rowControls.appendChild(deleteBtn);
                projectActivityCell.appendChild(rowControls);
            } else if (row.project) {
                projectActivityCell.classList.add('empty');
                projectActivityCell.textContent = 'Select Activity';
                projectActivityCell.addEventListener('click', () => this.app.showActivityDropdown(projectActivityCell, index));
            } else {
                projectActivityCell.classList.add('empty');
                projectActivityCell.textContent = 'Select Project First';
            }
        }
        
        return projectActivityCell;
    }

    /**
     * Create role cell
     */
    createRoleCell(row, index) {
        const roleCell = document.createElement('div');
        roleCell.className = 'schedule-cell role-cell';
        roleCell.dataset.type = 'role';
        roleCell.dataset.rowIndex = index;
        
        if (row.type === 'project-header') {
            // Project headers show role summary
            roleCell.classList.add('filled');
            roleCell.textContent = 'Roles';
            roleCell.style.fontSize = '0.875rem';
            roleCell.style.color = '#6b7280';
            roleCell.style.cursor = 'default';
        } else {
            // Activity rows can have roles only if activity is selected
            if (!row.activity) {
                // No activity selected - disable role selection, show blank
                roleCell.classList.add('disabled');
                roleCell.textContent = '';
                roleCell.style.cursor = 'not-allowed';
                roleCell.style.color = '#9ca3af';
                roleCell.title = 'Please select an activity first';
            } else {
                // Activity selected - enable role selection
                if (row.role) {
                    roleCell.classList.add('filled');
                    
                    // Find the role data to create icon
                    const role = this.app.state.roles.find(r => r.name === row.role);
                    if (role) {
                        roleCell.innerHTML = `
                            <div style="display: flex; align-items: center; height: 100%; padding: 0.25rem; justify-content: flex-start;">
                                <div style="width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; background: #f0f9ff; border-radius: 6px; flex-shrink: 0;">
                                    <i class="mdi mdi-account-tie" style="font-size: 14px; color: #0ea5e9;"></i>
                                </div>
                                <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.2;">${row.roleName || row.role}</span>
                            </div>
                        `;
                    } else {
                        roleCell.textContent = row.roleName || row.role;
                    }
                } else {
                    roleCell.classList.add('empty');
                    roleCell.innerHTML = `
                        <div style="display: flex; align-items: center; height: 100%; padding: 0.25rem; justify-content: flex-start;">
                            <div style="width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; background: #f1f5f9; border-radius: 6px; flex-shrink: 0;">
                                <i class="mdi mdi-account-multiple-outline" style="font-size: 14px; color: #64748b;"></i>
                            </div>
                            <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.2;">Any</span>
                        </div>
                    `;
                }
                roleCell.addEventListener('click', () => this.app.showRoleDropdown(roleCell, index));
            }
        }
        
        return roleCell;
    }

    /**
     * Create resource cell
     */
    createResourceCell(row, index) {
        const resourceCell = document.createElement('div');
        resourceCell.className = 'schedule-cell resource-cell';
        resourceCell.dataset.type = 'resource';
        resourceCell.dataset.rowIndex = index;
        
        if (row.type === 'project-header') {
            // Project headers show resource count
            resourceCell.style.visibility = 'visible';
            resourceCell.style.cursor = 'default';
            resourceCell.classList.add('filled');
            
            // Calculate resource type counts for this project
            const projectRows = this.app.state.scheduleRows.filter(r => 
                r.project === row.project && r.type === 'activity-row' && r.resource
            );
            
            // Use ResourceUtils to group resources by type
            const resourceTypeCounts = ResourceUtils.groupResourcesByType(
                this.app.state.resources, 
                this.app.state.scheduleRows, 
                row.project
            );
            
            // Create resource summary display
            resourceCell.innerHTML = ResourceUtils.createResourceSummary(resourceTypeCounts);
            resourceCell.style.fontSize = '0.875rem';
            resourceCell.style.color = '#6b7280';
        } else {
            // Activity rows can have resources only if activity is selected
            if (!row.activity) {
                // No activity selected - disable resource selection, show blank
                resourceCell.classList.add('disabled');
                resourceCell.textContent = '';
                resourceCell.style.cursor = 'not-allowed';
                resourceCell.style.color = '#9ca3af';
                resourceCell.title = 'Please select an activity first';
            } else {
                // Activity selected - enable resource selection
                resourceCell.style.visibility = 'visible';
                resourceCell.style.fontSize = '';
                resourceCell.style.color = '';
                
                if (row.resource) {
                    resourceCell.classList.add('filled');
                    
                    // Find the resource data to create avatar
                    const resource = this.app.state.resources.find(r => r.name === row.resource);
                    if (resource) {
                        const avatar = ResourceUtils.createResourceAvatar(resource);
                        resourceCell.innerHTML = `
                            <div style="display: flex; align-items: center; gap: 8px; height: 100%; padding: 0.25rem; justify-content: flex-start; width: 100%; max-width: 100%; overflow: hidden;">
                                ${avatar}
                                <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.2; min-width: 0; flex: 1; max-width: calc(100% - 32px);">${row.resourceName}</span>
                            </div>
                        `;
                    } else {
                        resourceCell.textContent = row.resourceName;
                    }
                } else {
                    resourceCell.classList.add('empty');
                    resourceCell.textContent = 'Select Resource';
                }
                resourceCell.addEventListener('click', () => this.app.showPersonDropdown(resourceCell, index));
            }
        }
        
        return resourceCell;
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
        
        // Add new click and drag selection handlers for activity rows
        if (row.type === 'activity-row' && row.project && row.activity) {
            cell.classList.add('interactive');
            
            // Single click handler
            cell.addEventListener('click', (e) => this.app.handleCellClick(e, rowIndex, date));
            
            // Drag selection handlers
            cell.addEventListener('mousedown', (e) => this.app.handleCellMouseDown(e, rowIndex, date));
        }
        
        const entriesContainer = document.createElement('div');
        entriesContainer.className = 'day-entries';
        
        if (row.type === 'project-header') {
            // Project header shows daily totals for the project
            if (row.project) {
                // Calculate total hours for this project on this date from Schedule Rows
                let totalHours = 0;
                
                // Get total from Schedule Rows if available
                const projectRows = this.app.state.scheduleRows.filter(r => 
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
                    const projectEntries = this.app.state.scheduleEntries.filter(entry => 
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
        const projectColor = this.app.state.projectColors[entry.project] || '#6b7280';
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
     * Create a time entry element for Schedule Row daily entries
     */
    createTimeEntry(entry, date, row) {
        const element = document.createElement('div');
        element.className = 'time-entry';
        element.dataset.date = date;
        element.dataset.rowIndex = row.scheduleRowId;
        
        // Set project color
        const projectColor = this.app.state.projectColors[row.project] || '#3b82f6';
        element.style.setProperty('--project-color', projectColor);
        
        const hours = typeof entry === 'object' ? entry.hours : entry;
        const description = typeof entry === 'object' ? entry.description : '';
        
        element.innerHTML = `
            <div class="time-entry-hours">${hours}h</div>
            <div class="time-entry-time">9:00 - 17:00</div>
        `;
        
        // Add click handler for editing
        element.addEventListener('click', () => {
            this.app.editTimeEntry(row.scheduleRowId, date, entry);
        });
        
        return element;
    }
}

// Export to global scope for HTML compatibility
window.RowRenderer = RowRenderer;
