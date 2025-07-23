/**
 * Todo Kanban Utility Functions
 */

class TodoUtils {
    /**
     * Generate a random color for user avatars
     */
    static generateUserColor(userId) {
        const colors = [
            '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
            '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1'
        ];
        
        // Use user ID to consistently generate the same color
        let hash = 0;
        for (let i = 0; i < userId.length; i++) {
            hash = userId.charCodeAt(i) + ((hash << 5) - hash);
        }
        
        return colors[Math.abs(hash) % colors.length];
    }
    
    /**
     * Get user initials from full name
     */
    static getUserInitials(fullName) {
        if (!fullName) return '?';
        
        const parts = fullName.trim().split(' ');
        if (parts.length >= 2) {
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        } else {
            return parts[0].substring(0, 2).toUpperCase();
        }
    }
    
    /**
     * Format relative date
     */
    static formatRelativeDate(dateString) {
        if (!dateString) return null;
        
        const date = new Date(dateString);
        const today = new Date();
        const diffTime = date - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            return { text: 'Today', class: 'today' };
        } else if (diffDays === 1) {
            return { text: 'Tomorrow', class: 'upcoming' };
        } else if (diffDays === -1) {
            return { text: 'Yesterday', class: 'overdue' };
        } else if (diffDays > 1) {
            return { text: `In ${diffDays} days`, class: 'upcoming' };
        } else {
            return { text: `${Math.abs(diffDays)} days ago`, class: 'overdue' };
        }
    }
    
    /**
     * Format date for display
     */
    static formatDate(dateString, format = 'MMM dd') {
        if (!dateString) return '';
        
        const date = new Date(dateString);
        const options = {};
        
        if (format === 'MMM dd') {
            options.month = 'short';
            options.day = 'numeric';
        } else if (format === 'full') {
            options.year = 'numeric';
            options.month = 'long';
            options.day = 'numeric';
        }
        
        return date.toLocaleDateString('en-US', options);
    }
    
    /**
     * Truncate text with ellipsis
     */
    static truncateText(text, maxLength = 100) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength).trim() + '...';
    }
    
    /**
     * Sanitize HTML content
     */
    static sanitizeHtml(html) {
        const div = document.createElement('div');
        div.textContent = html;
        return div.innerHTML;
    }
    
    /**
     * Get priority class name
     */
    static getPriorityClass(priority) {
        if (!priority) return 'medium';
        return priority.toLowerCase();
    }
    
    /**
     * Get priority color
     */
    static getPriorityColor(priority) {
        const colors = {
            'high': '#ef4444',
            'medium': '#f59e0b',
            'low': '#10b981'
        };
        return colors[priority?.toLowerCase()] || colors.medium;
    }
    
    /**
     * Get the column for a todo based on its status
     */
    static getTodoColumn(todo) {
        if (!todo) {
            return null;
        }
        
        // Only show Open, Backlog, and Planned todos on the kanban board
        if (!['Open', 'Backlog', 'Planned'].includes(todo.status)) {
            return null; // Don't show closed/cancelled todos
        }
        
        // Map status to columns
        const statusToColumn = {
            'Backlog': 'backlog',
            'Planned': 'todo', 
            'Open': 'progress'
        };
        
        return statusToColumn[todo.status] || 'backlog';
    }
    
    /**
     * Debounce function calls
     */
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Throttle function calls
     */
    static throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
    
    /**
     * Deep clone an object
     */
    static deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj.getTime());
        if (obj instanceof Array) return obj.map(item => TodoUtils.deepClone(item));
        if (typeof obj === 'object') {
            const clonedObj = {};
            for (const key in obj) {
                if (obj.hasOwnProperty(key)) {
                    clonedObj[key] = TodoUtils.deepClone(obj[key]);
                }
            }
            return clonedObj;
        }
    }
    
    /**
     * Generate unique ID
     */
    static generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
    
    /**
     * Check if user is manager
     */
    static isManager() {
        return window.todoKanbanData?.isManager || false;
    }
    
    /**
     * Get current user
     */
    static getCurrentUser() {
        return window.todoKanbanData?.currentUser || null;
    }
    
    /**
     * Get all users
     */
    static getUsers() {
        return window.todoKanbanData?.users || [];
    }
    
    /**
     * Find user by ID
     */
    static findUser(userId) {
        const users = TodoUtils.getUsers();
        return users.find(user => user.name === userId);
    }
    
    /**
     * Check if element is in viewport
     */
    static isInViewport(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }
    
    /**
     * Smooth scroll to element
     */
    static scrollToElement(element, offset = 0) {
        const elementPosition = element.getBoundingClientRect().top;
        const offsetPosition = elementPosition + window.pageYOffset - offset;
        
        window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
        });
    }
    
    /**
     * Get element position relative to container
     */
    static getElementPosition(element, container) {
        const elementRect = element.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        
        return {
            x: elementRect.left - containerRect.left,
            y: elementRect.top - containerRect.top,
            width: elementRect.width,
            height: elementRect.height
        };
    }
    
    /**
     * Check if point is inside element
     */
    static isPointInElement(x, y, element) {
        const rect = element.getBoundingClientRect();
        return (
            x >= rect.left &&
            x <= rect.right &&
            y >= rect.top &&
            y <= rect.bottom
        );
    }
    
    /**
     * Format file size
     */
    static formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    /**
     * Validate email address
     */
    static isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
    
    /**
     * Escape HTML entities
     */
    static escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
    
    /**
     * Parse query string
     */
    static parseQueryString(queryString) {
        const params = {};
        const pairs = (queryString || window.location.search.slice(1)).split('&');
        
        for (let pair of pairs) {
            const [key, value] = pair.split('=');
            if (key) {
                params[decodeURIComponent(key)] = decodeURIComponent(value || '');
            }
        }
        
        return params;
    }
    
    /**
     * Build query string from object
     */
    static buildQueryString(params) {
        return Object.keys(params)
            .filter(key => params[key] !== null && params[key] !== undefined)
            .map(key => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
            .join('&');
    }
}

// Make TodoUtils available globally
window.TodoUtils = TodoUtils;
