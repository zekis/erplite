/**
 * Sidebar component for project and activity management
 */
class SidebarComponent {
    constructor(app) {
        this.app = app;
        this.pinnedActivitys = new Set();
        this.init();
    }
    
    /**
     * Initialize sidebar functionality
     */
    init() {
        this.setupSearchFunctionality();
        this.setupProjectToggling();
        this.setupActivityToggling();
        this.setupPinningFunctionality();
        this.setupWeekNavigation();
        this.loadPinnedActivitys();
    }
    
    /**
     * Setup search functionality
     */
    setupSearchFunctionality() {
        // Create search input if it doesn't exist
        this.createSearchInput();
        
        const searchInput = document.getElementById('sidebar-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterProjects(e.target.value);
            });
            
            // Add clear button functionality
            const clearBtn = document.getElementById('search-clear');
            if (clearBtn) {
                clearBtn.addEventListener('click', () => {
                    searchInput.value = '';
                    this.clearFilter();
                });
            }
        }
    }
    
    /**
     * Create search input in sidebar
     */
    createSearchInput() {
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar || document.getElementById('sidebar-search')) return;
        
        const searchContainer = document.createElement('div');
        searchContainer.className = 'search-container';
        searchContainer.innerHTML = `
            <div class="search-input-wrapper">
                <input type="text" id="sidebar-search" placeholder="Search projects and activities..." class="search-input">
                <button id="search-clear" class="search-clear" title="Clear search">×</button>
            </div>
        `;
        
        // Insert after the sidebar header (which contains the title and week navigation)
        const sidebarHeader = sidebar.querySelector('.sidebar-header');
        if (sidebarHeader) {
            sidebarHeader.parentNode.insertBefore(searchContainer, sidebarHeader.nextSibling);
        } else {
            // Fallback: insert at the top if no header found
            sidebar.insertBefore(searchContainer, sidebar.firstChild);
        }
        
        // Add CSS for search functionality
        this.addSearchStyles();
    }
    
    /**
     * Add CSS styles for search functionality
     */
    addSearchStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .search-container {
                padding: 1rem;
                border-bottom: 1px solid #e2e8f0;
                background: #f8fafc;
            }
            
            .search-input-wrapper {
                position: relative;
                margin-bottom: 0.5rem;
            }
            
            .search-input {
                width: 100%;
                padding: 0.5rem 2rem 0.5rem 0.75rem;
                border: 1px solid #d1d5db;
                border-radius: 0.375rem;
                font-size: 0.875rem;
                background: white;
            }
            
            .search-input:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
            
            .search-clear {
                position: absolute;
                right: 0.5rem;
                top: 50%;
                transform: translateY(-50%);
                background: none;
                border: none;
                font-size: 1.25rem;
                color: #6b7280;
                cursor: pointer;
                padding: 0;
                width: 1.5rem;
                height: 1.5rem;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .search-clear:hover {
                color: #374151;
            }
            
            .search-actions {
                display: flex;
                gap: 0.5rem;
            }
            
            .btn-small {
                padding: 0.25rem 0.5rem;
                font-size: 0.75rem;
                border: 1px solid #d1d5db;
                border-radius: 0.25rem;
                background: white;
                cursor: pointer;
                flex: 1;
            }
            
            .btn-small:hover {
                background: #f3f4f6;
            }
            
            .activity-group {
                margin-left: 1rem;
                border-left: 2px solid #e5e7eb;
                padding-left: 0.5rem;
            }
            
            .activity-group.collapsed .activity-block {
                display: none;
            }
            
            .activity-toggle {
                cursor: pointer;
                user-select: none;
                font-size: 0.75rem;
                color: #6b7280;
                margin-right: 0.25rem;
            }
            
            .activity-buttons {
                display: flex;
                gap: 0.25rem;
                margin-left: auto;
                align-items: center;
            }
            
            .open-button,
            .pin-button {
                background: none;
                border: none;
                cursor: pointer;
                padding: 0.125rem;
                font-size: 0.875rem;
                color: #9ca3af;
                transition: color 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .open-button:hover {
                color: #3b82f6;
            }
            
            .pin-button:hover {
                color: #6b7280;
            }
            
            .pin-button.pinned {
                color: #6b7280;
            }
            
            .pinned-section {
                border-bottom: 1px solid #e2e8f0;
                margin-bottom: 0.5rem;
                padding-bottom: 0.5rem;
            }
            
            .pinned-section .section-title {
                font-size: 0.75rem;
                font-weight: 600;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 0.5rem;
                display: flex;
                align-items: center;
                gap: 0.25rem;
            }
            
            
            .pinned-activities-section {
                border-bottom: 1px solid #e2e8f0;
                margin-bottom: 1rem;
                background: #f8fafc;
            }
            
            .pinned-section-header {
                padding: 0.75rem 1rem;
                background: #f1f5f9;
                border-bottom: 1px solid #e2e8f0;
            }
            
            .pinned-section-header .section-title {
                font-size: 0.875rem;
                font-weight: 600;
                color: #374151;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }
            
            .pinned-section-header .section-icon {
                color: #6b7280;
                font-size: 1rem;
            }
            
            .section-count {
                color: #6b7280;
                font-weight: 400;
                font-size: 0.75rem;
            }
            
            .pinned-activities-container {
                padding: 0.5rem;
            }
            
            .pinned-activity-clone {
                margin-bottom: 0.25rem;
                border-radius: 0.375rem;
                background: white;
                border: 1px solid #e5e7eb;
            }
        `;
        
        document.head.appendChild(style);
    }
    
    /**
     * Setup activity expand/collapse functionality
     */
    setupActivityToggling() {
        // Enhanced project toggle that shows activity count
        this.enhanceProjectToggles();
    }
    
    /**
     * Enhance project toggles with activity counts and better UX
     */
    enhanceProjectToggles() {
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const activities = projectGroup.querySelectorAll('.activity-block');
            const projectToggle = projectGroup.querySelector('.project-toggle');
            const projectHeader = projectGroup.querySelector('.project-header');
            const activityList = projectGroup.querySelector('.activity-list');
            
            if (projectToggle) {
                if (activities.length > 0) {
                    // Project has activities - make it interactive and visible
                    projectToggle.textContent = `▼`; // Down arrow for collapsed (can expand down)
                    projectToggle.title = 'Click to expand/collapse activities';
                    projectGroup.style.display = '';
                    
                    // Start all projects with activities collapsed
                    this.toggleProject(projectGroup);
                } else {
                    // Project has no activities - hide it completely
                    projectGroup.style.display = 'none';
                }
            }
        });
    }
    
    /**
     * Setup pinning functionality
     */
    setupPinningFunctionality() {
        // Load pinned activities from localStorage first for immediate UI
        this.loadPinnedActivitys();
        
        // Add pin buttons with current state
        this.addPinButtons();
        
        // Then fetch from backend and sync
        this.fetchHeartStatusFromBackend().then(() => {
            // Refresh pin buttons after backend sync
            this.refreshPinButtons();
            this.reorganizeActivitys();
        });
    }
    
    /**
     * Fetch heart status from Frappe backend
     */
    fetchHeartStatusFromBackend() {
        return new Promise((resolve) => {
            if (typeof frappe === 'undefined' || !frappe.call) {
                console.warn('Frappe not available, using localStorage only');
                resolve();
                return;
            }
            
            // Get all activity IDs from the sidebar
            const activityIds = [];
            document.querySelectorAll('.activity-block').forEach(activityBlock => {
                const activityId = activityBlock.dataset.activity;
                if (activityId) {
                    activityIds.push(activityId);
                }
            });
            
            if (activityIds.length === 0) {
                resolve();
                return;
            }
            
            // Fetch heart status for all activities using Comment doctype with comment_type = "Like"
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Comment',
                    filters: {
                        comment_type: 'Like',
                        reference_doctype: 'Activity',
                        reference_name: ['in', activityIds],
                        owner: frappe.session.user
                    },
                    fields: ['reference_name']
                },
                callback: (r) => {
                    if (r.message) {
                        // Update pinned activities based on backend data
                        this.syncPinnedActivitysFromBackend(r.message);
                    }
                    resolve();
                },
                error: (err) => {
                    console.warn('Failed to fetch heart status from backend:', err);
                    resolve();
                }
            });
        });
    }
    
    /**
     * Sync pinned activities from backend heart status
     */
    syncPinnedActivitysFromBackend(likeRecords) {
        // Clear existing pinned activities
        this.pinnedActivitys.clear();
        
        // Process like records from backend
        likeRecords.forEach(likeRecord => {
            const activityId = likeRecord.reference_name;
            // Find the project for this activity
            const activityBlock = document.querySelector(`[data-activity="${activityId}"]`);
            if (activityBlock) {
                const projectId = activityBlock.dataset.project;
                const activityKey = `${projectId}:${activityId}`;
                this.pinnedActivitys.add(activityKey);
            }
        });
        
        // Save to localStorage for offline access
        this.savePinnedActivitys();
        
        console.log(`Synced ${this.pinnedActivitys.size} pinned activities from backend`);
    }
    
    /**
     * Add pin buttons to activity blocks
     */
    addPinButtons() {
        document.querySelectorAll('.activity-block').forEach(activityBlock => {
            if (activityBlock.querySelector('.pin-button')) return; // Already has pin button
            
            // Create button container
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'activity-buttons';
            
            // Create open in desk button
            const openButton = document.createElement('button');
            openButton.className = 'open-button mdi';
            openButton.innerHTML = '<i class="mdi mdi-open-in-new"></i>';
            openButton.title = 'Open activity in desk view';
            
            // Create pin button
            const pinButton = document.createElement('button');
            pinButton.className = 'pin-button mdi';
            pinButton.innerHTML = '<i class="mdi mdi-pin-outline"></i>'; // Outline pin icon
            pinButton.title = 'Pin this activity to top';
            
            const activityId = activityBlock.dataset.activity;
            const projectId = activityBlock.dataset.project;
            const activityKey = `${projectId}:${activityId}`;
            
            // Set initial pin state
            if (this.pinnedActivitys.has(activityKey)) {
                pinButton.innerHTML = '<i class="mdi mdi-pin"></i>'; // Filled pin icon
                pinButton.classList.add('pinned');
                pinButton.title = 'Unpin this activity';
                activityBlock.classList.add('pinned');
            }
            
            // Add event listeners
            openButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.openActivityInDesk(activityId);
            });
            
            pinButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.togglePin(activityBlock, pinButton);
            });
            
            // Add buttons to container
            buttonContainer.appendChild(openButton);
            buttonContainer.appendChild(pinButton);
            
            activityBlock.appendChild(buttonContainer);
        });
    }
    
    /**
     * Refresh pin button states after backend sync
     */
    refreshPinButtons() {
        document.querySelectorAll('.activity-block').forEach(activityBlock => {
            const pinButton = activityBlock.querySelector('.pin-button');
            if (!pinButton) return;
            
            const activityId = activityBlock.dataset.activity;
            const projectId = activityBlock.dataset.project;
            const activityKey = `${projectId}:${activityId}`;
            
            // Update pin button state based on current pinned activities
            if (this.pinnedActivitys.has(activityKey)) {
                pinButton.innerHTML = '<i class="mdi mdi-pin"></i>'; // Filled pin icon
                pinButton.classList.add('pinned');
                pinButton.title = 'Unpin this activity';
                activityBlock.classList.add('pinned');
            } else {
                pinButton.innerHTML = '<i class="mdi mdi-pin-outline"></i>'; // Outline pin icon
                pinButton.classList.remove('pinned');
                pinButton.title = 'Pin this activity to top';
                activityBlock.classList.remove('pinned');
            }
        });
    }
    
    /**
     * Open activity in Frappe desk view
     */
    openActivityInDesk(activityId) {
        if (typeof frappe !== 'undefined' && frappe.set_route) {
            frappe.set_route('Form', 'Activity', activityId);
        } else {
            // Fallback: open in new tab
            const url = `/app/activity/${activityId}`;
            window.open(url, '_blank');
        }
    }
    
    /**
     * Toggle pin state of a activity
     */
    togglePin(activityBlock, pinButton) {
        const activityId = activityBlock.dataset.activity;
        const projectId = activityBlock.dataset.project;
        const activityKey = `${projectId}:${activityId}`;
        
        if (this.pinnedActivitys.has(activityKey)) {
            // Unpin
            this.pinnedActivitys.delete(activityKey);
            
            // Update the cloned activity button (if this is a clone)
            pinButton.innerHTML = '<i class="mdi mdi-pin-outline"></i>'; // Outline pin icon
            pinButton.classList.remove('pinned');
            pinButton.title = 'Pin this activity to top';
            activityBlock.classList.remove('pinned');
            
            // Find and update the original activity in the project section
            const originalActivity = document.querySelector(`[data-project="${projectId}"][data-activity="${activityId}"]:not(.pinned-activity-clone)`);
            if (originalActivity) {
                const originalPinButton = originalActivity.querySelector('.pin-button');
                if (originalPinButton) {
                    originalPinButton.innerHTML = '<i class="mdi mdi-pin-outline"></i>';
                    originalPinButton.classList.remove('pinned');
                    originalPinButton.title = 'Pin this activity to top';
                }
                originalActivity.classList.remove('pinned');
                
                // Show the original activity back in its project
                originalActivity.style.display = '';
                originalActivity.classList.remove('hidden-pinned');
            }
            
            // Use Frappe's API to remove from favorites
            this.updateFrappeHeart(activityId, false);
        } else {
            // Pin
            this.pinnedActivitys.add(activityKey);
            
            // Update the current activity button
            pinButton.innerHTML = '<i class="mdi mdi-pin"></i>'; // Filled pin icon
            pinButton.classList.add('pinned');
            pinButton.title = 'Unpin this activity';
            activityBlock.classList.add('pinned');
            
            // Find and update the original activity in the project section (if this is not the original)
            if (activityBlock.classList.contains('pinned-activity-clone')) {
                const originalActivity = document.querySelector(`[data-project="${projectId}"][data-activity="${activityId}"]:not(.pinned-activity-clone)`);
                if (originalActivity) {
                    const originalPinButton = originalActivity.querySelector('.pin-button');
                    if (originalPinButton) {
                        originalPinButton.innerHTML = '<i class="mdi mdi-pin"></i>';
                        originalPinButton.classList.add('pinned');
                        originalPinButton.title = 'Unpin this activity';
                    }
                    originalActivity.classList.add('pinned');
                }
            }
            
            // Use Frappe's API to add to favorites
            this.updateFrappeHeart(activityId, true);
        }
        
        this.savePinnedActivitys();
        this.reorganizeActivitys();
    }
    
    /**
     * Update Frappe's heart/favorite status
     */
    updateFrappeHeart(activityId, isPinned) {
        if (typeof frappe === 'undefined' || !frappe.call) {
            console.warn('Frappe not available for heart update');
            return;
        }

        console.log(`Attempting to ${isPinned ? 'pin' : 'unpin'} activity ${activityId}`);

        if (isPinned) {
            // First check if already liked to avoid duplicates
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Comment',
                    filters: {
                        comment_type: 'Like',
                        reference_doctype: 'Activity',
                        reference_name: activityId,
                        owner: frappe.session.user
                    },
                    fields: ['name']
                },
                callback: (r) => {
                    if (r.message && r.message.length > 0) {
                        console.log(`Activity ${activityId} already liked by user`);
                    } else {
                        // Insert new like
                        frappe.call({
                            method: 'frappe.client.insert',
                            args: {
                                doc: {
                                    doctype: 'Comment',
                                    comment_type: 'Like',
                                    reference_doctype: 'Activity',
                                    reference_name: activityId,
                                    content: 'Liked'
                                }
                            },
                            callback: (insertResponse) => {
                                console.log(`Activity ${activityId} pinned successfully in backend`);
                            },
                            error: (err) => {
                                console.error('Failed to insert like comment:', err);
                                if (this.app && this.app.components && this.app.components.toast) {
                                    this.app.components.toast.show(
                                        `Failed to sync pin status with server for activity ${activityId}`, 
                                        'warning'
                                    );
                                }
                            }
                        });
                    }
                },
                error: (err) => {
                    console.error('Failed to check existing likes:', err);
                }
            });
        } else {
            // Remove like by deleting the Comment record
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Comment',
                    filters: {
                        comment_type: 'Like',
                        reference_doctype: 'Activity',
                        reference_name: activityId,
                        owner: frappe.session.user
                    },
                    fields: ['name']
                },
                callback: (r) => {
                    if (r.message && r.message.length > 0) {
                        // Delete the like comment
                        frappe.call({
                            method: 'frappe.client.delete',
                            args: {
                                doctype: 'Comment',
                                name: r.message[0].name
                            },
                            callback: (deleteResponse) => {
                                console.log(`Activity ${activityId} unpinned successfully in backend`);
                            },
                            error: (err) => {
                                console.error('Failed to delete like comment:', err);
                                if (this.app && this.app.components && this.app.components.toast) {
                                    this.app.components.toast.show(
                                        `Failed to remove pin status from server for activity ${activityId}`, 
                                        'warning'
                                    );
                                }
                            }
                        });
                    } else {
                        console.log(`No like found to remove for activity ${activityId}`);
                    }
                },
                error: (err) => {
                    console.error('Failed to find like comment to delete:', err);
                }
            });
        }
    }
    
    /**
     * Reorganize activities to show pinned ones at top
     */
    reorganizeActivitys() {
        // Create or update the dedicated pinned activities section
        this.createPinnedActivitysSection();
        
        // Hide pinned activities from their original project locations (don't remove them)
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const activityContainer = projectGroup.querySelector('.activity-group') || projectGroup;
            const activities = Array.from(activityContainer.querySelectorAll('.activity-block'));
            
            // Hide pinned activities from project groups (they'll be in the pinned section)
            activities.forEach(activity => {
                const activityKey = `${activity.dataset.project}:${activity.dataset.activity}`;
                if (this.pinnedActivitys.has(activityKey)) {
                    activity.style.display = 'none';
                    activity.classList.add('hidden-pinned');
                } else {
                    activity.style.display = '';
                    activity.classList.remove('hidden-pinned');
                }
            });
            
            // Sort remaining visible activities alphabetically
            const visibleActivitys = Array.from(activityContainer.querySelectorAll('.activity-block:not(.hidden-pinned)'));
            visibleActivitys.sort((a, b) => {
                return a.dataset.activityName.localeCompare(b.dataset.activityName);
            });
            
            // Reorder visible activities in DOM
            visibleActivitys.forEach(activity => {
                activityContainer.appendChild(activity);
            });
        });
    }
    
    /**
     * Create dedicated pinned activities section at top of sidebar
     */
    createPinnedActivitysSection() {
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar) {
            console.warn('Sidebar not found');
            return;
        }
        
        // Remove existing pinned section
        const existingPinnedSection = document.getElementById('pinned-activities-section');
        if (existingPinnedSection) {
            existingPinnedSection.remove();
        }
        
        // If no pinned activities, don't create section
        if (this.pinnedActivitys.size === 0) {
            console.log('No pinned activities to display');
            return;
        }
        
        console.log(`Creating pinned section for ${this.pinnedActivitys.size} activities:`, [...this.pinnedActivitys]);
        
        // Create pinned activities section
        const pinnedSection = document.createElement('div');
        pinnedSection.id = 'pinned-activities-section';
        pinnedSection.className = 'pinned-activities-section';
        
        // Create section header
        const sectionHeader = document.createElement('div');
        sectionHeader.className = 'pinned-section-header';
        sectionHeader.innerHTML = `
            <div class="section-title">
                <i class="mdi mdi-pin section-icon"></i>
                <span class="section-text">Pinned Activitys</span>
                <span class="section-count">(${this.pinnedActivitys.size})</span>
            </div>
        `;
        
        pinnedSection.appendChild(sectionHeader);
        
        // Create container for pinned activities
        const pinnedActivitysContainer = document.createElement('div');
        pinnedActivitysContainer.className = 'pinned-activities-container';
        
        // Collect all pinned activities and clone them
        const pinnedActivityElements = [];
        this.pinnedActivitys.forEach(activityKey => {
            const [projectId, activityId] = activityKey.split(':');
            console.log(`Looking for activity: project=${projectId}, activity=${activityId}`);
            
            // Try multiple selectors to find the original activity
            let originalActivity = document.querySelector(`[data-project="${projectId}"][data-activity="${activityId}"]`);
            
            // If not found, try looking in hidden activities
            if (!originalActivity) {
                originalActivity = document.querySelector(`[data-project="${projectId}"][data-activity="${activityId}"].hidden-pinned`);
            }
            
            // If still not found, try without hidden class
            if (!originalActivity) {
                const allActivitys = document.querySelectorAll(`[data-activity="${activityId}"]`);
                console.log(`Found ${allActivitys.length} activities with ID ${activityId}`);
                originalActivity = Array.from(allActivitys).find(activity => activity.dataset.project === projectId);
            }
            
            if (originalActivity) {
                console.log(`Found original activity for ${activityKey}:`, originalActivity);
                
                const clonedActivity = originalActivity.cloneNode(true);
                clonedActivity.classList.add('pinned-activity-clone');
                clonedActivity.classList.remove('hidden-pinned'); // Make sure it's visible
                clonedActivity.style.display = ''; // Ensure it's not hidden
                
                // Re-add event listeners to cloned buttons
                this.setupClonedActivityButtons(clonedActivity, activityId);
                
                pinnedActivityElements.push({
                    element: clonedActivity,
                    activityName: clonedActivity.dataset.activityName || 'Unknown Activity',
                    projectName: this.getProjectName(projectId) || 'Unknown Project'
                });
            } else {
                console.warn(`Could not find original activity for ${activityKey}`);
            }
        });
        
        console.log(`Found ${pinnedActivityElements.length} pinned activity elements to display`);
        
        // Sort pinned activities alphabetically
        pinnedActivityElements.sort((a, b) => {
            const aName = `${a.projectName} - ${a.activityName}`;
            const bName = `${b.projectName} - ${b.activityName}`;
            return aName.localeCompare(bName);
        });
        
        // Add sorted pinned activities to container
        pinnedActivityElements.forEach((item, index) => {
            console.log(`Adding pinned activity ${index + 1}:`, item.activityName);
            pinnedActivitysContainer.appendChild(item.element);
        });
        
        pinnedSection.appendChild(pinnedActivitysContainer);
        
        // Insert pinned section after search container
        const searchContainer = document.querySelector('.search-container');
        if (searchContainer) {
            searchContainer.parentNode.insertBefore(pinnedSection, searchContainer.nextSibling);
            console.log('Inserted pinned section after search container');
        } else {
            sidebar.insertBefore(pinnedSection, sidebar.firstChild);
            console.log('Inserted pinned section at top of sidebar');
        }
        
        console.log('Pinned activities section created successfully');
    }
    
    /**
     * Setup event listeners for cloned activity buttons
     */
    setupClonedActivityButtons(clonedActivity, activityId) {
        const openButton = clonedActivity.querySelector('.open-button');
        const pinButton = clonedActivity.querySelector('.pin-button');
        
        if (openButton) {
            openButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.openActivityInDesk(activityId);
            });
        }
        
        if (pinButton) {
            pinButton.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.togglePin(clonedActivity, pinButton);
            });
        }
        
        // Setup drag functionality for cloned activities
        this.setupClonedActivityDrag(clonedActivity);
    }
    
    /**
     * Setup drag functionality for cloned pinned activities
     */
    setupClonedActivityDrag(clonedActivity) {
        // Make sure the cloned activity is draggable
        clonedActivity.draggable = true;
        
        clonedActivity.addEventListener('dragstart', (e) => {
            clonedActivity.classList.add('dragging');
            
            const activityData = {
                project: clonedActivity.dataset.project,
                activity: clonedActivity.dataset.activity,
                projectName: clonedActivity.dataset.projectName,
                activityName: clonedActivity.dataset.activityName,
                color: clonedActivity.dataset.color,
                isExistingBlock: false // This is a new activity from sidebar, not an existing time block
            };
            
            e.dataTransfer.setData('text/plain', JSON.stringify(activityData));
            e.dataTransfer.effectAllowed = 'copy';
        });
        
        clonedActivity.addEventListener('dragend', (e) => {
            clonedActivity.classList.remove('dragging');
        });
    }
    
    /**
     * Save pinned activities to localStorage
     */
    savePinnedActivitys() {
        localStorage.setItem('timesheet_pinned_activities', JSON.stringify([...this.pinnedActivitys]));
    }
    
    /**
     * Load pinned activities from localStorage
     */
    loadPinnedActivitys() {
        const saved = localStorage.getItem('timesheet_pinned_activities');
        if (saved) {
            try {
                const pinnedArray = JSON.parse(saved);
                this.pinnedActivitys = new Set(pinnedArray);
            } catch (e) {
                console.warn('Failed to load pinned activities:', e);
                this.pinnedActivitys = new Set();
            }
        }
    }
    
    /**
     * Setup project collapsing/expanding
     */
    setupProjectToggling() {
        // Don't add event listeners here since HTML uses onclick="toggleProject()"
        // The global toggleProject function will call toggleProjectByName which calls toggleProject
        console.log('Project toggling setup - using global toggleProject function');
    }
    
    /**
     * Setup week navigation
     */
    setupWeekNavigation() {
        // Week navigation buttons are handled by CalendarManager
        // This is just for any sidebar-specific navigation features
    }
    
    /**
     * Toggle project visibility
     */
    toggleProject(projectGroup) {
        projectGroup.classList.toggle('collapsed');
        
        // Update toggle icon
        const toggle = projectGroup.querySelector('.project-toggle');
        if (toggle) {
            if (projectGroup.classList.contains('collapsed')) {
                toggle.textContent = `▼`; // Down arrow when collapsed (can expand down)
            } else {
                toggle.textContent = `▲`; // Up arrow when expanded (can collapse up)
            }
        }
        
        // Save collapsed state to localStorage
        this.saveProjectStates();
    }
    
    /**
     * Toggle project by name (for global function compatibility)
     */
    toggleProjectByName(projectName) {
        const projectGroup = document.querySelector(`[data-project="${projectName}"]`);
        if (projectGroup) {
            this.toggleProject(projectGroup);
        }
    }
    
    /**
     * Expand all projects
     */
    expandAllProjects() {
        document.querySelectorAll('.project-group.collapsed').forEach(projectGroup => {
            this.toggleProject(projectGroup);
        });
    }
    
    /**
     * Collapse all projects
     */
    collapseAllProjects() {
        document.querySelectorAll('.project-group:not(.collapsed)').forEach(projectGroup => {
            this.toggleProject(projectGroup);
        });
    }
    
    /**
     * Save project collapsed states to localStorage
     */
    saveProjectStates() {
        const states = {};
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const projectName = projectGroup.dataset.project;
            states[projectName] = projectGroup.classList.contains('collapsed');
        });
        
        localStorage.setItem('timesheet_project_states', JSON.stringify(states));
    }
    
    /**
     * Load project collapsed states from localStorage
     */
    loadProjectStates() {
        const saved = localStorage.getItem('timesheet_project_states');
        if (!saved) return;
        
        try {
            const states = JSON.parse(saved);
            Object.entries(states).forEach(([projectName, isCollapsed]) => {
                const projectGroup = document.querySelector(`[data-project="${projectName}"]`);
                if (projectGroup) {
                    if (isCollapsed && !projectGroup.classList.contains('collapsed')) {
                        this.toggleProject(projectGroup);
                    } else if (!isCollapsed && projectGroup.classList.contains('collapsed')) {
                        this.toggleProject(projectGroup);
                    }
                }
            });
        } catch (e) {
            console.warn('Failed to load project states:', e);
        }
    }
    
    /**
     * Filter projects and activities
     */
    filterProjects(searchTerm) {
        const term = searchTerm.toLowerCase().trim();
        
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const projectName = projectGroup.querySelector('.project-name').textContent.toLowerCase();
            const activities = projectGroup.querySelectorAll('.activity-block');
            
            let projectMatches = projectName.includes(term);
            let hasVisibleActivitys = false;
            
            // Check activities
            activities.forEach(activity => {
                const activityName = activity.dataset.activityName.toLowerCase();
                const activityMatches = activityName.includes(term);
                
                if (term === '' || activityMatches || projectMatches) {
                    activity.style.display = '';
                    hasVisibleActivitys = true;
                } else {
                    activity.style.display = 'none';
                }
            });
            
            // Show/hide project based on matches
            if (term === '' || projectMatches || hasVisibleActivitys) {
                projectGroup.style.display = '';
                // Expand project if it has matching activities
                if (hasVisibleActivitys && term !== '' && projectGroup.classList.contains('collapsed')) {
                    this.toggleProject(projectGroup);
                }
            } else {
                projectGroup.style.display = 'none';
            }
        });
    }
    
    /**
     * Clear project filter
     */
    clearFilter() {
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            projectGroup.style.display = '';
            projectGroup.querySelectorAll('.activity-block').forEach(activity => {
                activity.style.display = '';
            });
        });
    }
    
    /**
     * Get project statistics
     */
    getProjectStats() {
        const stats = {
            totalProjects: 0,
            totalActivitys: 0,
            projectsWithActivitys: 0,
            averageActivitysPerProject: 0
        };
        
        const projectGroups = document.querySelectorAll('.project-group');
        stats.totalProjects = projectGroups.length;
        
        projectGroups.forEach(projectGroup => {
            const activities = projectGroup.querySelectorAll('.activity-block');
            const activityCount = activities.length;
            
            stats.totalActivitys += activityCount;
            if (activityCount > 0) {
                stats.projectsWithActivitys++;
            }
        });
        
        if (stats.totalProjects > 0) {
            stats.averageActivitysPerProject = Math.round(stats.totalActivitys / stats.totalProjects * 10) / 10;
        }
        
        return stats;
    }
    
    /**
     * Highlight project and activity
     */
    highlightProjectActivity(projectId, activityId) {
        // Clear existing highlights
        this.clearHighlights();
        
        // Highlight project
        const projectGroup = document.querySelector(`[data-project="${projectId}"]`);
        if (projectGroup) {
            projectGroup.classList.add('highlighted');
            
            // Expand project if collapsed
            if (projectGroup.classList.contains('collapsed')) {
                this.toggleProject(projectGroup);
            }
            
            // Highlight activity
            if (activityId) {
                const activityBlock = projectGroup.querySelector(`[data-activity="${activityId}"]`);
                if (activityBlock) {
                    activityBlock.classList.add('highlighted');
                    
                    // Scroll activity into view
                    DOMUtils.scrollIntoView(activityBlock, { block: 'nearest' });
                }
            }
        }
    }
    
    /**
     * Clear all highlights
     */
    clearHighlights() {
        document.querySelectorAll('.highlighted').forEach(element => {
            element.classList.remove('highlighted');
        });
    }
    
    /**
     * Get project color
     */
    getProjectColor(projectId) {
        const projectGroup = document.querySelector(`[data-project="${projectId}"]`);
        if (projectGroup) {
            const colorElement = projectGroup.querySelector('.project-color');
            if (colorElement) {
                return getComputedStyle(colorElement).backgroundColor;
            }
        }
        return '#6b7280'; // Default color
    }
    
    /**
     * Get project name
     */
    getProjectName(projectId) {
        const projectGroup = document.querySelector(`[data-project="${projectId}"]`);
        if (projectGroup) {
            const nameElement = projectGroup.querySelector('.project-name');
            if (nameElement) {
                return nameElement.textContent;
            }
        }
        return projectId;
    }
    
    /**
     * Get activity name
     */
    getActivityName(projectId, activityId) {
        const projectGroup = document.querySelector(`[data-project="${projectId}"]`);
        if (projectGroup) {
            const activityBlock = projectGroup.querySelector(`[data-activity="${activityId}"]`);
            if (activityBlock) {
                return activityBlock.dataset.activityName;
            }
        }
        return activityId;
    }
    
    /**
     * Get all projects and activities data
     */
    getProjectsData() {
        const projects = [];
        
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            const projectId = projectGroup.dataset.project;
            const projectName = this.getProjectName(projectId);
            const projectColor = this.getProjectColor(projectId);
            
            const activities = [];
            projectGroup.querySelectorAll('.activity-block').forEach(activityBlock => {
                activities.push({
                    id: activityBlock.dataset.activity,
                    name: activityBlock.dataset.activityName,
                    priority: activityBlock.querySelector('.activity-priority')?.textContent || null
                });
            });
            
            projects.push({
                id: projectId,
                name: projectName,
                color: projectColor,
                activities: activities,
                isCollapsed: projectGroup.classList.contains('collapsed')
            });
        });
        
        return projects;
    }
    
    /**
     * Show project context menu
     */
    showProjectContextMenu(projectGroup, event) {
        event.preventDefault();
        event.stopPropagation();
        
        const projectId = projectGroup.dataset.project;
        const projectName = this.getProjectName(projectId);
        
        const menuItems = [
            {
                text: 'Expand All Activitys',
                icon: '📂',
                action: () => {
                    if (projectGroup.classList.contains('collapsed')) {
                        this.toggleProject(projectGroup);
                    }
                }
            },
            {
                text: 'Collapse Activitys',
                icon: '📁',
                action: () => {
                    if (!projectGroup.classList.contains('collapsed')) {
                        this.toggleProject(projectGroup);
                    }
                }
            },
            {
                text: 'Highlight in Calendar',
                icon: '🔍',
                action: () => {
                    this.highlightProjectInCalendar(projectId);
                }
            }
        ];
        
        this.app.components.contextMenu.show(event.pageX, event.pageY, menuItems);
    }
    
    /**
     * Highlight project entries in calendar
     */
    highlightProjectInCalendar(projectId) {
        // Clear existing highlights
        document.querySelectorAll('.time-block.project-highlighted').forEach(block => {
            block.classList.remove('project-highlighted');
        });
        
        // Highlight time blocks for this project
        document.querySelectorAll(`.time-block[data-project="${projectId}"]`).forEach(block => {
            block.classList.add('project-highlighted');
        });
        
        // Auto-remove highlight after delay
        setTimeout(() => {
            document.querySelectorAll('.time-block.project-highlighted').forEach(block => {
                block.classList.remove('project-highlighted');
            });
        }, 3000);
        
        this.app.components.toast.info(`Highlighted ${this.getProjectName(projectId)} entries in calendar`);
    }
    
    /**
     * Initialize sidebar after DOM is ready
     */
    initializeAfterLoad() {
        // Setup any additional functionality that requires full DOM
        this.setupProjectContextMenus();
        
        // Setup new features - do this BEFORE loading saved states
        this.enhanceProjectToggles();
        this.addPinButtons();
        this.reorganizeActivitys();
        
        // Load saved project states LAST (this will override the default collapsed state for previously expanded projects)
        // Comment this out to always start collapsed
        // this.loadProjectStates();
    }
    
    /**
     * Refresh projects from API data (for admin user switching)
     */
    refreshProjectsFromAPI() {
        if (!this.app.state.projectsData) {
            console.warn('No projects data available to refresh');
            return;
        }
        
        // Clear existing projects from sidebar
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar) return;
        
        // Remove all existing project groups
        sidebar.querySelectorAll('.project-group').forEach(group => group.remove());
        
        // Recreate projects from API data
        Object.entries(this.app.state.projectsData).forEach(([projectId, projectData]) => {
            this.createProjectGroup(projectId, projectData);
        });
        
        // Re-initialize sidebar features
        this.enhanceProjectToggles();
        this.addPinButtons();
        this.reorganizeActivitys();
    }
    
    /**
     * Create a project group element from API data
     */
    createProjectGroup(projectId, projectData) {
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar) return;
        
        const projectGroup = document.createElement('div');
        projectGroup.className = 'project-group';
        projectGroup.dataset.project = projectId;
        
        // Create project header
        const projectHeader = document.createElement('div');
        projectHeader.className = 'project-header';
        projectHeader.onclick = () => window.toggleProject(projectId);
        
        // Project color (use existing color or generate new one)
        const projectColor = this.app.state.projectColors[projectId] || this.generateProjectColor();
        const colorDiv = document.createElement('div');
        colorDiv.className = 'project-color';
        colorDiv.style.backgroundColor = projectColor;
        
        // Project name
        const nameDiv = document.createElement('div');
        nameDiv.className = 'project-name';
        nameDiv.textContent = projectData.project_name;
        
        // Project toggle
        const toggleDiv = document.createElement('div');
        toggleDiv.className = 'project-toggle';
        toggleDiv.textContent = '▼';
        
        projectHeader.appendChild(colorDiv);
        projectHeader.appendChild(nameDiv);
        projectHeader.appendChild(toggleDiv);
        
        // Create activity list
        const activityList = document.createElement('div');
        activityList.className = 'activity-list';
        
        // Add activities
        if (projectData.activities && projectData.activities.length > 0) {
            projectData.activities.forEach(activity => {
                const activityBlock = this.createActivityBlock(projectId, projectData, activity, projectColor);
                projectGroup.appendChild(activityBlock);
            });
        }
        
        projectGroup.appendChild(projectHeader);
        projectGroup.appendChild(activityList);
        
        // Insert before search container or at the end
        const searchContainer = sidebar.querySelector('.search-container');
        if (searchContainer && searchContainer.nextSibling) {
            sidebar.insertBefore(projectGroup, searchContainer.nextSibling);
        } else {
            sidebar.appendChild(projectGroup);
        }
    }
    
    /**
     * Create an activity block element
     */
    createActivityBlock(projectId, projectData, activity, projectColor) {
        const activityBlock = document.createElement('div');
        activityBlock.className = 'activity-block';
        activityBlock.draggable = true;
        activityBlock.dataset.project = projectId;
        activityBlock.dataset.activity = activity.name;
        activityBlock.dataset.projectName = projectData.project_name;
        activityBlock.dataset.activityName = activity.subject;
        activityBlock.dataset.color = projectColor;
        
        // Activity icon
        const iconDiv = document.createElement('div');
        iconDiv.className = 'activity-icon';
        iconDiv.style.backgroundColor = projectColor;
        
        // Activity name
        const nameDiv = document.createElement('div');
        nameDiv.className = 'activity-name';
        nameDiv.textContent = activity.subject;
        
        activityBlock.appendChild(iconDiv);
        activityBlock.appendChild(nameDiv);
        
        // Add drag event listeners
        activityBlock.addEventListener('dragstart', (e) => {
            activityBlock.classList.add('dragging');
            const activityData = {
                project: projectId,
                activity: activity.name,
                projectName: projectData.project_name,
                activityName: activity.subject,
                color: projectColor,
                isExistingBlock: false
            };
            e.dataTransfer.setData('text/plain', JSON.stringify(activityData));
            e.dataTransfer.effectAllowed = 'copy';
        });
        
        activityBlock.addEventListener('dragend', () => {
            activityBlock.classList.remove('dragging');
        });
        
        return activityBlock;
    }
    
    /**
     * Generate a project color
     */
    generateProjectColor() {
        const colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#84CC16', '#F97316'];
        return colors[Math.floor(Math.random() * colors.length)];
    }
    
    /**
     * Setup context menus for projects
     */
    setupProjectContextMenus() {
        document.querySelectorAll('.project-group').forEach(projectGroup => {
            projectGroup.addEventListener('contextmenu', (e) => {
                this.showProjectContextMenu(projectGroup, e);
            });
        });
    }
}

// Export to global scope
window.SidebarComponent = SidebarComponent;

// Setup global function for HTML compatibility
window.toggleProject = function(projectName) {
    if (window.app && window.app.components.sidebar) {
        window.app.components.sidebar.toggleProjectByName(projectName);
    }
};
