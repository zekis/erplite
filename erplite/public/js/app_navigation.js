/**
 * Shared App Navigation JavaScript
 * Handles sidebar functionality across all ERPLite apps
 */

class AppNavigation {
    constructor() {
        this.sidebar = null;
        this.sidebarToggle = null;
        this.sidebarOverlay = null;
        this.mobileMenuBtn = null;
        this.currentApp = null;
        
        this.init();
    }
    
    /**
     * Initialize navigation
     */
    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }
    
    /**
     * Setup navigation elements and event listeners
     */
    setup() {
        // Get navigation elements
        this.sidebar = document.getElementById('appSidebar');
        this.sidebarToggle = document.getElementById('sidebarToggle');
        this.sidebarOverlay = document.getElementById('sidebarOverlay');
        this.mobileMenuBtn = document.querySelector('.mobile-menu-btn');
        
        if (!this.sidebar) {
            console.log('App navigation not found on this page');
            return;
        }
        
        // Restore collapsed state FIRST to prevent flash
        this.restoreCollapsedState();
        
        // Detect current app and set active menu item
        this.detectCurrentApp();
        this.setActiveMenuItem();
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Setup mobile navigation
        this.setupMobileNavigation();
        
        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();
        
        // Add tooltip titles for collapsed sidebar
        this.addTooltipTitles();
        
        console.log('App navigation initialized');
    }
    
    /**
     * Detect current app from URL
     */
    detectCurrentApp() {
        const path = window.location.pathname;
        
        if (path.includes('/todo')) {
            this.currentApp = 'todo';
        } else if (path.includes('/scheduler')) {
            this.currentApp = 'scheduler';
        } else if (path.includes('/timesheet-calendar')) {
            this.currentApp = 'timesheet-calendar';
        } else if (path.includes('/app') || path === '/') {
            this.currentApp = 'desk';
        }
        
        console.log('Current app detected:', this.currentApp);
    }
    
    /**
     * Set active menu item based on current app
     */
    setActiveMenuItem() {
        if (!this.currentApp) return;
        
        // Remove active class from all menu items
        const menuItems = this.sidebar.querySelectorAll('.menu-item');
        menuItems.forEach(item => item.classList.remove('active'));
        
        // Add active class to current app menu item
        const currentMenuItem = this.sidebar.querySelector(`[data-app="${this.currentApp}"]`);
        if (currentMenuItem) {
            currentMenuItem.classList.add('active');
        }
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Sidebar toggle for desktop
        if (this.sidebarToggle) {
            this.sidebarToggle.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleSidebar();
            });
        }
        
        // Mobile menu button
        if (this.mobileMenuBtn) {
            this.mobileMenuBtn.addEventListener('click', () => {
                this.toggleMobileSidebar();
            });
        }
        
        // Sidebar overlay click (mobile)
        if (this.sidebarOverlay) {
            this.sidebarOverlay.addEventListener('click', () => {
                this.closeMobileSidebar();
            });
        }
        
        // Menu item clicks
        const menuItems = this.sidebar.querySelectorAll('.menu-item');
        menuItems.forEach(item => {
            item.addEventListener('click', (e) => {
                this.handleMenuItemClick(e, item);
            });
        });
        
        // Handle window resize
        window.addEventListener('resize', () => {
            this.handleResize();
        });
    }
    
    /**
     * Setup mobile navigation
     */
    setupMobileNavigation() {
        // Create mobile header if it doesn't exist
        if (window.innerWidth <= 768 && !document.querySelector('.mobile-header')) {
            this.createMobileHeader();
        }
    }
    
    /**
     * Create mobile header with menu button
     */
    createMobileHeader() {
        const mainContent = document.querySelector('.main-content');
        if (!mainContent) return;
        
        const mobileHeader = document.createElement('div');
        mobileHeader.className = 'mobile-header';
        mobileHeader.innerHTML = `
            <button class="mobile-menu-btn" type="button">
                <i class="mdi mdi-menu"></i>
            </button>
            <h1 class="mobile-title">${this.getAppTitle()}</h1>
        `;
        
        mainContent.insertBefore(mobileHeader, mainContent.firstChild);
        
        // Update mobile menu button reference
        this.mobileMenuBtn = mobileHeader.querySelector('.mobile-menu-btn');
        
        // Add event listener
        this.mobileMenuBtn.addEventListener('click', () => {
            this.toggleMobileSidebar();
        });
    }
    
    /**
     * Get app title for mobile header
     */
    getAppTitle() {
        const titles = {
            'todo': 'Todo Kanban',
            'scheduler': 'Scheduler',
            'timesheet-dashboard': 'Timesheet Dashboard',
            'timesheet-calendar': 'Timesheet Calendar'
        };
        
        return titles[this.currentApp] || 'ERPLite';
    }
    
    /**
     * Toggle sidebar (desktop)
     */
    toggleSidebar() {
        if (!this.sidebar) return;
        
        const isCurrentlyCollapsed = this.sidebar.classList.contains('collapsed');
        
        if (isCurrentlyCollapsed) {
            this.sidebar.classList.remove('collapsed');
        } else {
            this.sidebar.classList.add('collapsed');
        }
        
        // Save state to localStorage
        const isCollapsed = this.sidebar.classList.contains('collapsed');
        localStorage.setItem('sidebar-collapsed', isCollapsed.toString());
        
        console.log('Sidebar toggled, collapsed:', isCollapsed);
    }
    
    /**
     * Toggle mobile sidebar
     */
    toggleMobileSidebar() {
        if (!this.sidebar) return;
        
        const isOpen = this.sidebar.classList.contains('mobile-open');
        
        if (isOpen) {
            this.closeMobileSidebar();
        } else {
            this.openMobileSidebar();
        }
    }
    
    /**
     * Open mobile sidebar
     */
    openMobileSidebar() {
        if (!this.sidebar) return;
        
        this.sidebar.classList.add('mobile-open');
        if (this.sidebarOverlay) {
            this.sidebarOverlay.classList.add('active');
        }
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }
    
    /**
     * Close mobile sidebar
     */
    closeMobileSidebar() {
        if (!this.sidebar) return;
        
        this.sidebar.classList.remove('mobile-open');
        if (this.sidebarOverlay) {
            this.sidebarOverlay.classList.remove('active');
        }
        
        // Restore body scroll
        document.body.style.overflow = '';
    }
    
    /**
     * Handle menu item click
     */
    handleMenuItemClick(e, item) {
        const href = item.getAttribute('href');
        const app = item.getAttribute('data-app');
        
        // Close mobile sidebar if open
        if (window.innerWidth <= 768) {
            this.closeMobileSidebar();
        }
        
        // Let the browser handle navigation naturally
        console.log('Navigating to:', app, href);
    }
    
    /**
     * Handle window resize
     */
    handleResize() {
        const isMobile = window.innerWidth <= 768;
        
        if (!isMobile) {
            // Close mobile sidebar if window becomes desktop size
            this.closeMobileSidebar();
            
            // Restore sidebar state from localStorage on desktop
            this.restoreCollapsedState();
        } else {
            // Remove collapsed class on mobile
            if (this.sidebar) {
                this.sidebar.classList.remove('collapsed');
            }
            
            // Create mobile header if it doesn't exist
            if (!document.querySelector('.mobile-header')) {
                this.createMobileHeader();
            }
        }
    }
    
    /**
     * Setup keyboard shortcuts
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Alt + M: Toggle sidebar
            if (e.altKey && e.key === 'm') {
                e.preventDefault();
                if (window.innerWidth <= 768) {
                    this.toggleMobileSidebar();
                } else {
                    this.toggleSidebar();
                }
            }
            
            // Escape: Close mobile sidebar
            if (e.key === 'Escape' && window.innerWidth <= 768) {
                this.closeMobileSidebar();
            }
            
            // Number keys for quick navigation (Alt + 1-4)
            if (e.altKey && e.key >= '1' && e.key <= '4') {
                e.preventDefault();
                const menuItems = this.sidebar.querySelectorAll('.menu-item');
                const index = parseInt(e.key) - 1;
                if (menuItems[index]) {
                    menuItems[index].click();
                }
            }
        });
    }
    
    /**
     * Add tooltip titles for collapsed sidebar
     */
    addTooltipTitles() {
        const menuItems = this.sidebar.querySelectorAll('.menu-item');
        menuItems.forEach(item => {
            const text = item.querySelector('.menu-text');
            if (text) {
                item.setAttribute('title', text.textContent);
            }
        });
    }
    
    /**
     * Restore collapsed state from localStorage
     */
    restoreCollapsedState() {
        if (!this.sidebar) return;
        
        // Only restore on desktop
        if (window.innerWidth > 768) {
            const savedState = localStorage.getItem('sidebar-collapsed');
            if (savedState === 'true') {
                this.sidebar.classList.add('collapsed');
            } else {
                this.sidebar.classList.remove('collapsed');
            }
        }
    }
    
    /**
     * Check if sidebar is collapsed
     */
    isSidebarCollapsed() {
        return this.sidebar && this.sidebar.classList.contains('collapsed');
    }
    
    /**
     * Check if mobile sidebar is open
     */
    isMobileSidebarOpen() {
        return this.sidebar && this.sidebar.classList.contains('mobile-open');
    }
}

// Initialize navigation when script loads
let appNavigation;

// Auto-initialize
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        appNavigation = new AppNavigation();
    });
} else {
    appNavigation = new AppNavigation();
}

// Make available globally
window.AppNavigation = AppNavigation;
window.appNavigation = appNavigation;
