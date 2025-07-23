# DataManager.js Documentation

## Overview
Handles all API calls, data loading, and data processing for the scheduler. Acts as the data layer between the frontend application and the Frappe backend, managing both legacy schedule entries and new schedule rows.

## Class: DataManager

### Constructor
```javascript
constructor(app)
```
Initializes the data manager with reference to the main scheduler app.

**Properties:**
- `app`: Reference to the main SchedulerApp instance

### Data Loading Methods

#### `loadInitialData()`
Loads initial data from the window object set by the template.

**Data Sources:**
- `window.schedulerData.currentStartDate`: Initial start date
- `window.schedulerData.projects`: Available projects
- `window.schedulerData.resources`: Available resources
- `window.schedulerData.roles`: Available roles
- `window.schedulerData.scheduleEntries`: Legacy schedule entries
- `window.schedulerData.projectColors`: Project color mappings

**Fallback:** Uses today's date if no initial data available

#### `loadSchedulerData()`
Loads scheduler data from API with parallel requests for optimal performance.

**Process:**
1. Sets loading state
2. Calculates end date based on date range
3. Makes parallel API calls for projects and schedule rows
4. Processes schedule rows from API or falls back to legacy processing
5. Returns success/error result

**API Calls:**
- `erplite.scheduler.api.get_scheduler_data`
- `erplite.scheduler.api.get_schedule_rows`

### Data Processing Methods

#### `processScheduleRowsFromAPI(scheduleRowsData)`
Processes schedule rows from API response (structure only, no time entries for frontend development).

**Process:**
1. Groups schedule rows by project
2. Creates project groups with rows
3. Adds default projects that don't have schedule rows
4. Converts to flat array with project headers and activity rows
5. Adds blank activity rows for new assignments

**Row Types Created:**
- `project-header`: Project summary rows
- `activity-row`: Individual activity assignments

#### `processScheduleRows()` (Legacy)
Processes legacy schedule entries into rows with project headers and activity rows.

**Process:**
1. Groups entries by project, activity, and resource
2. Adds default projects
3. Creates hierarchical structure
4. Flattens to array with headers and rows

#### `addDefaultProjectsToGroups(projectGroups)`
Ensures all active/open projects appear in the schedule even without existing rows.

**Filter Criteria:**
- Project status: "Active" or "Open"

### CRUD Operations

#### `createScheduleEntry(formData)`
Creates a new schedule entry via API.

**Parameters:**
- `formData`: Object containing entry data

**Returns:**
- Success/error object with message

**API Call:** `erplite.scheduler.api.create_schedule_entry`

#### `updateScheduleEntry(entryId, formData)`
Updates an existing schedule entry via API.

**Parameters:**
- `entryId`: ID of entry to update
- `formData`: Updated entry data

**Returns:**
- Success/error object with message

**API Call:** `erplite.scheduler.api.update_schedule_entry`

#### `deleteScheduleEntry(entryId)`
Deletes a schedule entry via API.

**Parameters:**
- `entryId`: ID of entry to delete

**Returns:**
- Success/error object with message

**API Call:** `erplite.scheduler.api.delete_schedule_entry`

### Navigation and Refresh

#### `refreshData()`
Refreshes scheduler data and re-renders all components.

**Process:**
1. Calls loadSchedulerData()
2. Renders all components on success
3. Returns result

#### `navigateDate(days)`
Navigates to a different date range.

**Parameters:**
- `days`: Number of days to navigate (positive or negative)

**Process:**
1. Calculates new start date
2. Updates application state
3. Loads new data
4. Renders all components on success

### Data Validation

#### `validateScheduleEntry(formData)`
Validates schedule entry data before submission.

**Validation Rules:**
- Project is required
- Activity is required
- Schedule date is required
- Duration must be greater than 0

**Returns:**
- Object with `isValid` boolean and `errors` array

### Data Access Methods

#### `getProject(projectId)`
Retrieves project by ID from loaded projects.

#### `getActivity(projectId, activityId)`
Retrieves activity by project and activity ID.

#### `getResource(resourceId)`
Retrieves resource by ID from loaded resources.

#### `getRole(roleId)`
Retrieves role by ID from loaded roles.

#### `getActiveProjects()`
Returns all projects with "Active" or "Open" status.

#### `getProjectColor(projectId)`
Returns project color or default gray if not found.

### Utility Methods

#### `getResourceName(resourceId)`
Gets resource display name by ID, returns "Unassigned" if not found.

#### `isDataLoaded()`
Checks if data has been loaded (projects or schedule rows exist).

#### `getDataSummary()`
Returns summary object for debugging with counts and state information.

#### `getTodayString()`
Gets today's date string by delegating to SchedulerUtils.

**Delegates to:** `SchedulerUtils.getTodayString()`

**See:** [SchedulerUtils.md](../utils/SchedulerUtils.md#getTodayString) for date utility details

#### `addDays(dateString, days)`
Adds days to date string by delegating to SchedulerUtils.

**Delegates to:** `SchedulerUtils.addDays(dateString, days)`

**See:** [SchedulerUtils.md](../utils/SchedulerUtils.md#addDays) for date calculation details

### API Integration

#### `apiCall(method, args)`
Makes API calls to the Frappe backend.

**Parameters:**
- `method`: Frappe method name
- `args`: Arguments object

**Returns:**
- Promise resolving to response message

**Implementation:**
- Uses Frappe's `frappe.call()` method
- Wraps in Promise for async/await support
- Handles errors appropriately

## Usage Examples

### Loading Data
```javascript
// Load initial data from window
dataManager.loadInitialData();

// Load scheduler data from API
const result = await dataManager.loadSchedulerData();
if (result.success) {
    console.log('Data loaded successfully');
}
```

### CRUD Operations
```javascript
// Create schedule entry
const createResult = await dataManager.createScheduleEntry({
    project: 'PROJECT-001',
    activity: 'TASK-001',
    resource: 'RESOURCE-001',
    schedule_date: '2024-01-15',
    duration: 8,
    priority: 'Medium',
    description: 'Work on project task'
});

// Update schedule entry
const updateResult = await dataManager.updateScheduleEntry('ENTRY-001', {
    duration: 6,
    description: 'Updated description'
});

// Delete schedule entry
const deleteResult = await dataManager.deleteScheduleEntry('ENTRY-001');
```

### Data Access
```javascript
// Get project information
const project = dataManager.getProject('PROJECT-001');

// Get activity for project
const activity = dataManager.getActivity('PROJECT-001', 'TASK-001');

// Get all active projects
const activeProjects = dataManager.getActiveProjects();

// Validate entry data
const validation = dataManager.validateScheduleEntry(formData);
if (!validation.isValid) {
    console.log('Validation errors:', validation.errors);
}
```

### Navigation
```javascript
// Navigate forward 7 days
await dataManager.navigateDate(7);

// Navigate backward 7 days
await dataManager.navigateDate(-7);

// Refresh current data
await dataManager.refreshData();
```

## Data Structures

### Schedule Row Structure
```javascript
{
    type: 'activity-row',
    scheduleRowId: 'ROW-001',
    project: 'PROJECT-001',
    projectName: 'Sample Project',
    activity: 'TASK-001',
    activityName: 'Sample Task',
    role: 'ROLE-001',
    roleName: 'Developer',
    resource: 'RESOURCE-001',
    resourceName: 'John Doe',
    entries: [],
    dailyEntries: {}
}
```

### Project Header Structure
```javascript
{
    type: 'project-header',
    project: 'PROJECT-001',
    projectName: 'Sample Project',
    workType: 'Development',
    activity: null,
    activityName: null,
    resource: null,
    resourceName: null,
    entries: []
}
```

### Schedule Entry Structure (Legacy)
```javascript
{
    name: 'ENTRY-001',
    project: 'PROJECT-001',
    project_name: 'Sample Project',
    activity: 'TASK-001',
    activity_name: 'Sample Task',
    resource: 'RESOURCE-001',
    resource_name: 'John Doe',
    schedule_date: '2024-01-15',
    duration: 8,
    priority: 'Medium',
    description: 'Work description'
}
```

## Error Handling

All API methods include comprehensive error handling:
- Try-catch blocks around API calls
- Loading state management
- User-friendly error messages
- Console logging for debugging
- Graceful fallbacks for missing data

## Dependencies
- SchedulerApp: Main application reference
- SchedulerUtils: Date and utility functions
- Frappe API: Backend integration
- Toast notifications: User feedback

## Integration
The DataManager is instantiated by the main SchedulerApp and serves as the single source of truth for all data operations. It maintains consistency between frontend state and backend data while providing efficient loading and caching mechanisms.
