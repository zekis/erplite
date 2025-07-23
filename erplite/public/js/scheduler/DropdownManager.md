# DropdownManager.js Documentation

## Overview
Handles all dropdown functionality with professional styling, filtering, and icons. Provides interactive dropdowns for selecting projects, activities, roles, and resources in the scheduler.

## Class: DropdownManager

### Constructor
```javascript
constructor(schedulerApp)
```
Initializes the dropdown manager with reference to the main scheduler app.

**Properties:**
- `app`: Reference to the main SchedulerApp instance
- `activeDropdown`: Currently active dropdown reference
- `boundHandleOutsideClick`: Bound outside click handler for cleanup

### Core Dropdown Methods

#### `showProjectDropdown(cell, rowIndex)`
Shows project selection dropdown with:
- Search functionality
- Project list with color indicators
- Project status display
- Click handlers for selection

**Features:**
- Color-coded project indicators
- Status badges (Active, Open, etc.)
- Search filtering
- Keyboard navigation support

#### `showActivityDropdown(cell, rowIndex)`
Shows activity selection dropdown with:
- Project context header
- Search functionality
- Activity list with priority badges
- Status indicators

**Requirements:**
- Project must be selected first
- Shows activities only for the selected project

**Features:**
- Context header showing selected project
- Priority badges (High, Medium, Low)
- Status indicators (Open, Completed, etc.)
- Search filtering

#### `showRoleDropdown(cell, rowIndex)`
Shows role selection dropdown with:
- "Any Role" option
- Search functionality
- Role list with descriptions
- Icon indicators

**Features:**
- Default "Any Role" option for flexible assignments
- Role descriptions and titles
- Icon-based visual indicators
- Search filtering

#### `showResourceDropdown(cell, rowIndex)`
Shows resource selection dropdown with:
- "Unassigned" option
- Resource avatars with initials
- Type filtering (People, Equipment, etc.)
- Availability indicators
- Search functionality

**Features:**
- Resource avatars with color-coded initials
- Resource type filtering buttons
- Availability status indicators
- Search and filter capabilities

### Dropdown Creation Methods

#### `createDropdown(type, cell)`
Creates base dropdown element with:
- Proper CSS classes
- Type-specific styling
- Reference storage for cleanup

#### `createSearchInput(placeholder)`
Creates search input with:
- Search icon
- Placeholder text
- Input field for filtering

#### `createProjectItem(project, rowIndex)`
Creates project dropdown item with:
- Project color indicator
- Project name and status
- Click handler for selection

#### `createActivityItem(activity, rowIndex)`
Creates activity dropdown item with:
- Activity icon
- Activity name and status
- Priority badge
- Click handler for selection

#### `createRoleItem(role, rowIndex)`
Creates role dropdown item with:
- Role icon
- Role name and description
- Click handler for selection
- Special handling for "Any Role" option

#### `createResourceItem(resource, rowIndex)`
Creates resource dropdown item with:
- Resource avatar
- Resource name and type
- Availability indicator
- Click handler for selection
- Special handling for "Unassigned" option

### Avatar and Visual Elements

#### `createResourceAvatar(resource)`
Creates resource avatar by delegating to ResourceUtils.

**Delegates to:** `ResourceUtils.createResourceAvatar(resource)`

**See:** [ResourceUtils.md](../utils/ResourceUtils.md#createResourceAvatar) for avatar creation details

#### `getAvailabilityStatus(resource)`
Determines resource availability status:
- Available, Busy, Away states
- Visual indicators
- Status-based styling

### Filtering and Search

#### `createResourceFilters()`
Creates filter buttons for resources:
- All resources
- People only
- Equipment only
- Available only

#### `setupSearch(searchInput, listContainer, type)`
Sets up search functionality:
- Real-time filtering
- Case-insensitive search
- Keyboard navigation support
- No results messaging

#### `setupResourceFilters(filtersContainer, listContainer)`
Sets up resource filter functionality:
- Filter button activation
- Type-based filtering
- Combined search and filter support

#### `handleKeyboardNavigation(e, listContainer)`
Handles keyboard navigation in dropdowns:
- Arrow key navigation
- Enter key selection
- Escape key closing
- Focus management

#### `updateNoResultsMessage(listContainer, searchTerm)`
Updates no results message display:
- Shows when no items match search
- Hides when results are available
- Search term highlighting

### Positioning and Display

#### `positionDropdown(dropdown, cell)`
Positions dropdown relative to cell:
- Fixed positioning
- Viewport boundary checking
- Z-index management
- Minimum width enforcement

#### `adjustDropdownPosition(dropdown)`
Adjusts dropdown position if off-screen:
- Horizontal overflow handling
- Vertical overflow handling
- Viewport boundary respect

#### `setupOutsideClickHandler()`
Sets up outside click detection:
- Document-level click listener
- Delayed attachment for proper event handling
- Cleanup on dropdown close

### Event Handling

#### `handleOutsideClick(event)`
Handles clicks outside dropdown:
- Closes active dropdown
- Ignores clicks on dropdown elements
- Ignores clicks on trigger cells

#### `hideAllDropdowns()`
Hides all open dropdowns:
- Removes dropdown elements from DOM
- Cleans up event listeners
- Resets active dropdown reference

### Cleanup

#### `cleanup()`
Cleans up dropdown manager:
- Hides all dropdowns
- Removes event listeners
- Clears references

## Usage Examples

### Basic Dropdown Usage
```javascript
// Show project dropdown
dropdownManager.showProjectDropdown(cell, rowIndex);

// Show activity dropdown (requires project selection)
dropdownManager.showActivityDropdown(cell, rowIndex);

// Show role dropdown
dropdownManager.showRoleDropdown(cell, rowIndex);

// Show resource dropdown
dropdownManager.showResourceDropdown(cell, rowIndex);
```

### Event Handling
```javascript
// Hide all dropdowns
dropdownManager.hideAllDropdowns();

// Handle outside clicks
document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown-menu')) {
        dropdownManager.hideAllDropdowns();
    }
});
```

## CSS Classes Used

### Dropdown Structure
- `.dropdown-menu`: Main dropdown container
- `.dropdown-search`: Search input container
- `.dropdown-list`: Items list container
- `.dropdown-item`: Individual dropdown item
- `.dropdown-separator`: Visual separator between sections

### Item Types
- `.project-item`: Project dropdown item
- `.activity-item`: Activity dropdown item
- `.role-item`: Role dropdown item
- `.resource-item`: Resource dropdown item

### Visual Elements
- `.project-color-indicator`: Project color dot
- `.resource-avatar`: Resource avatar circle
- `.priority-badge`: Activity priority indicator
- `.availability-indicator`: Resource availability status

### Interactive States
- `.keyboard-focused`: Keyboard navigation focus
- `.no-results-message`: No search results display
- `.filter-button`: Resource filter buttons
- `.active`: Active filter button state

## Dependencies
- SchedulerApp: Main application reference
- Material Design Icons: Icon classes (mdi-*)
- CSS: Dropdown styling and animations

## Integration
The DropdownManager is instantiated by the main SchedulerApp and handles all dropdown interactions. It communicates back to the app through selection methods and maintains its own state for active dropdowns and event handling.
