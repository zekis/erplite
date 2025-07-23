/**
 * Dropdown Manager
 * Handles all dropdown functionality with professional styling, filtering, and icons
 */
class DropdownManager {
    constructor(schedulerApp) {
        this.app = schedulerApp;
        this.activeDropdown = null;
        this.boundHandleOutsideClick = null;
    }

    /**
     * Show project dropdown with search and filtering
     */
    showProjectDropdown(cell, rowIndex) {
        // Check if dropdown is already open for this cell
        if (this.activeDropdown && this.activeDropdown.cell === cell) {
            this.hideAllDropdowns();
            return;
        }

        this.hideAllDropdowns();

        const dropdown = this.createDropdown('project', cell);
        
        // Add search input
        const searchInput = this.createSearchInput('Search projects...');
        dropdown.appendChild(searchInput);

        // Add projects list
        const projectsList = document.createElement('div');
        projectsList.className = 'dropdown-list';
        
        this.app.state.projects.forEach(project => {
            const item = this.createProjectItem(project, rowIndex);
            projectsList.appendChild(item);
        });

        dropdown.appendChild(projectsList);
        
        // Position and show dropdown
        this.positionDropdown(dropdown, cell);
        
        // Setup search functionality
        this.setupSearch(searchInput, projectsList, 'project');
        
        // Focus search input
        setTimeout(() => searchInput.focus(), 100);
    }

    /**
     * Show activity dropdown with search and project context
     */
    showActivityDropdown(cell, rowIndex) {
        const row = this.app.state.scheduleRows[rowIndex];
        if (!row.project) return;

        // Check if dropdown is already open for this cell
        if (this.activeDropdown && this.activeDropdown.cell === cell) {
            this.hideAllDropdowns();
            return;
        }

        this.hideAllDropdowns();

        const dropdown = this.createDropdown('activity', cell);
        
        // Add project context header
        const project = this.app.state.projects.find(p => p.name === row.project);
        if (project) {
            const contextHeader = document.createElement('div');
            contextHeader.className = 'dropdown-context-header';
            contextHeader.innerHTML = `
                <div class="context-project">
                    <i class="mdi mdi-folder-outline"></i>
                    <span>${project.project_name}</span>
                </div>
            `;
            dropdown.appendChild(contextHeader);
        }

        // Add search input
        const searchInput = this.createSearchInput('Search activities...');
        dropdown.appendChild(searchInput);

        // Add activities list
        const activitiesList = document.createElement('div');
        activitiesList.className = 'dropdown-list';
        
        if (project && project.activities) {
            project.activities.forEach(activity => {
                const item = this.createActivityItem(activity, rowIndex);
                activitiesList.appendChild(item);
            });
        }

        dropdown.appendChild(activitiesList);
        
        // Position and show dropdown
        this.positionDropdown(dropdown, cell);
        
        // Setup search functionality
        this.setupSearch(searchInput, activitiesList, 'activity');
        
        // Focus search input
        setTimeout(() => searchInput.focus(), 100);
    }

    /**
     * Show role dropdown with search and icons
     */
    showRoleDropdown(cell, rowIndex) {
        // Check if dropdown is already open for this cell
        if (this.activeDropdown && this.activeDropdown.cell === cell) {
            this.hideAllDropdowns();
            return;
        }

        this.hideAllDropdowns();

        const dropdown = this.createDropdown('role', cell);
        
        // Add search input
        const searchInput = this.createSearchInput('Search roles...');
        dropdown.appendChild(searchInput);

        // Add roles list
        const rolesList = document.createElement('div');
        rolesList.className = 'dropdown-list';
        
        // Add "Any Role" option
        const anyRoleItem = this.createRoleItem(null, rowIndex);
        rolesList.appendChild(anyRoleItem);

        // Add separator
        const separator = document.createElement('div');
        separator.className = 'dropdown-separator';
        rolesList.appendChild(separator);
        
        // Add roles from state
        this.app.state.roles.forEach(role => {
            const item = this.createRoleItem(role, rowIndex);
            rolesList.appendChild(item);
        });

        dropdown.appendChild(rolesList);
        
        // Position and show dropdown
        this.positionDropdown(dropdown, cell);
        
        // Setup search functionality
        this.setupSearch(searchInput, rolesList, 'role');
        
        // Focus search input
        setTimeout(() => searchInput.focus(), 100);
    }

    /**
     * Show resource dropdown with search, avatars, and filtering
     */
    showResourceDropdown(cell, rowIndex) {
        console.log('showResourceDropdown called', { cell, rowIndex, resources: this.app.state.resources });
        
        // Check if dropdown is already open for this cell
        if (this.activeDropdown && this.activeDropdown.cell === cell) {
            this.hideAllDropdowns();
            return;
        }

        this.hideAllDropdowns();

        const dropdown = this.createDropdown('resource', cell);
        
        // Add search input
        const searchInput = this.createSearchInput('Search resources...');
        dropdown.appendChild(searchInput);

        // Add filter buttons
        const filterButtons = this.createResourceFilters();
        dropdown.appendChild(filterButtons);

        // Add resources list
        const resourcesList = document.createElement('div');
        resourcesList.className = 'dropdown-list';
        
        // Add "Unassigned" option
        const unassignedItem = this.createResourceItem(null, rowIndex);
        resourcesList.appendChild(unassignedItem);

        // Add separator
        const separator = document.createElement('div');
        separator.className = 'dropdown-separator';
        resourcesList.appendChild(separator);
        
        // Add resources from state with error handling
        if (this.app.state.resources && Array.isArray(this.app.state.resources)) {
            console.log('Adding resources to dropdown:', this.app.state.resources.length);
            this.app.state.resources.forEach(resource => {
                const item = this.createResourceItem(resource, rowIndex);
                resourcesList.appendChild(item);
            });
        } else {
            console.warn('No resources available or resources is not an array:', this.app.state.resources);
        }

        dropdown.appendChild(resourcesList);
        
        console.log('Dropdown created, positioning...', dropdown);
        
        // Position and show dropdown
        this.positionDropdown(dropdown, cell);
        
        console.log('Dropdown positioned and added to DOM');
        
        // Setup search functionality
        this.setupSearch(searchInput, resourcesList, 'resource');
        
        // Setup filter functionality
        this.setupResourceFilters(filterButtons, resourcesList);
        
        // Focus search input
        setTimeout(() => {
            const input = searchInput.querySelector('.dropdown-search-input');
            if (input) input.focus();
        }, 100);
    }

    /**
     * Create base dropdown element
     */
    createDropdown(type, cell) {
        const dropdown = document.createElement('div');
        dropdown.className = `dropdown-menu dropdown-${type}`;
        dropdown.id = `${type}Dropdown`;
        
        // Store reference for cleanup
        this.activeDropdown = { dropdown, cell, type };
        
        return dropdown;
    }

    /**
     * Create search input
     */
    createSearchInput(placeholder) {
        const searchContainer = document.createElement('div');
        searchContainer.className = 'dropdown-search';
        
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'dropdown-search-input';
        searchInput.placeholder = placeholder;
        
        const searchIcon = document.createElement('i');
        searchIcon.className = 'mdi mdi-magnify dropdown-search-icon';
        
        searchContainer.appendChild(searchIcon);
        searchContainer.appendChild(searchInput);
        
        return searchContainer;
    }

    /**
     * Create project dropdown item
     */
    createProjectItem(project, rowIndex) {
        const item = document.createElement('div');
        item.className = 'dropdown-item project-item';
        item.dataset.searchText = project.project_name.toLowerCase();
        
        // Get project color
        const projectColor = this.app.state.projectColors[project.name] || '#6b7280';
        
        item.innerHTML = `
            <div class="item-icon">
                <div class="project-color-indicator" style="background-color: ${projectColor}"></div>
            </div>
            <div class="item-content">
                <div class="item-title">${project.project_name}</div>
                <div class="item-subtitle">${project.status || 'Active'}</div>
            </div>
            <div class="item-meta">
                <i class="mdi mdi-folder-outline"></i>
            </div>
        `;
        
        item.addEventListener('click', () => {
            this.app.selectProject(rowIndex, project);
            this.hideAllDropdowns();
        });
        
        return item;
    }

    /**
     * Create activity dropdown item
     */
    createActivityItem(activity, rowIndex) {
        const item = document.createElement('div');
        item.className = 'dropdown-item activity-item';
        item.dataset.searchText = activity.subject.toLowerCase();
        
        item.innerHTML = `
            <div class="item-icon">
                <i class="mdi mdi-clipboard-text-outline"></i>
            </div>
            <div class="item-content">
                <div class="item-title">${activity.subject}</div>
                <div class="item-subtitle">${activity.status || 'Open'}</div>
            </div>
            <div class="item-meta">
                <span class="priority-badge ${(activity.priority || 'medium').toLowerCase()}">${activity.priority || 'Medium'}</span>
            </div>
        `;
        
        item.addEventListener('click', () => {
            this.app.selectActivity(rowIndex, activity);
            this.hideAllDropdowns();
        });
        
        return item;
    }

    /**
     * Create role dropdown item
     */
    createRoleItem(role, rowIndex) {
        const item = document.createElement('div');
        item.className = 'dropdown-item role-item';
        
        if (role) {
            // Handle different possible role data structures
            const roleName = role.role_name || role.name || role.title || 'Unknown Role';
            const roleDescription = role.description || role.role_description || 'Role';
            
            item.dataset.searchText = roleName.toLowerCase();
            item.innerHTML = `
                <div class="item-icon">
                    <i class="mdi mdi-account-tie"></i>
                </div>
                <div class="item-content">
                    <div class="item-title">${roleName}</div>
                    <div class="item-subtitle">${roleDescription}</div>
                </div>
            `;
        } else {
            item.dataset.searchText = 'any role';
            item.innerHTML = `
                <div class="item-icon">
                    <i class="mdi mdi-account-multiple-outline"></i>
                </div>
                <div class="item-content">
                    <div class="item-title">Any Role</div>
                    <div class="item-subtitle">No specific role required</div>
                </div>
            `;
        }
        
        item.addEventListener('click', () => {
            this.app.selectRole(rowIndex, role);
            this.hideAllDropdowns();
        });
        
        return item;
    }

    /**
     * Create resource dropdown item with avatar
     */
    createResourceItem(resource, rowIndex) {
        const item = document.createElement('div');
        item.className = 'dropdown-item resource-item';
        
        if (resource) {
            item.dataset.searchText = resource.resource_name.toLowerCase();
            item.dataset.resourceType = resource.resource_type || 'person';
            
            // Create avatar
            const avatar = this.createResourceAvatar(resource);
            
            item.innerHTML = `
                <div class="item-icon">
                    ${avatar}
                </div>
                <div class="item-content">
                    <div class="item-title">${resource.resource_name}</div>
                    <div class="item-subtitle">${resource.resource_type || 'Person'}</div>
                </div>
                <div class="item-meta">
                    <div class="availability-indicator ${this.getAvailabilityStatus(resource)}"></div>
                </div>
            `;
        } else {
            item.dataset.searchText = 'unassigned';
            item.dataset.resourceType = 'unassigned';
            item.innerHTML = `
                <div class="item-icon">
                    <i class="mdi mdi-account-off-outline"></i>
                </div>
                <div class="item-content">
                    <div class="item-title">Unassigned</div>
                    <div class="item-subtitle">No resource assigned</div>
                </div>
            `;
        }
        
        item.addEventListener('click', () => {
            this.app.selectPerson(rowIndex, resource);
            this.hideAllDropdowns();
        });
        
        return item;
    }

    /**
     * Create resource avatar - delegates to ResourceUtils
     */
    createResourceAvatar(resource) {
        return ResourceUtils.createResourceAvatar(resource);
    }

    /**
     * Get availability status for resource
     */
    getAvailabilityStatus(resource) {
        // This would typically check against actual availability data
        // For now, return a random status for demo purposes
        const statuses = ['available', 'busy', 'away'];
        return statuses[Math.floor(Math.random() * statuses.length)];
    }

    /**
     * Create resource filter buttons
     */
    createResourceFilters() {
        const filtersContainer = document.createElement('div');
        filtersContainer.className = 'dropdown-filters';
        
        const filters = [
            { key: 'all', label: 'All', icon: 'account-group' },
            { key: 'person', label: 'People', icon: 'account' },
            { key: 'equipment', label: 'Equipment', icon: 'tools' },
            { key: 'available', label: 'Available', icon: 'check-circle' }
        ];
        
        filters.forEach(filter => {
            const button = document.createElement('button');
            button.className = 'filter-button';
            button.dataset.filter = filter.key;
            if (filter.key === 'all') button.classList.add('active');
            
            button.innerHTML = `
                <i class="mdi mdi-${filter.icon}"></i>
                <span>${filter.label}</span>
            `;
            
            filtersContainer.appendChild(button);
        });
        
        return filtersContainer;
    }

    /**
     * Setup search functionality
     */
    setupSearch(searchInput, listContainer, type) {
        const input = searchInput.querySelector('.dropdown-search-input');
        
        input.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const items = listContainer.querySelectorAll('.dropdown-item');
            
            items.forEach(item => {
                const searchText = item.dataset.searchText || '';
                const matches = searchText.includes(searchTerm);
                item.style.display = matches ? 'flex' : 'none';
            });
            
            // Show "no results" message if needed
            this.updateNoResultsMessage(listContainer, searchTerm);
        });
        
        // Handle keyboard navigation
        input.addEventListener('keydown', (e) => {
            this.handleKeyboardNavigation(e, listContainer);
        });
    }

    /**
     * Setup resource filter functionality
     */
    setupResourceFilters(filtersContainer, listContainer) {
        const filterButtons = filtersContainer.querySelectorAll('.filter-button');
        
        filterButtons.forEach(button => {
            button.addEventListener('click', () => {
                // Update active filter
                filterButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                const filterType = button.dataset.filter;
                const items = listContainer.querySelectorAll('.dropdown-item');
                
                items.forEach(item => {
                    let show = true;
                    
                    if (filterType !== 'all') {
                        if (filterType === 'available') {
                            const indicator = item.querySelector('.availability-indicator');
                            show = indicator && indicator.classList.contains('available');
                        } else if (filterType === 'person') {
                            // Show items that are people/persons or unassigned
                            const resourceType = (item.dataset.resourceType || '').toLowerCase();
                            show = resourceType === 'person' || resourceType === 'people' || 
                                   resourceType === 'human' || resourceType === 'employee' || 
                                   resourceType === 'staff' || resourceType === 'unassigned' || 
                                   resourceType === '';
                        } else if (filterType === 'equipment') {
                            // Show items that are equipment, tools, machines, vehicles, etc.
                            const resourceType = (item.dataset.resourceType || '').toLowerCase();
                            show = resourceType === 'equipment' || resourceType === 'tool' || 
                                   resourceType === 'machine' || resourceType === 'vehicle' || 
                                   resourceType === 'asset' || resourceType === 'material';
                        } else {
                            // Exact match for other filter types
                            show = (item.dataset.resourceType || '').toLowerCase() === filterType.toLowerCase();
                        }
                    }
                    
                    item.style.display = show ? 'flex' : 'none';
                });
                
                // Update no results message after filtering
                this.updateNoResultsMessage(listContainer, '');
            });
        });
    }

    /**
     * Handle keyboard navigation in dropdown
     */
    handleKeyboardNavigation(e, listContainer) {
        const visibleItems = Array.from(listContainer.querySelectorAll('.dropdown-item'))
            .filter(item => item.style.display !== 'none');
        
        if (visibleItems.length === 0) return;
        
        const currentFocused = listContainer.querySelector('.dropdown-item.keyboard-focused');
        let newIndex = 0;
        
        if (currentFocused) {
            const currentIndex = visibleItems.indexOf(currentFocused);
            currentFocused.classList.remove('keyboard-focused');
            
            if (e.key === 'ArrowDown') {
                newIndex = (currentIndex + 1) % visibleItems.length;
            } else if (e.key === 'ArrowUp') {
                newIndex = currentIndex > 0 ? currentIndex - 1 : visibleItems.length - 1;
            } else if (e.key === 'Enter') {
                e.preventDefault();
                currentFocused.click();
                return;
            } else {
                return;
            }
        } else if (e.key === 'ArrowDown') {
            newIndex = 0;
        } else {
            return;
        }
        
        e.preventDefault();
        visibleItems[newIndex].classList.add('keyboard-focused');
        visibleItems[newIndex].scrollIntoView({ block: 'nearest' });
    }

    /**
     * Update no results message
     */
    updateNoResultsMessage(listContainer, searchTerm) {
        let noResultsMsg = listContainer.querySelector('.no-results-message');
        const visibleItems = Array.from(listContainer.querySelectorAll('.dropdown-item'))
            .filter(item => item.style.display !== 'none');
        
        if (visibleItems.length === 0 && searchTerm) {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.className = 'no-results-message';
                listContainer.appendChild(noResultsMsg);
            }
            noResultsMsg.innerHTML = `
                <i class="mdi mdi-magnify"></i>
                <span>No results found for "${searchTerm}"</span>
            `;
            noResultsMsg.style.display = 'flex';
        } else if (noResultsMsg) {
            noResultsMsg.style.display = 'none';
        }
    }

    /**
     * Position dropdown relative to cell
     */
    positionDropdown(dropdown, cell) {
        const rect = cell.getBoundingClientRect();
        dropdown.style.position = 'fixed';
        dropdown.style.top = `${rect.bottom + 5}px`;
        dropdown.style.left = `${rect.left}px`;
        dropdown.style.minWidth = `${Math.max(rect.width, 280)}px`;
        dropdown.style.maxWidth = '400px';
        dropdown.style.zIndex = '10000';
        
        
        // Append to body to avoid clipping
        document.body.appendChild(dropdown);
        
        console.log('Dropdown added to body, checking if visible...', {
            position: dropdown.style.position,
            top: dropdown.style.top,
            left: dropdown.style.left,
            zIndex: dropdown.style.zIndex,
            display: dropdown.style.display,
            visibility: dropdown.style.visibility,
            opacity: dropdown.style.opacity,
            width: dropdown.style.width,
            height: dropdown.style.height
        });
        
        // Force visibility for debugging
        dropdown.style.display = 'block';
        dropdown.style.visibility = 'visible';
        dropdown.style.opacity = '1';
        
        console.log('Dropdown forced visible, final computed styles:', {
            computedDisplay: window.getComputedStyle(dropdown).display,
            computedVisibility: window.getComputedStyle(dropdown).visibility,
            computedOpacity: window.getComputedStyle(dropdown).opacity,
            computedPosition: window.getComputedStyle(dropdown).position,
            computedZIndex: window.getComputedStyle(dropdown).zIndex,
            boundingRect: dropdown.getBoundingClientRect()
        });
        
        // Adjust position if dropdown goes off screen
        this.adjustDropdownPosition(dropdown);
        
        // Setup outside click handler
        this.setupOutsideClickHandler();
    }

    /**
     * Adjust dropdown position if it goes off screen
     */
    adjustDropdownPosition(dropdown) {
        const rect = dropdown.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        // Adjust horizontal position
        if (rect.right > viewportWidth) {
            dropdown.style.left = `${viewportWidth - rect.width - 10}px`;
        }
        
        // Adjust vertical position
        if (rect.bottom > viewportHeight) {
            const cell = this.activeDropdown.cell;
            const cellRect = cell.getBoundingClientRect();
            dropdown.style.top = `${cellRect.top - rect.height - 5}px`;
        }
    }

    /**
     * Setup outside click handler
     */
    setupOutsideClickHandler() {
        this.boundHandleOutsideClick = this.handleOutsideClick.bind(this);
        setTimeout(() => {
            document.addEventListener('click', this.boundHandleOutsideClick);
        }, 100);
    }

    /**
     * Handle outside click to close dropdowns
     */
    handleOutsideClick(event) {
        if (!event.target.closest('.dropdown-menu') && !event.target.closest('.schedule-cell')) {
            this.hideAllDropdowns();
        }
    }

    /**
     * Hide all dropdowns
     */
    hideAllDropdowns() {
        const dropdowns = document.querySelectorAll('.dropdown-menu');
        dropdowns.forEach(dropdown => dropdown.remove());
        
        if (this.boundHandleOutsideClick) {
            document.removeEventListener('click', this.boundHandleOutsideClick);
            this.boundHandleOutsideClick = null;
        }
        
        this.activeDropdown = null;
    }

    /**
     * Cleanup
     */
    cleanup() {
        this.hideAllDropdowns();
    }
}

// Export to global scope for HTML compatibility
window.DropdownManager = DropdownManager;
