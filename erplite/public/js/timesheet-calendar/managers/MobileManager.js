/**
 * Manages mobile-specific functionality and responsive behavior
 */
class MobileManager {
    constructor(app) {
        this.app = app;
        this.currentMobileDayIndex = 0;
        this.weekDates = [];
        this.lastMobileDayChange = 0;
        this.swipeThreshold = 50;
        this.swipeStartX = 0;
        this.swipeStartY = 0;
        this.isSwipeActive = false;
        
        this.init();
    }
    
    /**
     * Initialize mobile functionality
     */
    init() {
        this.initializeMobileNavigation();
        this.setupSwipeGestures();
        this.setupMobileButtons();
        this.handleResize();
    }
    
    /**
     * Initialize mobile day navigation
     */
    initializeMobileNavigation() {
        // Initialize week dates from day columns
        this.weekDates = [];
        document.querySelectorAll('.day-column').forEach(dayColumn => {
            this.weekDates.push(dayColumn.dataset.date);
        });
        
        // Set initial mobile day (Monday = 0)
        this.currentMobileDayIndex = 0;
        this.updateMobileDayDisplay();
        this.updateMobileDayPosition();
    }
    
    /**
     * Update mobile day display information
     */
    updateMobileDayDisplay() {
        if (this.weekDates.length === 0) return;
        
        const currentDate = new Date(this.weekDates[this.currentMobileDayIndex]);
        const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        
        const dayName = dayNames[currentDate.getDay()];
        const monthName = monthNames[currentDate.getMonth()];
        const dayNumber = currentDate.getDate();
        
        const dayNameElement = document.getElementById('currentDayName');
        const dayDateElement = document.getElementById('currentDayDate');
        
        if (dayNameElement) dayNameElement.textContent = dayName;
        if (dayDateElement) dayDateElement.textContent = `${monthName} ${dayNumber}`;
        
        // Update button states
        const prevBtn = document.getElementById('prevDayBtn');
        const nextBtn = document.getElementById('nextDayBtn');
        
        if (prevBtn) prevBtn.disabled = this.currentMobileDayIndex === 0;
        if (nextBtn) nextBtn.disabled = this.currentMobileDayIndex === this.weekDates.length - 1;
    }
    
    /**
     * Update mobile day position (slide animation)
     */
    updateMobileDayPosition() {
        const calendarDays = document.querySelector('.calendar-days');
        const calendarBody = document.querySelector('.calendar-body');
        
        if (calendarDays && calendarBody) {
            // Each day is 1/7th of the container, so we need to translate by (100/7)% per day
            const translateX = -this.currentMobileDayIndex * (100 / 7);
            calendarDays.style.transform = `translateX(${translateX}%)`;
            calendarBody.style.transform = `translateX(${translateX}%)`;
        }
    }
    
    /**
     * Change mobile day with debouncing
     */
    changeMobileDay(direction) {
        // Debounce to prevent double clicks
        const now = Date.now();
        if (now - this.lastMobileDayChange < 300) {
            return;
        }
        this.lastMobileDayChange = now;
        
        const newIndex = this.currentMobileDayIndex + direction;
        
        if (newIndex >= 0 && newIndex < this.weekDates.length) {
            this.currentMobileDayIndex = newIndex;
            this.updateMobileDayDisplay();
            this.updateMobileDayPosition();
            
            // Update app state
            this.app.setState({ currentMobileDayIndex: this.currentMobileDayIndex });
        }
    }
    
    /**
     * Setup mobile navigation buttons
     */
    setupMobileButtons() {
        const prevBtn = document.getElementById('prevDayBtn');
        const nextBtn = document.getElementById('nextDayBtn');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.changeMobileDay(-1));
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.changeMobileDay(1));
        }
    }
    
    /**
     * Setup swipe gestures for mobile navigation
     */
    setupSwipeGestures() {
        const calendarGrid = document.querySelector('.calendar-grid');
        if (!calendarGrid) return;
        
        // Touch events
        calendarGrid.addEventListener('touchstart', (e) => {
            this.handleSwipeStart(e);
        }, { passive: true });
        
        calendarGrid.addEventListener('touchmove', (e) => {
            this.handleSwipeMove(e);
        }, { passive: false });
        
        calendarGrid.addEventListener('touchend', (e) => {
            this.handleSwipeEnd(e);
        }, { passive: true });
        
        // Mouse events for desktop testing
        calendarGrid.addEventListener('mousedown', (e) => {
            if (this.isMobileView()) {
                this.handleSwipeStart(e, true);
            }
        });
        
        calendarGrid.addEventListener('mousemove', (e) => {
            if (this.isMobileView() && this.isSwipeActive) {
                this.handleSwipeMove(e, true);
            }
        });
        
        calendarGrid.addEventListener('mouseup', (e) => {
            if (this.isMobileView()) {
                this.handleSwipeEnd(e, true);
            }
        });
        
        // Prevent context menu on long press
        calendarGrid.addEventListener('contextmenu', (e) => {
            if (this.isMobileView()) {
                e.preventDefault();
            }
        });
    }
    
    /**
     * Handle swipe start
     */
    handleSwipeStart(e, isMouse = false) {
        if (!this.isMobileView()) return;
        
        const clientX = isMouse ? e.clientX : e.touches[0].clientX;
        const clientY = isMouse ? e.clientY : e.touches[0].clientY;
        
        this.swipeStartX = clientX;
        this.swipeStartY = clientY;
        this.isSwipeActive = true;
        
        if (isMouse) {
            e.preventDefault();
        }
    }
    
    /**
     * Handle swipe move
     */
    handleSwipeMove(e, isMouse = false) {
        if (!this.isSwipeActive || !this.isMobileView()) return;
        
        const clientX = isMouse ? e.clientX : e.touches[0].clientX;
        const clientY = isMouse ? e.clientY : e.touches[0].clientY;
        
        const deltaX = Math.abs(clientX - this.swipeStartX);
        const deltaY = Math.abs(clientY - this.swipeStartY);
        
        // Prevent default scrolling if horizontal swipe
        if (deltaX > deltaY && deltaX > 10) {
            e.preventDefault();
        }
        
        if (isMouse) {
            e.preventDefault();
        }
    }
    
    /**
     * Handle swipe end
     */
    handleSwipeEnd(e, isMouse = false) {
        if (!this.isSwipeActive || !this.isMobileView()) return;
        
        const clientX = isMouse ? e.clientX : (e.changedTouches ? e.changedTouches[0].clientX : this.swipeStartX);
        const clientY = isMouse ? e.clientY : (e.changedTouches ? e.changedTouches[0].clientY : this.swipeStartY);
        
        const deltaX = clientX - this.swipeStartX;
        const deltaY = clientY - this.swipeStartY;
        
        // Check if it's a horizontal swipe
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > this.swipeThreshold) {
            if (deltaX > 0) {
                // Swipe right - go to previous day
                this.changeMobileDay(-1);
            } else {
                // Swipe left - go to next day
                this.changeMobileDay(1);
            }
        }
        
        this.isSwipeActive = false;
    }
    
    /**
     * Check if currently in mobile view
     */
    isMobileView() {
        return window.innerWidth < 1200;
    }
    
    /**
     * Handle window resize
     */
    handleResize() {
        const isMobile = this.isMobileView();
        
        // Update mobile navigation visibility
        const mobileNav = document.querySelector('.mobile-day-nav');
        if (mobileNav) {
            mobileNav.style.display = isMobile ? 'flex' : 'none';
        }
        
        // Update calendar layout
        if (isMobile) {
            this.enableMobileLayout();
        } else {
            this.disableMobileLayout();
        }
    }
    
    /**
     * Enable mobile layout
     */
    enableMobileLayout() {
        // Ensure mobile day position is correct
        this.updateMobileDayPosition();
        
        // Hide day headers on mobile
        document.querySelectorAll('.day-header').forEach(header => {
            header.style.display = 'none';
        });
        
        // Adjust time block controls for mobile
        this.adjustMobileControls();
    }
    
    /**
     * Disable mobile layout
     */
    disableMobileLayout() {
        // Reset calendar position
        const calendarDays = document.querySelector('.calendar-days');
        const calendarBody = document.querySelector('.calendar-body');
        
        if (calendarDays) calendarDays.style.transform = 'translateX(0)';
        if (calendarBody) calendarBody.style.transform = 'translateX(0)';
        
        // Show day headers on desktop
        document.querySelectorAll('.day-header').forEach(header => {
            header.style.display = '';
        });
    }
    
    /**
     * Adjust controls for mobile view
     */
    adjustMobileControls() {
        // Make time block controls more touch-friendly
        document.querySelectorAll('.control-btn').forEach(btn => {
            if (this.isMobileView()) {
                btn.style.minWidth = '44px';
                btn.style.minHeight = '44px';
            } else {
                btn.style.minWidth = '';
                btn.style.minHeight = '';
            }
        });
    }
    
    /**
     * Get current visible day date
     */
    getCurrentVisibleDate() {
        if (this.isMobileView() && this.weekDates.length > 0) {
            return this.weekDates[this.currentMobileDayIndex];
        }
        return null;
    }
    
    /**
     * Navigate to specific day index
     */
    navigateToDay(dayIndex) {
        if (dayIndex >= 0 && dayIndex < this.weekDates.length) {
            this.currentMobileDayIndex = dayIndex;
            this.updateMobileDayDisplay();
            this.updateMobileDayPosition();
            
            // Update app state
            this.app.setState({ currentMobileDayIndex: this.currentMobileDayIndex });
        }
    }
    
    /**
     * Navigate to today if it's in current week
     */
    navigateToToday() {
        const today = new Date().toISOString().split('T')[0];
        const todayIndex = this.weekDates.indexOf(today);
        
        if (todayIndex !== -1) {
            this.navigateToDay(todayIndex);
            return true;
        }
        
        return false;
    }
    
    /**
     * Get mobile-specific settings
     */
    getMobileSettings() {
        return {
            isMobileView: this.isMobileView(),
            currentDayIndex: this.currentMobileDayIndex,
            currentDate: this.getCurrentVisibleDate(),
            weekDates: this.weekDates
        };
    }
}

// Export to global scope
window.MobileManager = MobileManager;
