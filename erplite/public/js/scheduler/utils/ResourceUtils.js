/**
 * Resource Utilities
 * Handles resource-related operations like avatars, colors, and icons
 */
class ResourceUtils {
    /**
     * Color palette for resource avatars
     */
    static AVATAR_COLORS = [
        '#3b82f6', '#ef4444', '#10b981', '#f59e0b',
        '#8b5cf6', '#06b6d4', '#84cc16', '#f97316',
        '#ec4899', '#6366f1', '#14b8a6', '#eab308'
    ];

    /**
     * Resource type to icon mapping
     */
    static RESOURCE_TYPE_ICONS = {
        'person': 'mdi-account',
        'people': 'mdi-account',
        'human': 'mdi-account',
        'employee': 'mdi-account',
        'staff': 'mdi-account',
        'equipment': 'mdi-tools',
        'tool': 'mdi-tools',
        'machine': 'mdi-cog',
        'vehicle': 'mdi-car',
        'room': 'mdi-door',
        'space': 'mdi-map-marker',
        'location': 'mdi-map-marker',
        'asset': 'mdi-package-variant',
        'material': 'mdi-package-variant',
        'resource': 'mdi-cube-outline'
    };

    /**
     * Create resource avatar with initials and background color
     * @param {Object} resource - Resource object with resource_name
     * @param {number} size - Avatar size in pixels (default: 24)
     * @returns {string} HTML string for avatar
     */
    static createResourceAvatar(resource, size = 24) {
        if (!resource || !resource.resource_name) {
            return ResourceUtils.createDefaultAvatar(size);
        }

        const initials = ResourceUtils.getResourceInitials(resource.resource_name);
        const backgroundColor = ResourceUtils.getResourceColor(resource.resource_name);
        
        return `
            <div class="resource-avatar" style="
                background-color: ${backgroundColor}; 
                width: ${size}px; 
                height: ${size}px; 
                border-radius: 50%; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                color: white; 
                font-weight: 600; 
                font-size: ${Math.max(8, size * 0.4)}px;
                flex-shrink: 0;
            ">
                <span class="avatar-initials">${initials}</span>
            </div>
        `;
    }

    /**
     * Create default avatar for unassigned resources
     * @param {number} size - Avatar size in pixels
     * @returns {string} HTML string for default avatar
     */
    static createDefaultAvatar(size = 24) {
        return `
            <div class="resource-avatar default" style="
                background-color: #9ca3af; 
                width: ${size}px; 
                height: ${size}px; 
                border-radius: 50%; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                color: white; 
                font-weight: 600; 
                font-size: ${Math.max(8, size * 0.4)}px;
                flex-shrink: 0;
            ">
                <i class="mdi mdi-account-off" style="font-size: ${Math.max(10, size * 0.6)}px;"></i>
            </div>
        `;
    }

    /**
     * Get initials from resource name
     * @param {string} name - Resource name
     * @returns {string} Initials (max 2 characters)
     */
    static getResourceInitials(name) {
        if (!name || typeof name !== 'string') {
            return '??';
        }

        return name
            .trim()
            .split(' ')
            .map(word => word.charAt(0))
            .join('')
            .substring(0, 2)
            .toUpperCase();
    }

    /**
     * Get consistent color for resource based on name hash
     * @param {string} name - Resource name
     * @returns {string} Hex color code
     */
    static getResourceColor(name) {
        if (!name || typeof name !== 'string') {
            return ResourceUtils.AVATAR_COLORS[0];
        }

        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        
        return ResourceUtils.AVATAR_COLORS[Math.abs(hash) % ResourceUtils.AVATAR_COLORS.length];
    }

    /**
     * Get icon class for resource type
     * @param {string} resourceType - Type of resource
     * @returns {string} Material Design Icon class
     */
    static getResourceTypeIcon(resourceType) {
        if (!resourceType || typeof resourceType !== 'string') {
            return ResourceUtils.RESOURCE_TYPE_ICONS['person'];
        }

        const normalizedType = resourceType.toLowerCase().trim();
        return ResourceUtils.RESOURCE_TYPE_ICONS[normalizedType] || ResourceUtils.RESOURCE_TYPE_ICONS['person'];
    }

    /**
     * Create resource type indicator with icon and count
     * @param {string} resourceType - Type of resource
     * @param {number} count - Number of resources of this type
     * @returns {string} HTML string for type indicator
     */
    static createResourceTypeIndicator(resourceType, count) {
        const icon = ResourceUtils.getResourceTypeIcon(resourceType);
        
        return `
            <div class="resource-type-indicator" style="
                display: flex; 
                align-items: center; 
                gap: 4px; 
                margin-right: 8px;
            ">
                <i class="mdi ${icon}" style="font-size: 14px; color: #64748b;"></i>
                <span style="font-size: 0.75rem; color: #64748b;">${count}</span>
            </div>
        `;
    }

    /**
     * Create "No Resources" indicator
     * @returns {string} HTML string for no resources indicator
     */
    static createNoResourcesIndicator() {
        return `
            <div class="no-resources-indicator" style="
                display: flex; 
                align-items: center; 
                gap: 4px;
            ">
                <i class="mdi mdi-account-off-outline" style="font-size: 14px; color: #9ca3af;"></i>
                <span style="font-size: 0.75rem; color: #9ca3af;">No Resources</span>
            </div>
        `;
    }

    /**
     * Group resources by type and count them
     * @param {Array} resources - Array of resource objects
     * @param {Array} scheduleRows - Array of schedule rows to check for resource usage
     * @param {string} projectFilter - Optional project filter
     * @returns {Object} Object with resource type counts
     */
    static groupResourcesByType(resources, scheduleRows = [], projectFilter = null) {
        const resourceTypeCounts = {};
        const uniqueResources = new Set();
        
        // Filter schedule rows if project filter is provided
        const filteredRows = projectFilter 
            ? scheduleRows.filter(r => r.project === projectFilter && r.type === 'activity-row' && r.resource)
            : scheduleRows.filter(r => r.type === 'activity-row' && r.resource);
        
        filteredRows.forEach(row => {
            if (row.resource && !uniqueResources.has(row.resource)) {
                uniqueResources.add(row.resource);
                
                // Find the resource data to get its type
                const resource = resources.find(r => r.name === row.resource);
                const resourceType = resource ? resource.resource_type || 'person' : 'person';
                
                resourceTypeCounts[resourceType] = (resourceTypeCounts[resourceType] || 0) + 1;
            }
        });
        
        return resourceTypeCounts;
    }

    /**
     * Create resource summary display for project headers
     * @param {Object} resourceTypeCounts - Object with resource type counts
     * @returns {string} HTML string for resource summary
     */
    static createResourceSummary(resourceTypeCounts) {
        if (!resourceTypeCounts || Object.keys(resourceTypeCounts).length === 0) {
            return ResourceUtils.createNoResourcesIndicator();
        }
        
        const resourceTypeElements = Object.entries(resourceTypeCounts)
            .map(([type, count]) => ResourceUtils.createResourceTypeIndicator(type, count))
            .join('');
        
        return `
            <div class="resource-summary" style="
                display: flex; 
                align-items: center; 
                flex-wrap: wrap; 
                gap: 4px;
            ">
                ${resourceTypeElements}
            </div>
        `;
    }

    /**
     * Validate resource object
     * @param {Object} resource - Resource object to validate
     * @returns {boolean} True if valid resource
     */
    static isValidResource(resource) {
        return resource && 
               typeof resource === 'object' && 
               resource.resource_name && 
               typeof resource.resource_name === 'string' &&
               resource.resource_name.trim().length > 0;
    }

    /**
     * Get resource display name
     * @param {Object} resource - Resource object
     * @returns {string} Display name for resource
     */
    static getResourceDisplayName(resource) {
        if (!ResourceUtils.isValidResource(resource)) {
            return 'Unknown Resource';
        }
        
        return resource.resource_name.trim();
    }

    /**
     * Get resource type display name
     * @param {string} resourceType - Resource type
     * @returns {string} Formatted display name for resource type
     */
    static getResourceTypeDisplayName(resourceType) {
        if (!resourceType || typeof resourceType !== 'string') {
            return 'Person';
        }
        
        // Capitalize first letter and return
        return resourceType.charAt(0).toUpperCase() + resourceType.slice(1).toLowerCase();
    }
}

// Export to global scope for HTML compatibility
window.ResourceUtils = ResourceUtils;
