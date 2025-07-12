/**
 * Toast notification component for user feedback
 */
class ToastComponent {
    constructor(app) {
        this.app = app;
        this.activeToasts = [];
        this.maxToasts = 3;
    }
    
    /**
     * Show a toast notification
     */
    show(message, type = 'success', duration = 3000) {
        // Remove oldest toast if we have too many
        if (this.activeToasts.length >= this.maxToasts) {
            this.removeToast(this.activeToasts[0]);
        }
        
        // Create toast element
        const toast = this.createToastElement(message, type);
        
        // Add to page
        document.body.appendChild(toast);
        this.activeToasts.push(toast);
        
        // Show toast with animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Auto-hide toast after duration
        setTimeout(() => {
            this.removeToast(toast);
        }, duration);
        
        return toast;
    }
    
    /**
     * Create toast DOM element
     */
    createToastElement(message, type) {
        const toast = DOMUtils.createElement('div', {
            className: `toast-notification toast-${type}`
        }, message);
        
        // Add click to dismiss
        toast.addEventListener('click', () => {
            this.removeToast(toast);
        });
        
        return toast;
    }
    
    /**
     * Remove a toast notification
     */
    removeToast(toast) {
        if (!toast || !toast.parentNode) return;
        
        // Remove from active toasts array
        const index = this.activeToasts.indexOf(toast);
        if (index > -1) {
            this.activeToasts.splice(index, 1);
        }
        
        // Hide with animation
        toast.classList.remove('show');
        
        // Remove from DOM after animation
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }
    
    /**
     * Show success toast
     */
    success(message, duration = 3000) {
        return this.show(message, 'success', duration);
    }
    
    /**
     * Show error toast
     */
    error(message, duration = 5000) {
        return this.show(message, 'error', duration);
    }
    
    /**
     * Show warning toast
     */
    warning(message, duration = 4000) {
        return this.show(message, 'warning', duration);
    }
    
    /**
     * Show info toast
     */
    info(message, duration = 3000) {
        return this.show(message, 'info', duration);
    }
    
    /**
     * Clear all toasts
     */
    clearAll() {
        [...this.activeToasts].forEach(toast => {
            this.removeToast(toast);
        });
    }
    
    /**
     * Show loading toast (doesn't auto-hide)
     */
    showLoading(message = 'Loading...') {
        const toast = this.createToastElement(message, 'info');
        toast.classList.add('loading-toast');
        
        // Add spinner
        const spinner = DOMUtils.createElement('div', {
            className: 'spinner',
            style: { display: 'inline-block', marginRight: '0.5rem' }
        });
        
        toast.insertBefore(spinner, toast.firstChild);
        
        // Add to page
        document.body.appendChild(toast);
        this.activeToasts.push(toast);
        
        // Show toast with animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        return toast;
    }
    
    /**
     * Hide loading toast
     */
    hideLoading(loadingToast) {
        if (loadingToast && loadingToast.classList.contains('loading-toast')) {
            this.removeToast(loadingToast);
        }
    }
    
    /**
     * Show toast with action button
     */
    showWithAction(message, type, actionText, actionCallback, duration = 5000) {
        const toast = this.createToastElement('', type);
        
        // Create message and action elements
        const messageSpan = DOMUtils.createElement('span', {}, message);
        const actionBtn = DOMUtils.createElement('button', {
            className: 'toast-action-btn',
            style: {
                marginLeft: '1rem',
                padding: '0.25rem 0.5rem',
                background: 'rgba(255, 255, 255, 0.2)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                borderRadius: '0.25rem',
                color: 'inherit',
                cursor: 'pointer',
                fontSize: '0.75rem'
            }
        }, actionText);
        
        // Add action handler
        actionBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            actionCallback();
            this.removeToast(toast);
        });
        
        toast.appendChild(messageSpan);
        toast.appendChild(actionBtn);
        
        // Add to page
        document.body.appendChild(toast);
        this.activeToasts.push(toast);
        
        // Show toast with animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Auto-hide toast after duration
        setTimeout(() => {
            this.removeToast(toast);
        }, duration);
        
        return toast;
    }
    
    /**
     * Show confirmation toast
     */
    showConfirmation(message, onConfirm, onCancel = null) {
        const toast = this.createToastElement('', 'warning');
        
        // Create message and action elements
        const messageSpan = DOMUtils.createElement('span', {}, message);
        const actionsDiv = DOMUtils.createElement('div', {
            style: {
                marginTop: '0.5rem',
                display: 'flex',
                gap: '0.5rem'
            }
        });
        
        const confirmBtn = DOMUtils.createElement('button', {
            className: 'toast-action-btn',
            style: {
                padding: '0.25rem 0.5rem',
                background: '#10b981',
                border: 'none',
                borderRadius: '0.25rem',
                color: 'white',
                cursor: 'pointer',
                fontSize: '0.75rem'
            }
        }, 'Confirm');
        
        const cancelBtn = DOMUtils.createElement('button', {
            className: 'toast-action-btn',
            style: {
                padding: '0.25rem 0.5rem',
                background: 'rgba(255, 255, 255, 0.2)',
                border: '1px solid rgba(255, 255, 255, 0.3)',
                borderRadius: '0.25rem',
                color: 'inherit',
                cursor: 'pointer',
                fontSize: '0.75rem'
            }
        }, 'Cancel');
        
        // Add action handlers
        confirmBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            onConfirm();
            this.removeToast(toast);
        });
        
        cancelBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (onCancel) onCancel();
            this.removeToast(toast);
        });
        
        actionsDiv.appendChild(confirmBtn);
        actionsDiv.appendChild(cancelBtn);
        
        toast.appendChild(messageSpan);
        toast.appendChild(actionsDiv);
        
        // Add to page
        document.body.appendChild(toast);
        this.activeToasts.push(toast);
        
        // Show toast with animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Don't auto-hide confirmation toasts
        
        return toast;
    }
}

// Export to global scope
window.ToastComponent = ToastComponent;
