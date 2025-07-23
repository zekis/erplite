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
        // Refresh data when page becomes visible again
        setTimeout(() => {
            window.todoKanban.refreshTodos();
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

// Card expand/collapse functionality
window.handleCardClick = function(event) {
    // Don't expand/collapse if clicking on interactive elements
    if (event.target.matches('select, input, button, .card-action-btn, .expand-btn, .collapse-btn')) {
        return;
    }
    
    const card = event.currentTarget;
    const isCollapsed = card.classList.contains('collapsed');
    
    if (isCollapsed) {
        expandCard(card);
    } else {
        collapseCard(card);
    }
};

function expandCard(card) {
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
}

function collapseCard(card) {
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

console.log('Todo Kanban initialization script loaded');
