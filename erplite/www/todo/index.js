/**
 * Todo Kanban Application Initialization
 */
console.log('Initializing Todo Kanban application...');

// Load JavaScript files dynamically in correct order
async function loadTodoKanbanScripts() {
    const scripts = [
        `/assets/erplite/js/todo/utils/TodoUtils.js`,
        `/assets/erplite/js/todo/data/TodoDataManager.js`,
        `/assets/erplite/js/todo/rendering/TodoCardRenderer.js`,
        `/assets/erplite/js/todo/columns/TodoColumnManager.js`,
        `/assets/erplite/js/todo/dragdrop/TodoDragDropManager.js`,
        `/assets/erplite/js/todo/modals/TodoModalManager.js`,
        `/assets/erplite/js/todo/TodoKanbanApp.js`
    ];
    
    for (const scriptSrc of scripts) {
        await loadScript(scriptSrc);
    }
}

// Helper function to load a script and wait for it to complete
function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = () => {
            console.log(`Loaded: ${src}`);
            resolve();
        };
        script.onerror = () => {
            console.error(`Failed to load: ${src}`);
            reject(new Error(`Failed to load script: ${src}`));
        };
        document.head.appendChild(script);
    });
}

// Initialize todo kanban when page is ready
function startTodoKanbanInitialization() {
    console.log('Starting Todo Kanban initialization...');
    
    // Method 1: Try frappe.ready if available
    if (typeof frappe !== 'undefined' && frappe.ready) {
        console.log('Using frappe.ready()');
        frappe.ready(async function() {
            console.log('frappe.ready called, starting script loading...');
            await initializeTodoKanbanScripts();
        });
    } 
    // Method 2: Use document ready as fallback
    else if (document.readyState === 'loading') {
        console.log('Using document.addEventListener(DOMContentLoaded)');
        document.addEventListener('DOMContentLoaded', async function() {
            console.log('DOMContentLoaded fired, starting script loading...');
            await initializeTodoKanbanScripts();
        });
    } 
    // Method 3: Document is already ready
    else {
        console.log('Document already ready, starting immediately');
        setTimeout(async () => {
            await initializeTodoKanbanScripts();
        }, 100);
    }
}

async function initializeTodoKanbanScripts() {
    try {
        console.log('Loading Todo Kanban scripts...');
        await loadTodoKanbanScripts();
        console.log('All Todo Kanban scripts loaded, initializing...');
        initializeTodoKanban();
    } catch (error) {
        console.error('Failed to load Todo Kanban scripts:', error);
        showToast('Failed to load Todo Kanban components: ' + error.message, 'error');
    }
}

// Start initialization immediately
startTodoKanbanInitialization();

function initializeTodoKanban() {
    // Show loading overlay
    showLoading();
    
    try {
        // Debug: Check if TodoKanbanApp class is available
        console.log('Checking TodoKanbanApp class availability...');
        console.log('window.TodoKanbanApp:', window.TodoKanbanApp);
        console.log('typeof TodoKanbanApp:', typeof TodoKanbanApp);
        
        if (typeof TodoKanbanApp === 'undefined') {
            throw new Error('TodoKanbanApp class is not defined. Check if TodoKanbanApp.js is loaded properly.');
        }
        
        // Initialize the main todo kanban application
        console.log('Creating new TodoKanbanApp instance...');
        window.todoKanban = new TodoKanbanApp();
        
        // Hide loading overlay after initialization
        setTimeout(() => {
            hideLoading();
        }, 500);
        
        console.log('Todo Kanban application initialized successfully');
    } catch (error) {
        console.error('Failed to initialize Todo Kanban:', error);
        console.error('Error stack:', error.stack);
        hideLoading();
        showToast('Failed to initialize Todo Kanban: ' + error.message, 'error');
    }
}

// Utility functions
window.showLoading = function() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = 'flex';
    }
};

window.hideLoading = function() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
};

window.showToast = function(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <i class="toast-icon mdi ${getToastIcon(type)}"></i>
        <span class="toast-message">${message}</span>
        <i class="toast-close mdi mdi-close"></i>
    `;
    
    container.appendChild(toast);
    
    // Show toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Add close functionality
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
        hideToast(toast);
    });
    
    // Hide and remove toast after 5 seconds
    setTimeout(() => {
        hideToast(toast);
    }, 5000);
};

function getToastIcon(type) {
    switch (type) {
        case 'success': return 'mdi-check-circle';
        case 'error': return 'mdi-alert-circle';
        case 'warning': return 'mdi-alert';
        case 'info': 
        default: return 'mdi-information';
    }
}

function hideToast(toast) {
    toast.classList.remove('show');
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 300);
}

// Error handling
window.addEventListener('error', function(event) {
    console.error('Todo Kanban error:', event.error);
    showToast('An error occurred: ' + event.error.message, 'error');
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    showToast('An error occurred: ' + event.reason, 'error');
    event.preventDefault();
});

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Only handle shortcuts if todo kanban is initialized
    if (!window.todoKanban) return;
    
    // Ctrl/Cmd + N: New todo
    if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
        event.preventDefault();
        window.todoKanban.showAddTodoModal();
    }
    
    // Ctrl/Cmd + R: Refresh
    if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
        event.preventDefault();
        window.todoKanban.refreshTodos();
    }
    
    // Escape: Close modals
    if (event.key === 'Escape') {
        window.todoKanban.closeModals();
    }
});

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (!document.hidden && window.todoKanban) {
        // Only do quiet refresh when page becomes visible to avoid disrupting user interaction
        setTimeout(() => {
            window.todoKanban.quietRefresh();
        }, 1000);
    }
});

// Handle window resize
window.addEventListener('resize', function() {
    if (window.todoKanban && window.todoKanban.handleResize) {
        window.todoKanban.handleResize();
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.todoKanban && window.todoKanban.cleanup) {
        window.todoKanban.cleanup();
    }
});

// Enhanced drag and drop handlers - delegating to drag drop manager but keeping simple pattern
let draggedCard = null;

// Card expand/collapse functionality - only handle button clicks, not general card clicks
window.handleCardClick = function(event) {
    // Do nothing - we only want expand/collapse to happen via the specific buttons
    // This prevents accidental toggling when editing text or interacting with other elements
    return;
};

function expandCard(card) {
    const todoId = card.getAttribute('data-todo-id');
    
    card.classList.remove('collapsed');
    card.classList.add('expanded');
    
    // Update expand button to collapse button
    const expandBtn = card.querySelector('.expand-btn');
    if (expandBtn) {
        expandBtn.innerHTML = '<i class="mdi mdi-chevron-up"></i>';
        expandBtn.title = 'Collapse card';
        expandBtn.classList.remove('expand-btn');
        expandBtn.classList.add('collapse-btn');
    }
    
    // Notify column manager to save the expanded state
    if (window.todoKanban && window.todoKanban.columnManager) {
        window.todoKanban.columnManager.toggleCard(todoId, true);
    }
}

function collapseCard(card) {
    const todoId = card.getAttribute('data-todo-id');
    
    card.classList.remove('expanded');
    card.classList.add('collapsed');
    
    // Update collapse button to expand button
    const collapseBtn = card.querySelector('.collapse-btn');
    if (collapseBtn) {
        collapseBtn.innerHTML = '<i class="mdi mdi-chevron-down"></i>';
        collapseBtn.title = 'Expand card';
        collapseBtn.classList.remove('collapse-btn');
        collapseBtn.classList.add('expand-btn');
    }
    
    // Notify column manager to save the collapsed state
    if (window.todoKanban && window.todoKanban.columnManager) {
        window.todoKanban.columnManager.toggleCard(todoId, false);
    }
}

// Handle expand/collapse button clicks
window.addEventListener('click', function(event) {
    if (event.target.closest('.expand-btn')) {
        event.stopPropagation();
        const card = event.target.closest('.todo-card');
        if (card) {
            expandCard(card);
        }
    } else if (event.target.closest('.collapse-btn')) {
        event.stopPropagation();
        const card = event.target.closest('.todo-card');
        if (card) {
            collapseCard(card);
        }
    } else if (event.target.closest('#toggleAllCardsBtn')) {
        event.stopPropagation();
        toggleAllCards();
    } else if (event.target.closest('.column-collapse-btn')) {
        event.stopPropagation();
        const columnId = event.target.closest('.column-collapse-btn').getAttribute('data-column');
        toggleColumn(columnId);
    }
});

// Global toggle state for all cards
let allCardsExpanded = false;

// Toggle all cards expanded/collapsed
function toggleAllCards() {
    const toggleBtn = document.getElementById('toggleAllCardsBtn');
    const allCards = document.querySelectorAll('.todo-card');
    
    if (!allCards.length) {
        showToast('No cards to toggle', 'info');
        return;
    }
    
    // Determine if we should expand all or collapse all
    // If any cards are collapsed, expand all. If all are expanded, collapse all.
    const collapsedCards = document.querySelectorAll('.todo-card.collapsed');
    const shouldExpandAll = collapsedCards.length > 0;
    
    allCards.forEach(card => {
        if (shouldExpandAll) {
            expandCard(card);
        } else {
            collapseCard(card);
        }
    });
    
    // Update button text and icon
    allCardsExpanded = shouldExpandAll;
    if (allCardsExpanded) {
        toggleBtn.innerHTML = '<i class="mdi mdi-unfold-less-horizontal"></i> Collapse All';
        toggleBtn.title = 'Collapse all cards';
        showToast('All cards expanded', 'success');
    } else {
        toggleBtn.innerHTML = '<i class="mdi mdi-unfold-more-horizontal"></i> Expand All';
        toggleBtn.title = 'Expand all cards';
        showToast('All cards collapsed', 'success');
    }
}

// Column collapse/expand functionality
function toggleColumn(columnId) {
    const column = document.querySelector(`.kanban-column[data-column="${columnId}"]`);
    const collapseBtn = column.querySelector('.column-collapse-btn');
    
    if (!column) return;
    
    const isCollapsed = column.classList.contains('collapsed');
    
    if (isCollapsed) {
        // Expand column
        column.classList.remove('collapsed');
        collapseBtn.innerHTML = '<i class="mdi mdi-chevron-left"></i>';
        collapseBtn.title = 'Collapse column';
        showToast(`${getColumnDisplayName(columnId)} column expanded`, 'success');
    } else {
        // Collapse column
        column.classList.add('collapsed');
        collapseBtn.innerHTML = '<i class="mdi mdi-chevron-right"></i>';
        collapseBtn.title = 'Expand column';
        showToast(`${getColumnDisplayName(columnId)} column collapsed`, 'success');
    }
}

// Add keyboard shortcut for column toggling
document.addEventListener('keydown', function(event) {
    // Only handle shortcuts if todo kanban is initialized
    if (!window.todoKanban) return;
    
    // Ctrl/Cmd + 1-3: Toggle specific columns
    if ((event.ctrlKey || event.metaKey)) {
        const columnMap = {
            '1': 'backlog',
            '2': 'todo', 
            '3': 'progress'
        };
        
        if (columnMap[event.key]) {
            event.preventDefault();
            toggleColumn(columnMap[event.key]);
        }
    }
});

window.handleCardDragStart = function(event) {
    console.log('🚀 DRAG START - Enhanced handler');
    draggedCard = event.target;
    
    // Try to use drag drop manager if available, otherwise fallback to simple
    if (window.todoKanban && window.todoKanban.dragDropManager && window.todoKanban.dragDropManager.handleSimpleDragStart) {
        window.todoKanban.dragDropManager.handleSimpleDragStart(event);
    } else {
        // Fallback to simple implementation
        event.target.style.opacity = '0.5';
        event.dataTransfer.setData('text/plain', event.target.getAttribute('data-todo-id') || 'unknown');
        event.dataTransfer.effectAllowed = 'move';
    }
};

window.handleCardDragEnd = function(event) {
    console.log('🏁 DRAG END - Enhanced handler');
    
    // Try to use drag drop manager if available, otherwise fallback to simple
    if (window.todoKanban && window.todoKanban.dragDropManager && window.todoKanban.dragDropManager.handleSimpleDragEnd) {
        window.todoKanban.dragDropManager.handleSimpleDragEnd(event);
    } else {
        // Fallback to simple implementation
        event.target.style.opacity = '1';
        document.querySelectorAll('.column-body').forEach(col => {
            col.style.backgroundColor = '';
        });
    }
    
    draggedCard = null;
};

window.handleColumnDragOver = function(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    
    // Debug the drag drop manager availability
    console.log('🔍 DEBUG handleColumnDragOver:');
    console.log('  - window.todoKanban:', !!window.todoKanban);
    console.log('  - window.todoKanban.dragDropManager:', !!window.todoKanban?.dragDropManager);
    console.log('  - handleSimpleDragOver method:', !!window.todoKanban?.dragDropManager?.handleSimpleDragOver);
    
    if (window.todoKanban?.dragDropManager?.handleSimpleDragOver) {
        console.log('  - Calling handleSimpleDragOver');
        try {
            window.todoKanban.dragDropManager.handleSimpleDragOver(event);
            console.log('  - handleSimpleDragOver called successfully');
        } catch (error) {
            console.error('  - Error calling handleSimpleDragOver:', error);
        }
    } else {
        console.log('  - handleSimpleDragOver not available, using fallback');
    }
};

window.handleColumnDragEnter = function(event) {
    event.preventDefault();
    
    // Try to use drag drop manager if available, otherwise fallback to simple
    if (window.todoKanban && window.todoKanban.dragDropManager && window.todoKanban.dragDropManager.handleSimpleDragEnter) {
        window.todoKanban.dragDropManager.handleSimpleDragEnter(event);
    } else {
        // Fallback to simple implementation
        event.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
    }
};

window.handleColumnDragLeave = function(event) {
    // Try to use drag drop manager if available, otherwise fallback to simple
    if (window.todoKanban && window.todoKanban.dragDropManager && window.todoKanban.dragDropManager.handleSimpleDragLeave) {
        window.todoKanban.dragDropManager.handleSimpleDragLeave(event);
    } else {
        // Fallback to simple implementation
        if (!event.currentTarget.contains(event.relatedTarget)) {
            event.currentTarget.style.backgroundColor = '';
        }
    }
};

window.handleColumnDrop = function(event, columnId) {
    console.log('🎯 DROP - Enhanced handler for column:', columnId);
    event.preventDefault();
    event.currentTarget.style.backgroundColor = '';
    
    // Try to use drag drop manager if available, otherwise fallback to simple
    if (window.todoKanban && window.todoKanban.dragDropManager && window.todoKanban.dragDropManager.handleSimpleDrop) {
        window.todoKanban.dragDropManager.handleSimpleDrop(event, columnId, draggedCard);
    } else {
        // Fallback to simple implementation
        if (draggedCard) {
            const targetColumn = document.getElementById(columnId + '-body');
            if (targetColumn) {
                targetColumn.appendChild(draggedCard);
                console.log('✅ Card moved successfully to', columnId);
                updateColumnCounts();
                showToast(`Moved to ${getColumnDisplayName(columnId)}`, 'success');
            }
        }
    }
};

// Helper functions
function updateColumnCounts() {
    ['backlog', 'todo', 'progress'].forEach(columnId => {
        const columnBody = document.getElementById(columnId + '-body');
        const countElement = document.getElementById(columnId + '-count');
        
        if (columnBody && countElement) {
            const cardCount = columnBody.querySelectorAll('.todo-card').length;
            countElement.textContent = cardCount;
            
            // Hide/show placeholder based on card count
            const placeholder = columnBody.querySelector('.empty-state, .no-activitys-message');
            if (placeholder) {
                placeholder.style.display = cardCount > 0 ? 'none' : 'block';
            }
        }
    });
}

function getColumnDisplayName(columnId) {
    const names = {
        backlog: 'Backlog',
        todo: 'To Do',
        progress: 'In Progress'
    };
    return names[columnId] || columnId;
}

// Helper function to parse date from "Aug 07, 2025" to "2025-08-07" format (local time)
function parseToStandardDate(dateString) {
    if (!dateString) return null;
    
    try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return null;
        
        // Use local date to avoid timezone issues
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        
        return `${year}-${month}-${day}`; // Returns YYYY-MM-DD in local time
    } catch (e) {
        return null;
    }
}

// Daily metrics functionality - now using server-side API
async function updateDailyMetrics() {
    try {
        console.log('Fetching daily metrics from server...');
        
        // Get CSRF token from multiple possible sources
        let csrfToken = '';
        if (typeof frappe !== 'undefined' && frappe.csrf_token) {
            csrfToken = frappe.csrf_token;
        } else if (window.csrf_token) {
            csrfToken = window.csrf_token;
        } else {
            // Try to get from meta tag
            const metaToken = document.querySelector('meta[name="csrf-token"]');
            if (metaToken) {
                csrfToken = metaToken.getAttribute('content');
            }
        }
        
        console.log('Using CSRF token:', csrfToken ? 'Found' : 'Not found');
        
        // Call the server-side API
        const response = await fetch('/api/method/erplite.www.todo.index.get_daily_metrics', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': csrfToken
            }
        });
        
        const data = await response.json();
        
        if (data.message && data.message.success) {
            const metrics = data.message.metrics;
            console.log('Server metrics received:', metrics);
            console.log('Server debug info:', data.message.debug);
            
            // Update the DOM
            const metricElements = {
                created: document.getElementById('metric-created'),
                completed: document.getElementById('metric-completed'),
                cancelled: document.getElementById('metric-cancelled'),
                active: document.getElementById('metric-active')
            };
            
            Object.keys(metrics).forEach(key => {
                if (metricElements[key]) {
                    metricElements[key].textContent = metrics[key];
                }
            });
            
            return metrics;
        } else {
            console.error('Server returned error:', data.message?.message || 'Unknown error');
            throw new Error(data.message?.message || 'Failed to get metrics from server');
        }
        
    } catch (error) {
        console.error('Error fetching daily metrics:', error);
        
        // Fallback to DOM counting if API fails
        const todoCards = document.querySelectorAll('.todo-card');
        const fallbackMetrics = {
            created: 0,
            completed: 0, 
            cancelled: 0,
            active: todoCards.length
        };
        
        // Update DOM with fallback values
        const metricElements = {
            created: document.getElementById('metric-created'),
            completed: document.getElementById('metric-completed'),
            cancelled: document.getElementById('metric-cancelled'),
            active: document.getElementById('metric-active')
        };
        
        Object.keys(fallbackMetrics).forEach(key => {
            if (metricElements[key]) {
                metricElements[key].textContent = fallbackMetrics[key];
            }
        });
        
        showToast('Failed to load metrics from server, using fallback', 'warning');
        return fallbackMetrics;
    }
}

// Initialize metrics when page loads
function initializeDailyMetrics() {
    // Wait for DOM to be ready and data to be available
    setTimeout(() => {
        updateDailyMetrics();
    }, 1000);
}

// Hook into todo operations to update metrics
window.addEventListener('todoCreated', updateDailyMetrics);
window.addEventListener('todoCompleted', updateDailyMetrics);
window.addEventListener('todoCancelled', updateDailyMetrics);
window.addEventListener('todoDeleted', updateDailyMetrics);

// Also update metrics when todos are refreshed
window.addEventListener('todosRefreshed', updateDailyMetrics);

// Initialize metrics after page load
document.addEventListener('DOMContentLoaded', initializeDailyMetrics);

// Also initialize if DOM is already ready
if (document.readyState === 'complete' || document.readyState === 'interactive') {
    initializeDailyMetrics();
}

console.log('Todo Kanban initialization script loaded');
