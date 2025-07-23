/**
 * Context menu component for right-click actions
 */
class ContextMenuComponent {
    constructor(app) {
        this.app = app;
        this.currentMenu = null;
        this.targetElement = null;
        this.init();
    }
    
    /**
     * Initialize context menu functionality
     */
    init() {
        this.setupGlobalEvents();
        this.setupTimeBlockContextMenus();
    }
    
    /**
     * Setup global event listeners
     */
    setupGlobalEvents() {
        // Hide context menu when clicking elsewhere
        document.addEventListener('click', () => {
            this.hide();
        });
        
        // Hide context menu on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hide();
            }
        });
        
        // Prevent default context menu on time blocks
        document.addEventListener('contextmenu', (e) => {
            if (e.target.closest('.time-block')) {
                e.preventDefault();
            }
        });
    }
    
    /**
     * Setup context menus for time blocks
     */
    setupTimeBlockContextMenus() {
        // Use event delegation for dynamically created time blocks
        document.addEventListener('contextmenu', (e) => {
            const timeBlock = e.target.closest('.time-block');
            if (timeBlock) {
                e.preventDefault();
                this.showTimeBlockMenu(timeBlock, e);
            }
        });
    }
    
    /**
     * Show context menu at specific position
     */
    show(x, y, menuItems) {
        this.hide(); // Hide any existing menu
        
        const menu = this.createMenu(menuItems);
        document.body.appendChild(menu);
        
        // Position menu
        this.positionMenu(menu, x, y);
        
        // Show menu
        menu.style.display = 'block';
        this.currentMenu = menu;
        
        return menu;
    }
    
    /**
     * Hide context menu
     */
    hide() {
        if (this.currentMenu) {
            this.currentMenu.remove();
            this.currentMenu = null;
        }
        this.targetElement = null;
    }
    
    /**
     * Create menu element
     */
    createMenu(menuItems) {
        const menu = DOMUtils.createElement('div', {
            className: 'context-menu',
            style: {
                position: 'fixed',
                background: 'white',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                zIndex: '10001',
                display: 'none',
                minWidth: '150px',
                padding: '0.5rem 0'
            }
        });
        
        menuItems.forEach((item, index) => {
            if (item.separator) {
                const separator = DOMUtils.createElement('div', {
                    style: {
                        height: '1px',
                        background: '#e2e8f0',
                        margin: '0.5rem 0'
                    }
                });
                menu.appendChild(separator);
            } else {
                const menuItem = this.createMenuItem(item);
                menu.appendChild(menuItem);
            }
        });
        
        return menu;
    }
    
    /**
     * Create menu item element
     */
    createMenuItem(item) {
        const menuItem = DOMUtils.createElement('div', {
            className: 'context-menu-item',
            style: {
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.75rem 1rem',
                cursor: 'pointer',
                fontSize: '0.875rem',
                color: item.danger ? '#dc2626' : '#374151',
                transition: 'all 0.2s'
            }
        });
        
        // Add icon if provided
        if (item.icon) {
            const icon = DOMUtils.createElement('span', {
                className: 'context-icon',
                style: {
                    fontSize: '1rem',
                    width: '1rem',
                    textAlign: 'center'
                }
            }, item.icon);
            menuItem.appendChild(icon);
        }
        
        // Add text
        const text = DOMUtils.createElement('span', {}, item.text);
        menuItem.appendChild(text);
        
        // Add keyboard shortcut if provided
        if (item.shortcut) {
            const shortcut = DOMUtils.createElement('span', {
                style: {
                    marginLeft: 'auto',
                    fontSize: '0.75rem',
                    color: '#9ca3af'
                }
            }, item.shortcut);
            menuItem.appendChild(shortcut);
        }
        
        // Add hover effects
        menuItem.addEventListener('mouseenter', () => {
            menuItem.style.background = item.danger ? '#fef2f2' : '#f3f4f6';
            if (item.danger) {
                menuItem.style.color = '#dc2626';
            }
        });
        
        menuItem.addEventListener('mouseleave', () => {
            menuItem.style.background = '';
            menuItem.style.color = item.danger ? '#dc2626' : '#374151';
        });
        
        // Add click handler
        menuItem.addEventListener('click', (e) => {
            e.stopPropagation();
            if (item.action) {
                item.action();
            }
            this.hide();
        });
        
        // Disable if specified
        if (item.disabled) {
            menuItem.style.opacity = '0.5';
            menuItem.style.cursor = 'not-allowed';
            menuItem.style.pointerEvents = 'none';
        }
        
        return menuItem;
    }
    
    /**
     * Position menu within viewport
     */
    positionMenu(menu, x, y) {
        // Get menu dimensions
        menu.style.visibility = 'hidden';
        menu.style.display = 'block';
        const rect = menu.getBoundingClientRect();
        menu.style.display = 'none';
        menu.style.visibility = 'visible';
        
        // Calculate position
        let left = x;
        let top = y;
        
        // Ensure menu stays within viewport
        if (left + rect.width > window.innerWidth) {
            left = window.innerWidth - rect.width - 10;
        }
        
        if (top + rect.height > window.innerHeight) {
            top = window.innerHeight - rect.height - 10;
        }
        
        // Ensure menu doesn't go off-screen
        left = Math.max(10, left);
        top = Math.max(10, top);
        
        menu.style.left = `${left}px`;
        menu.style.top = `${top}px`;
    }
    
    /**
     * Show time block context menu
     */
    showTimeBlockMenu(timeBlock, event) {
        this.targetElement = timeBlock;
        
        const timeBlockData = this.app.components.timeBlock.getTimeBlockData(timeBlock);
        const isExistingEntry = timeBlockData.id && timeBlockData.id !== 'null';
        
        const menuItems = [
            {
                icon: '✏️',
                text: 'Edit Entry',
                shortcut: 'Double-click',
                action: () => {
                    this.app.components.modal.openEditModal(timeBlock);
                }
            },
            {
                icon: '📋',
                text: 'Copy Entry',
                shortcut: 'Ctrl+C',
                action: () => {
                    this.copyTimeBlock(timeBlock);
                }
            },
            {
                icon: '📄',
                text: 'Duplicate Entry',
                action: () => {
                    this.duplicateTimeBlock(timeBlock);
                }
            },
            { separator: true },
            {
                icon: '⏱️',
                text: 'Extend +30min',
                action: () => {
                    this.app.managers.timeBlock.adjustDuration(timeBlock, 0.5);
                }
            },
            {
                icon: '⏱️',
                text: 'Reduce -30min',
                action: () => {
                    this.app.managers.timeBlock.adjustDuration(timeBlock, -0.5);
                }
            },
            { separator: true },
            {
                icon: '◀️',
                text: 'Clone to Previous Day',
                action: () => {
                    this.app.managers.timeBlock.cloneTimeBlock(timeBlock, -1);
                }
            },
            {
                icon: '▶️',
                text: 'Clone to Next Day',
                action: () => {
                    this.app.managers.timeBlock.cloneTimeBlock(timeBlock, 1);
                }
            }
        ];
        
        // Add entry-specific options
        if (isExistingEntry) {
            menuItems.push({ separator: true });
            menuItems.push({
                icon: '🔗',
                text: 'Open in Frappe',
                action: () => {
                    window.open(`/app/timesheet-entry/${timeBlockData.id}`, '_blank');
                }
            });
        }
        
        // Add delete option
        menuItems.push({ separator: true });
        menuItems.push({
            icon: '🗑️',
            text: 'Delete Entry',
            shortcut: 'Del',
            danger: true,
            action: () => {
                this.app.managers.timeBlock.deleteTimeBlock(timeBlock);
            }
        });
        
        this.show(event.pageX, event.pageY, menuItems);
    }
    
    /**
     * Copy time block data to clipboard
     */
    copyTimeBlock(timeBlock) {
        const data = this.app.components.timeBlock.getTimeBlockData(timeBlock);
        const summary = this.app.components.timeBlock.getTimeBlockSummary(timeBlock);
        
        const textData = `${summary.project} - ${summary.activity}\n${summary.timeRange} (${summary.duration})\n${summary.date}`;
        
        if (navigator.clipboard) {
            navigator.clipboard.writeText(textData).then(() => {
                this.app.components.toast.success('Time entry copied to clipboard');
            }).catch(() => {
                this.fallbackCopyToClipboard(textData);
            });
        } else {
            this.fallbackCopyToClipboard(textData);
        }
        
        // Store in app state for potential paste operation
        this.app.setState({ copiedTimeBlock: data });
    }
    
    /**
     * Fallback copy to clipboard method
     */
    fallbackCopyToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            this.app.components.toast.success('Time entry copied to clipboard');
        } catch (err) {
            this.app.components.toast.error('Failed to copy to clipboard');
        }
        
        document.body.removeChild(textArea);
    }
    
    /**
     * Duplicate time block in same position
     */
    duplicateTimeBlock(timeBlock) {
        const data = this.app.components.timeBlock.getTimeBlockData(timeBlock);
        const dayColumn = timeBlock.closest('.day-column');
        
        // Find next available time slot
        let newStartHour = data.startHour;
        let newStartMinute = data.startMinute;
        let attempts = 0;
        const maxAttempts = 48; // 24 hours in 30-minute increments
        
        while (attempts < maxAttempts) {
            // Check if this time slot is available
            const hasOverlap = TimeUtils.checkTimeOverlap(
                dayColumn, 
                newStartHour, 
                newStartMinute, 
                data.duration
            );
            
            if (!hasOverlap) {
                // Found available slot
                const newTimeBlock = this.app.managers.timeBlock.createTimeBlock({
                    ...data,
                    id: null, // Remove ID for new entry
                    startHour: newStartHour,
                    startMinute: newStartMinute
                });
                
                if (newTimeBlock) {
                    this.app.selectTimeBlock(newTimeBlock);
                    this.app.components.toast.success('Time entry duplicated');
                    this.app.managers.storage.autoSave();
                }
                return;
            }
            
            // Move to next 30-minute slot
            newStartMinute += 30;
            if (newStartMinute >= 60) {
                newStartMinute = 0;
                newStartHour++;
                if (newStartHour >= 24) {
                    newStartHour = 0;
                }
            }
            
            attempts++;
        }
        
        this.app.components.toast.warning('No available time slots found for duplication');
    }
    
    /**
     * Show calendar context menu
     */
    showCalendarMenu(x, y) {
        const menuItems = [
            {
                icon: '📅',
                text: 'Go to Today',
                action: () => {
                    if (this.app.managers.mobile.navigateToToday()) {
                        this.app.components.toast.info('Navigated to today');
                    } else {
                        this.app.components.toast.info('Today is not in current week');
                    }
                }
            },
            {
                icon: '🔄',
                text: 'Refresh Calendar',
                action: () => {
                    window.location.reload();
                }
            },
            { separator: true },
            {
                icon: '📊',
                text: 'Week Summary',
                action: () => {
                    this.showWeekSummary();
                }
            },
            {
                icon: '📤',
                text: 'Export Week',
                action: () => {
                    this.app.managers.storage.exportData('csv', this.app.state.currentWeekStart);
                }
            }
        ];
        
        this.show(x, y, menuItems);
    }
    
    /**
     * Show week summary
     */
    showWeekSummary() {
        const summary = this.calculateWeekSummary();
        
        const content = `
            <div style="padding: 1rem;">
                <h4 style="margin: 0 0 1rem 0;">Week Summary</h4>
                <div style="display: grid; gap: 0.5rem;">
                    <div><strong>Total Hours:</strong> ${summary.totalHours}h</div>
                    <div><strong>Total Entries:</strong> ${summary.totalEntries}</div>
                    <div><strong>Projects:</strong> ${summary.uniqueProjects}</div>
                    <div><strong>Average per Day:</strong> ${summary.averagePerDay}h</div>
                </div>
                
                <h5 style="margin: 1rem 0 0.5rem 0;">By Project:</h5>
                <div style="display: grid; gap: 0.25rem; font-size: 0.875rem;">
                    ${summary.byProject.map(p => 
                        `<div>${p.name}: ${p.hours}h (${p.entries} entries)</div>`
                    ).join('')}
                </div>
            </div>
        `;
        
        this.app.components.modal.showCustomModal('Week Summary', content, [
            {
                text: 'Close',
                class: 'btn-secondary',
                handler: () => this.app.components.modal.hideCustomModal()
            }
        ]);
    }
    
    /**
     * Calculate week summary statistics
     */
    calculateWeekSummary() {
        const summary = {
            totalHours: 0,
            totalEntries: 0,
            uniqueProjects: new Set(),
            byProject: {},
            byDay: {}
        };
        
        this.app.state.timeBlocks.forEach(block => {
            const data = this.app.components.timeBlock.getTimeBlockData(block);
            const duration = parseFloat(data.duration);
            
            summary.totalHours += duration;
            summary.totalEntries++;
            summary.uniqueProjects.add(data.project);
            
            // By project
            if (!summary.byProject[data.project]) {
                summary.byProject[data.project] = {
                    name: data.projectName,
                    hours: 0,
                    entries: 0
                };
            }
            summary.byProject[data.project].hours += duration;
            summary.byProject[data.project].entries++;
            
            // By day
            if (!summary.byDay[data.date]) {
                summary.byDay[data.date] = 0;
            }
            summary.byDay[data.date] += duration;
        });
        
        // Calculate averages
        const workingDays = Object.keys(summary.byDay).length || 1;
        summary.averagePerDay = Math.round(summary.totalHours / workingDays * 10) / 10;
        summary.uniqueProjects = summary.uniqueProjects.size;
        
        // Convert byProject to array and sort
        summary.byProject = Object.values(summary.byProject)
            .sort((a, b) => b.hours - a.hours);
        
        // Round total hours
        summary.totalHours = Math.round(summary.totalHours * 10) / 10;
        
        return summary;
    }
}

// Export to global scope
window.ContextMenuComponent = ContextMenuComponent;

// Setup global functions for HTML compatibility
window.editFromContext = function() {
    if (window.app && window.app.components.contextMenu && window.app.components.contextMenu.targetElement) {
        window.app.components.modal.openEditModal(window.app.components.contextMenu.targetElement);
        window.app.components.contextMenu.hide();
    }
};

window.deleteFromContext = function() {
    if (window.app && window.app.components.contextMenu && window.app.components.contextMenu.targetElement) {
        window.app.managers.timeBlock.deleteTimeBlock(window.app.components.contextMenu.targetElement);
        window.app.components.contextMenu.hide();
    }
};
