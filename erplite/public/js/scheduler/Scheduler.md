# Scheduler.js Documentation

## Overview
The main Scheduler Application Controller that coordinates all components and manages application state. This is the central orchestrator for the entire scheduler system.

## Class: SchedulerApp

### Constructor
Initializes the scheduler application with default state and component managers.

**State Properties:**
- `currentStartDate`: Current start date for the schedule view
- `projects`: Array of available projects
- `resources`: Array of available resources
- `roles`: Array of available roles
- `scheduleEntries`: Array of schedule entries (legacy)
- `projectColors`: Object mapping project IDs to colors
- `scheduleRows`: Array of schedule rows with project/activity/resource combinations
- `dateRange`: Number of days to display (default: 30)
- `isLoading`: Loading state flag

**Component Managers:**
- `dataManager`: Handles API calls and data processing
- `rowManager`: Manages schedule row operations
- `dropdownManager`: Handles dropdown functionality
- `rowRenderer`: Renders schedule rows and cells
- `timeBlockManager`: Manages time block cards
- `toolbarManager`: Handles toolbar functionality

### Core Methods

#### `init()`
Initializes the application by:
- Loading initial data from window object
- Initializing toolbar manager
- Loading and rendering scheduler data

#### `loadInitialData()`
Delegates to DataManager to load initial data from window object set by template.

#### `loadSchedulerData()`
Delegates to DataManager to load scheduler data from API and renders all components on success.

#### `renderAll()`
Renders all scheduler components:
- Updates date range display
- Renders date columns header
- Renders schedule rows

#### `updateDateRange()`
Updates the date range display in the header showing start and end dates.

#### `renderDateColumns()`
Creates the date column headers with:
- Day of week abbreviation
- Month and day
- Weekend highlighting
- Today highlighting

#### `renderScheduleRows()`
Renders all schedule rows by:
- Clearing existing content
- Creating fixed left columns and scrollable right columns for each row
- Rendering time block cards after all rows are created

### Cell and Entry Management

#### `createDayCell(row, date, rowIndex)`
Creates a day cell with:
- Weekend styling
- Drag and drop event handlers
- Entry containers for time entries or project totals
- Hover effects for valid cells
- Click handlers for entry creation

#### `createScheduleEntry(entry)`
Creates a schedule entry element with:
- Project color styling
- Duration display
- Edit and delete controls
- Drag event listeners

#### `createTimeEntry(entry, date, row)`
Creates a time entry element for Schedule Row daily entries with:
- Project color styling
- Hours and time display
- Click handler for editing

### Dropdown Management

#### `showProjectDropdown(cell, rowIndex)`
Delegates to DropdownManager to show project selection dropdown.

#### `showActivityDropdown(cell, rowIndex)`
Delegates to DropdownManager to show activity selection dropdown.

#### `showRoleDropdown(cell, rowIndex)`
Delegates to DropdownManager to show role selection dropdown.

#### `showPersonDropdown(cell, rowIndex)`
Delegates to DropdownManager to show resource selection dropdown.

#### `hideAllDropdowns()`
Delegates to DropdownManager to hide all open dropdowns.

### Selection Methods

#### `selectProject(rowIndex, project)`
Delegates to RowManager to handle project selection for a row.

#### `selectActivity(rowIndex, activity)`
Delegates to RowManager to handle activity selection for a row.

#### `selectRole(rowIndex, role)`
Delegates to RowManager to handle role selection for a row.

#### `selectPerson(rowIndex, resource)`
Delegates to RowManager to handle resource selection for a row.

### Time Entry Management

#### `addSingleTimeEntry(rowIndex, date)`
Adds a single 8-hour time entry (9:00-17:00) to a schedule row.

#### `addMultipleTimeEntries(rowIndex, dates)`
Adds time entries for multiple dates with drag selection.

#### `updateTimeEntry(scheduleRowId, date, hours)`
Updates an existing time entry with new hours.

#### `editTimeEntry(scheduleRowId, date, entry)`
Opens edit interface for a time entry (currently uses prompt).

### Drag Selection

#### `startDragSelection(event, rowIndex, startDate)`
Initiates drag selection for multiple days:
- Sets up mouse event listeners
- Prevents text selection
- Marks starting cell

#### `handleDragSelection(event)`
Handles drag selection movement:
- Finds cell under mouse
- Updates selected date range
- Applies visual selection styling

#### `endDragSelection(event)`
Completes drag selection:
- Cleans up event listeners
- Adds time entries for selected dates
- Restores normal interaction

### Row Management

#### `addNewRow()`
Adds a new empty schedule row to the bottom of the list.

#### `deleteRow(rowIndex)`
Removes a schedule row at the specified index.

#### `copyActivityDown(rowIndex)`
Creates a duplicate activity row below the current one with:
- Same project and activity
- Empty resource assignment
- Additional blank row for new assignments

### Template and Drag/Drop

#### `handleTemplateDrop(template, rowIndex, date)`
Handles dropping a template card onto a day cell:
- Validates project and activity selection
- Gets template configuration
- Adds time entry with template settings

#### `getTemplateConfig(template)`
Gets template configuration by delegating to SchedulerUtils.

**Delegates to:** `SchedulerUtils.getTemplateConfig(template)`

**See:** [SchedulerUtils.md](utils/SchedulerUtils.md#getTemplateConfig) for template configurations

#### `handleCellDrop(event, rowIndex, date)`
Handles drop events on day cells for both templates and existing entries.

### Time Block Management

#### `editTimeBlock(rowIndex, blockData, type)`
Delegates to TimeBlockManager to edit time block properties.

#### `updateTimeBlock(rowIndex, blockData, updates)`
Delegates to TimeBlockManager to update time block data.

#### `startResize(event, card, direction, rowIndex, blockData)`
Delegates to TimeBlockManager to start resizing a time block card.

### Modal Management

#### `openEntryModal(entry, prefill)`
Opens the entry creation/editing modal with:
- Pre-filled data if editing existing entry
- Project/activity/resource selectors
- Date and duration inputs

#### `closeEntryModal()`
Closes the entry modal.

#### `saveEntry()`
Saves entry data from modal form with validation.

### Navigation and Actions

#### `navigateDate(days)`
Navigates the date range by the specified number of days.

#### `refreshData()`
Reloads scheduler data from the API.

#### `exportSchedule()`
Placeholder for export functionality.

### Utility Methods

#### `getTodayString()`
Gets today's date string by delegating to SchedulerUtils.

**Delegates to:** `SchedulerUtils.getTodayString()`

**See:** [SchedulerUtils.md](utils/SchedulerUtils.md#getTodayString) for date utility details

#### `addDays(dateString, days)`
Adds days to date string by delegating to SchedulerUtils.

**Delegates to:** `SchedulerUtils.addDays(dateString, days)`

**See:** [SchedulerUtils.md](utils/SchedulerUtils.md#addDays) for date calculation details

#### `calculateDaysBetween(startDate, endDate)`
Calculates days between dates by delegating to SchedulerUtils.

**Delegates to:** `SchedulerUtils.calculateDaysBetween(startDate, endDate)`

**See:** [SchedulerUtils.md](utils/SchedulerUtils.md#calculateDaysBetween) for date calculation details

#### `setLoading(loading)`
Sets the loading state and shows/hides loading overlay.

#### `showToast(message, type)`
Shows a toast notification message.

#### `apiCall(method, args)`
Makes API calls by delegating to DataManager.

**Delegates to:** `DataManager.apiCall(method, args)`

**See:** [DataManager.md](data/DataManager.md#apiCall) for API integration details

### Resource Utilities

#### `createResourceAvatar(resource)`
Creates resource avatar by delegating to ResourceUtils.

**Delegates to:** `ResourceUtils.createResourceAvatar(resource)`

**See:** [ResourceUtils.md](utils/ResourceUtils.md#createResourceAvatar) for avatar creation details

#### `getResourceColor(name)`
Gets resource color by delegating to ResourceUtils.

**Delegates to:** `ResourceUtils.getResourceColor(name)`

**See:** [ResourceUtils.md](utils/ResourceUtils.md#getResourceColor) for color generation details

#### `getResourceTypeIcon(resourceType)`
Gets resource type icon by delegating to ResourceUtils.

**Delegates to:** `ResourceUtils.getResourceTypeIcon(resourceType)`

**See:** [ResourceUtils.md](utils/ResourceUtils.md#getResourceTypeIcon) for icon mapping details

### Cleanup

#### `cleanup()`
Cleans up all component managers and event listeners.

#### `handleResize()`
Handles window resize events.

## Global Functions

### `editScheduleEntry(entryId)`
Global function to edit a schedule entry by ID.

### `deleteScheduleEntry(entryId)`
Global function to delete a schedule entry by ID with confirmation.

### `deleteScheduleRow(rowIndex)`
Global function to delete a schedule row by index with confirmation.

### `copyActivityDown(rowIndex)`
Global function to copy an activity row down.

## Dependencies
- DataManager: Data loading and API calls
- DropdownManager: Dropdown functionality
- ScheduleRowManager: Row operations
- RowRenderer: Row and cell rendering
- TimeBlockManager: Time block management
- ToolbarManager: Toolbar functionality
- SchedulerUtils: General utilities
- ResourceUtils: Resource-related utilities

## Usage
```javascript
// Initialize scheduler
const scheduler = new SchedulerApp();

// Access from global scope
window.scheduler = scheduler;
