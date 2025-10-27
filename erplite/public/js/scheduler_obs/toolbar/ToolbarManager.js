/**
 * Toolbar Manager
 * Handles all toolbar functionality including navigation, templates, and actions
 */
class ToolbarManager {
    constructor(app) {
        this.app = app;
        this.templateCards = [];
        this.navigationButtons = {};
        this.actionButtons = {};
        this.dateDisplay = null;
    }

    /**
     * Initialize toolbar functionality
     */
    init() {
        this.initializeTemplateCards();
        this.initializeNavigationButtons();
        this.initializeActionButtons();
        this.initializeDateDisplay();
        
        console.log('ToolbarManager initialized');
    }

    /**
     * Initialize template cards with drag and drop
     */
    initializeTemplateCards() {
        const templateCards = document.querySelectorAll('.template-card');
        
        templateCards.forEach(card => {
            // Store reference
            this.templateCards.push({
                element: card,
                template: card.dataset.template
            });
            
            // Add drag event listeners
            card.addEventListener('dragstart', (e) => this.handleTemplateDragStart(e, card));
            card.addEventListener('dragend', (e) => this.handleTemplateDragEnd(e, card));
            
            // Add click handler for mobile/touch devices
            card.addEventListener('click', (e) => this.handleTemplateClick(e, card));
        });
        
        console.log(`Initialized ${templateCards.length} template cards`);
    }

    /**
     * Initialize navigation buttons
     */
    initializeNavigationButtons() {
        // Find navigation buttons
        const navButtons = document.querySelectorAll('.nav-btn');
        
        navButtons.forEach(button => {
            const onClick = button.getAttribute('onclick');
            if (onClick) {
                // Extract the days parameter from onclick
                const match = onClick.match(/navigateDate\((-?\d+)\)/);
                if (match) {
                    const days = parseInt(match[1]);
                    
                    // Store reference
                    this.navigationButtons[days] = button;
                    
                    // Replace onclick with proper event listener
                    button.removeAttribute('onclick');
                    button.addEventListener('click', () => this.navigateDate(days));
                    
                    // Add keyboard support
                    button.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            this.navigateDate(days);
                        }
                    });
                }
            }
        });
        
        console.log(`Initialized ${Object.keys(this.navigationButtons).length} navigation buttons`);
    }

    /**
     * Initialize action buttons (refresh, export, etc.)
     */
    initializeActionButtons() {
        // Refresh button
        const refreshBtn = document.querySelector('button[onclick="refreshData()"]');
        if (refreshBtn) {
            this.actionButtons.refresh = refreshBtn;
            refreshBtn.removeAttribute('onclick');
            refreshBtn.addEventListener('click', () => this.refreshData());
            
            // Add loading state support
            refreshBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.refreshData();
                }
            });
        }
        
        // Export button
        const exportBtn = document.querySelector('button[onclick="exportSchedule()"]');
        if (exportBtn) {
            this.actionButtons.export = exportBtn;
            exportBtn.removeAttribute('onclick');
            exportBtn.addEventListener('click', () => this.exportSchedule());
            
            exportBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.exportSchedule();
                }
            });
        }
        
        // Add Row button
        const addRowBtn = document.querySelector('button[onclick="addNewRow()"]');
        if (addRowBtn) {
            this.actionButtons.addRow = addRowBtn;
            addRowBtn.removeAttribute('onclick');
            addRowBtn.addEventListener('click', () => this.addNewRow());
            
            addRowBtn.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.addNewRow();
                }
            });
        }
        
        console.log(`Initialized ${Object.keys(this.actionButtons).length} action buttons`);
    }

    /**
     * Initialize date display
     */
    initializeDateDisplay() {
        this.dateDisplay = document.getElementById('dateRangeDisplay');
        if (this.dateDisplay) {
            console.log('Date display initialized');
        }
    }

    /**
     * Handle template drag start
     */
    handleTemplateDragStart(event, card) {
        const template = card.dataset.template;
        
        // Set drag data
        event.dataTransfer.setData('text/plain', JSON.stringify({
            type: 'template',
            template: template
        }));
        
        // Add dragging visual state
        card.classList.add('dragging');
        
        // Add drag image customization
        const dragImage = card.cloneNode(true);
        dragImage.style.transform = 'rotate(5deg)';
        dragImage.style.opacity = '0.8';
        document.body.appendChild(dragImage);
        event.dataTransfer.setDragImage(dragImage, 20, 20);
        
        // Clean up drag image after drag starts
        setTimeout(() => {
            if (document.body.contains(dragImage)) {
                document.body.removeChild(dragImage);
            }
        }, 0);
        
        console.log(`Started dragging template: ${template}`);
    }

    /**
     * Handle template drag end
     */
    handleTemplateDragEnd(event, card) {
        // Remove dragging visual state
        card.classList.remove('dragging');
        
        console.log('Template drag ended');
    }

    /**
     * Handle template click (for mobile/touch devices)
     */
    handleTemplateClick(event, card) {
        const template = card.dataset.template;
        
        // Show template info or provide alternative interaction
        const templateConfig = this.getTemplateConfig(template);
        
        // Add visual feedback
        card.classList.add('clicked');
        setTimeout(() => card.classList.remove('clicked'), 200);
        
        // Show tooltip or info
        this.showTemplateInfo(card, templateConfig);
        
        console.log(`Template clicked: ${template}`);
    }

    /**
     * Show template information
     */
    showTemplateInfo(card, config) {
        // Create temporary tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'template-tooltip';
        tooltip.innerHTML = `
            <div class="tooltip-title">${config.name}</div>
            <div class="tooltip-details">
                <div>${config.hours} hours</div>
                <div>${config.start_time} - ${config.end_time}</div>
            </div>
            <div class="tooltip-instruction">Drag to schedule cells</div>
        `;
        
        // Position tooltip
        const rect = card.getBoundingClientRect();
        tooltip.style.position = 'fixed';
        tooltip.style.top = `${rect.bottom + 10}px`;
        tooltip.style.left = `${rect.left}px`;
        tooltip.style.zIndex = '10001';
        
        document.body.appendChild(tooltip);
        
        // Remove tooltip after delay
        setTimeout(() => {
            if (document.body.contains(tooltip)) {
                document.body.removeChild(tooltip);
            }
        }, 3000);
    }

    /**
     * Get template configuration - delegates to SchedulerUtils
     */
    getTemplateConfig(template) {
        return SchedulerUtils.getTemplateConfig(template);
    }

    /**
     * Navigate date range
     */
    navigateDate(days) {
        // Add loading state to navigation button
        const button = this.navigationButtons[days];
        if (button) {
            button.classList.add('loading');
            button.disabled = true;
        }
        
        // Calculate new date
        const newDate = SchedulerUtils.addDays(this.app.state.currentStartDate, days);
        this.app.state.currentStartDate = newDate;
        
        // Load new data
        this.app.loadSchedulerData().finally(() => {
            // Remove loading state
            if (button) {
                button.classList.remove('loading');
                button.disabled = false;
            }
        });
        
        // Update date display immediately for better UX
        this.updateDateDisplay();
        
        console.log(`Navigated ${days} days to ${newDate}`);
    }

    /**
     * Update date range display
     */
    updateDateDisplay() {
        if (!this.dateDisplay) return;
        
        const startDate = new Date(this.app.state.currentStartDate);
        const endDate = SchedulerUtils.addDays(this.app.state.currentStartDate, this.app.state.dateRange - 1);
        
        const formatDate = (date) => {
            return new Date(date).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric',
                year: 'numeric'
            });
        };
        
        this.dateDisplay.textContent = `${formatDate(startDate)} - ${formatDate(endDate)}`;
    }

    /**
     * Refresh data
     */
    refreshData() {
        const button = this.actionButtons.refresh;
        
        // Add loading state
        if (button) {
            button.classList.add('loading');
            button.disabled = true;
            
            // Update button text/icon
            const icon = button.querySelector('i');
            if (icon) {
                icon.classList.remove('mdi-refresh');
                icon.classList.add('mdi-loading', 'mdi-spin');
            }
        }
        
        // Reload data
        this.app.loadSchedulerData().finally(() => {
            // Remove loading state
            if (button) {
                button.classList.remove('loading');
                button.disabled = false;
                
                // Restore button icon
                const icon = button.querySelector('i');
                if (icon) {
                    icon.classList.remove('mdi-loading', 'mdi-spin');
                    icon.classList.add('mdi-refresh');
                }
            }
        });
        
        console.log('Refreshing scheduler data');
    }

    /**
     * Export schedule
     */
    exportSchedule() {
        const button = this.actionButtons.export;
        
        // Add loading state
        if (button) {
            button.classList.add('loading');
            button.disabled = true;
        }
        
        // Simulate export process (replace with actual export logic)
        setTimeout(() => {
            this.app.showToast('Export functionality coming soon!', 'info');
            
            // Remove loading state
            if (button) {
                button.classList.remove('loading');
                button.disabled = false;
            }
        }, 1000);
        
        console.log('Exporting schedule');
    }

    /**
     * Add new row
     */
    addNewRow() {
        const button = this.actionButtons.addRow;
        
        // Add visual feedback
        if (button) {
            button.classList.add('clicked');
            setTimeout(() => button.classList.remove('clicked'), 200);
        }
        
        // Add new row to scheduler
        this.app.addNewRow();
        
        console.log('Added new row');
    }

    /**
     * Set loading state for all toolbar elements
     */
    setLoading(loading) {
        // Disable/enable all interactive elements
        this.templateCards.forEach(card => {
            card.element.style.pointerEvents = loading ? 'none' : '';
            card.element.style.opacity = loading ? '0.6' : '';
        });
        
        Object.values(this.navigationButtons).forEach(button => {
            button.disabled = loading;
        });
        
        Object.values(this.actionButtons).forEach(button => {
            button.disabled = loading;
        });
        
        console.log(`Toolbar loading state: ${loading}`);
    }

    /**
     * Update toolbar state based on scheduler state
     */
    updateToolbarState() {
        // Update date display
        this.updateDateDisplay();
        
        // Update navigation button states based on data availability
        const hasData = this.app.state.scheduleRows.length > 0;
        
        Object.values(this.navigationButtons).forEach(button => {
            button.style.opacity = hasData ? '' : '0.6';
        });
        
        // Update export button state
        if (this.actionButtons.export) {
            this.actionButtons.export.disabled = !hasData;
            this.actionButtons.export.style.opacity = hasData ? '' : '0.6';
        }
    }

    /**
     * Add keyboard shortcuts
     */
    initializeKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Only handle shortcuts when not in input fields
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            // Navigation shortcuts
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 'ArrowLeft':
                        e.preventDefault();
                        this.navigateDate(-7);
                        break;
                    case 'ArrowRight':
                        e.preventDefault();
                        this.navigateDate(7);
                        break;
                    case 'r':
                        e.preventDefault();
                        this.refreshData();
                        break;
                    case 'e':
                        e.preventDefault();
                        this.exportSchedule();
                        break;
                    case 'n':
                        e.preventDefault();
                        this.addNewRow();
                        break;
                }
            }
        });
        
        console.log('Keyboard shortcuts initialized');
    }

    /**
     * Cleanup
     */
    cleanup() {
        // Remove event listeners
        this.templateCards.forEach(card => {
            const element = card.element;
            element.removeEventListener('dragstart', this.handleTemplateDragStart);
            element.removeEventListener('dragend', this.handleTemplateDragEnd);
            element.removeEventListener('click', this.handleTemplateClick);
        });
        
        // Clear references
        this.templateCards = [];
        this.navigationButtons = {};
        this.actionButtons = {};
        this.dateDisplay = null;
        
        console.log('ToolbarManager cleanup completed');
    }
}

// Export to global scope for HTML compatibility
window.ToolbarManager = ToolbarManager;
