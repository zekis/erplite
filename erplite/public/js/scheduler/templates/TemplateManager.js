/**
 * TemplateManager - Template system for the scheduler
 * Handles template configurations, validation, and application
 */
class TemplateManager {
    constructor(eventBus, stateManager) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.dataProcessor = null; // Will be injected
        
        // Template configurations
        this.templates = this.getDefaultTemplates();
        
        // Initialize drag and drop
        this.initializeTemplateDragDrop();
    }

    /**
     * Set data processor reference
     * @param {DataProcessor} dataProcessor - Data processor instance
     */
    setDataProcessor(dataProcessor) {
        this.dataProcessor = dataProcessor;
    }

    /**
     * Get default template configurations
     * @returns {Object} Template configurations
     */
    getDefaultTemplates() {
        return {
            '8h': {
                name: '8 Hour Shift',
                hours: 8,
                start_time: '09:00',
                end_time: '17:00',
                description: 'Standard 8-hour work day',
                status: 'planned',
                color: '#10b981',
                icon: 'mdi-clock-outline'
            },
            '12h': {
                name: '12 Hour Shift',
                hours: 12,
                start_time: '07:00',
                end_time: '19:00',
                description: 'Extended 12-hour shift',
                status: 'planned',
                color: '#f59e0b',
                icon: 'mdi-clock-outline'
            },
            'leave': {
                name: 'Leave',
                hours: 8,
                start_time: '00:00',
                end_time: '23:59',
                description: 'Time off / Leave',
                status: 'leave',
                color: '#ef4444',
                icon: 'mdi-beach'
            },
            '4h': {
                name: '4 Hour Shift',
                hours: 4,
                start_time: '09:00',
                end_time: '13:00',
                description: 'Half-day shift',
                status: 'planned',
                color: '#8b5cf6',
                icon: 'mdi-clock-outline'
            },
            'overtime': {
                name: 'Overtime',
                hours: 10,
                start_time: '08:00',
                end_time: '18:00',
                description: 'Overtime shift',
                status: 'planned',
                color: '#f97316',
                icon: 'mdi-clock-plus-outline'
            }
        };
    }

    /**
     * Get template configuration by ID
     * @param {string} templateId - Template ID
     * @returns {Object|null} Template configuration
     */
    getTemplate(templateId) {
        return this.templates[templateId] || null;
    }

    /**
     * Get all available templates
     * @returns {Object} All template configurations
     */
    getAllTemplates() {
        return { ...this.templates };
    }

    /**
     * Add custom template
     * @param {string} templateId - Template ID
     * @param {Object} config - Template configuration
     * @returns {boolean} Success status
     */
    addTemplate(templateId, config) {
        const validation = this.validateTemplateConfig(config);
        if (!validation.isValid) {
            console.error('[TemplateManager] Invalid template config:', validation.errors);
            return false;
        }

        this.templates[templateId] = { ...config };
        
        // Emit template added event
        this.eventBus.emit('template:added', {
            templateId,
            config: this.templates[templateId]
        });

        return true;
    }

    /**
     * Remove template
     * @param {string} templateId - Template ID to remove
     * @returns {boolean} Success status
     */
    removeTemplate(templateId) {
        if (!this.templates[templateId]) {
            return false;
        }

        delete this.templates[templateId];
        
        // Emit template removed event
        this.eventBus.emit('template:removed', { templateId });

        return true;
    }

    /**
     * Validate template configuration
     * @param {Object} config - Template configuration
     * @returns {Object} Validation result
     */
    validateTemplateConfig(config) {
        const errors = [];
        const warnings = [];

        // Required fields
        if (!config.name) {
            errors.push('Template name is required');
        }

        if (typeof config.hours !== 'number' || config.hours <= 0) {
            errors.push('Hours must be a positive number');
        }

        if (!config.start_time || !/^\d{2}:\d{2}$/.test(config.start_time)) {
            errors.push('Start time must be in HH:MM format');
        }

        if (!config.end_time || !/^\d{2}:\d{2}$/.test(config.end_time)) {
            errors.push('End time must be in HH:MM format');
        }

        // Optional field validation
        if (config.color && !window.SchedulerColorUtils.isValidColor(config.color)) {
            warnings.push('Invalid color format');
        }

        if (config.status && !['planned', 'in-progress', 'completed', 'cancelled', 'leave'].includes(config.status)) {
            warnings.push('Unknown status value');
        }

        return {
            isValid: errors.length === 0,
            errors,
            warnings
        };
    }

    /**
     * Apply template to a schedule row
     * @param {string} templateId - Template ID
     * @param {number} rowIndex - Row index
     * @param {string} date - Date to apply template
     * @returns {boolean} Success status
     */
    applyTemplate(templateId, rowIndex, date) {
        const template = this.getTemplate(templateId);
        if (!template) {
            console.error(`[TemplateManager] Template not found: ${templateId}`);
            return false;
        }

        const scheduleRows = this.stateManager.get('scheduleRows');
        const row = scheduleRows[rowIndex];

        if (!row || row.type !== 'task-row') {
            console.error('[TemplateManager] Invalid row for template application');
            return false;
        }

        if (!row.project || !row.task) {
            this.eventBus.emit('toast:show', {
                message: 'Please select project and task first',
                type: 'warning'
            });
            return false;
        }

        // Initialize dailyEntries if not exists
        if (!row.dailyEntries) {
            row.dailyEntries = {};
        }

        // Apply template to the date
        row.dailyEntries[date] = {
            hours: template.hours,
            start_time: template.start_time,
            end_time: template.end_time,
            description: template.description,
            status: template.status,
            id: this.dataProcessor ? this.dataProcessor.generateEntryId() : this.generateSimpleId()
        };

        // Update state
        this.stateManager.set('scheduleRows', scheduleRows);

        // Emit events
        this.eventBus.emit('template:applied', {
            templateId,
            rowIndex,
            date,
            template
        });

        this.eventBus.emit('toast:show', {
            message: `${template.name} template applied!`,
            type: 'success'
        });

        return true;
    }

    /**
     * Initialize drag and drop for template cards
     */
    initializeTemplateDragDrop() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.setupTemplateDragDrop();
            });
        } else {
            this.setupTemplateDragDrop();
        }
    }

    /**
     * Setup drag and drop event listeners for template cards
     */
    setupTemplateDragDrop() {
        const templateCards = document.querySelectorAll('.template-card');
        
        templateCards.forEach(card => {
            // Remove existing listeners to prevent duplicates
            card.removeEventListener('dragstart', this.handleDragStart);
            card.removeEventListener('dragend', this.handleDragEnd);
            
            // Add new listeners
            card.addEventListener('dragstart', this.handleDragStart.bind(this));
            card.addEventListener('dragend', this.handleDragEnd.bind(this));
        });

        console.log(`[TemplateManager] Initialized drag & drop for ${templateCards.length} template cards`);
    }

    /**
     * Handle drag start event
     * @param {Event} event - Drag start event
     */
    handleDragStart(event) {
        const templateId = event.target.dataset.template;
        
        if (!templateId) {
            console.error('[TemplateManager] No template ID found on drag element');
            return;
        }

        const template = this.getTemplate(templateId);
        if (!template) {
            console.error(`[TemplateManager] Template not found: ${templateId}`);
            return;
        }

        // Set drag data
        event.dataTransfer.setData('text/plain', JSON.stringify({
            type: 'template',
            templateId: templateId,
            template: template
        }));

        // Add dragging class for visual feedback
        event.target.classList.add('dragging');

        // Emit drag start event
        this.eventBus.emit('template:drag:start', {
            templateId,
            template,
            element: event.target
        });

        console.log(`[TemplateManager] Started dragging template: ${templateId}`);
    }

    /**
     * Handle drag end event
     * @param {Event} event - Drag end event
     */
    handleDragEnd(event) {
        // Remove dragging class
        event.target.classList.remove('dragging');

        const templateId = event.target.dataset.template;
        
        // Emit drag end event
        this.eventBus.emit('template:drag:end', {
            templateId,
            element: event.target
        });

        console.log(`[TemplateManager] Ended dragging template: ${templateId}`);
    }

    /**
     * Handle template drop on day cell
     * @param {string} templateId - Template ID
     * @param {number} rowIndex - Row index
     * @param {string} date - Target date
     * @returns {boolean} Success status
     */
    handleTemplateDrop(templateId, rowIndex, date) {
        console.log(`[TemplateManager] Handling template drop: ${templateId} on row ${rowIndex}, date ${date}`);
        
        return this.applyTemplate(templateId, rowIndex, date);
    }

    /**
     * Get template preview HTML
     * @param {string} templateId - Template ID
     * @returns {string} HTML string
     */
    getTemplatePreview(templateId) {
        const template = this.getTemplate(templateId);
        if (!template) {
            return '<div>Template not found</div>';
        }

        return `
            <div class="template-preview" style="border-left: 3px solid ${template.color}">
                <div class="template-name">${template.name}</div>
                <div class="template-hours">${template.hours}h</div>
                <div class="template-time">${template.start_time} - ${template.end_time}</div>
                <div class="template-description">${template.description}</div>
            </div>
        `;
    }

    /**
     * Export templates to JSON
     * @returns {string} JSON string of templates
     */
    exportTemplates() {
        return JSON.stringify(this.templates, null, 2);
    }

    /**
     * Import templates from JSON
     * @param {string} jsonString - JSON string of templates
     * @returns {Object} Import result
     */
    importTemplates(jsonString) {
        try {
            const importedTemplates = JSON.parse(jsonString);
            const results = {
                success: 0,
                failed: 0,
                errors: []
            };

            Object.keys(importedTemplates).forEach(templateId => {
                const config = importedTemplates[templateId];
                const validation = this.validateTemplateConfig(config);
                
                if (validation.isValid) {
                    this.templates[templateId] = config;
                    results.success++;
                } else {
                    results.failed++;
                    results.errors.push({
                        templateId,
                        errors: validation.errors
                    });
                }
            });

            // Emit import completed event
            this.eventBus.emit('templates:imported', results);

            return results;
        } catch (error) {
            return {
                success: 0,
                failed: 1,
                errors: ['Invalid JSON format']
            };
        }
    }

    /**
     * Generate simple ID (fallback when DataProcessor not available)
     * @returns {string} Simple ID
     */
    generateSimpleId() {
        return 'template_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Refresh template drag and drop (call after DOM changes)
     */
    refreshDragDrop() {
        this.setupTemplateDragDrop();
    }

    /**
     * Get template statistics
     * @returns {Object} Template usage statistics
     */
    getTemplateStats() {
        const scheduleRows = this.stateManager.get('scheduleRows');
        const stats = {};

        // Initialize stats for all templates
        Object.keys(this.templates).forEach(templateId => {
            stats[templateId] = {
                name: this.templates[templateId].name,
                usageCount: 0,
                totalHours: 0
            };
        });

        // Count usage in schedule rows
        scheduleRows.forEach(row => {
            if (row.type === 'task-row' && row.dailyEntries) {
                Object.values(row.dailyEntries).forEach(entry => {
                    // Try to match entry to template based on hours and times
                    Object.keys(this.templates).forEach(templateId => {
                        const template = this.templates[templateId];
                        if (entry.hours === template.hours &&
                            entry.start_time === template.start_time &&
                            entry.end_time === template.end_time) {
                            stats[templateId].usageCount++;
                            stats[templateId].totalHours += entry.hours;
                        }
                    });
                });
            }
        });

        return stats;
    }
}

// Export for use in other modules
window.SchedulerTemplateManager = TemplateManager;
