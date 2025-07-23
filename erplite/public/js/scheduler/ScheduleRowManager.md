# ScheduleRowManager.js Documentation

## Overview
Handles all schedule row operations and backend API calls. Manages the creation, updating, and manipulation of schedule rows including project/activity/resource assignments and time entries.

## Class: ScheduleRowManager

### Constructor
```javascript
constructor(schedulerApp)
```
Initializes the schedule row manager with reference to the main scheduler app.

**Properties:**
- `app`: Reference to the main SchedulerApp instance

### Schedule Row API Methods

#### `createScheduleRow(project, activity, resource, role)`
Creates a new schedule row entry in the backend.

**Parameters:**
- `project`: Project ID
- `activity`: Activity ID
- `resource`: Resource ID (optional)
- `role`: Role ID (optional)

**Returns:**
- Success object with `scheduleRowId` if successful
- Error object with message if failed

**API Call:** `erplite.scheduler.api.create_schedule_row_entry`

#### `updateScheduleRowRole(scheduleRowId, role)`
Updates the role assignment for an existing schedule row.

**Parameters:**
- `scheduleRowId`: ID of the schedule row to update
- `role`: New role ID (can be null for "Any Role")

**Returns:**
- Success/error object with message

**API Call:** `erplite.scheduler.api.update_schedule_row_role`

#### `updateScheduleRowResource(scheduleRowId, resource)`
Updates the resource assignment for an existing schedule row.

**Parameters:**
- `scheduleRowId`: ID of the schedule row to update
- `resource`: New resource ID (can be null for "Unassigned")

**Returns:**
- Success/error object with message

**API Call:** `erplite.scheduler.api.update_schedule_row_resource`

#### `updateScheduleRowEntries(scheduleRowId, entriesJson)`
Updates the time entries for a schedule row.

**Parameters:**
- `scheduleRowId`: ID of the schedule row to update
- `entriesJson`: JSON string of daily entries

**Returns:**
- Success object with `optimizedEntries` if successful
- Error object with message if failed

**API Call:** `erplite.scheduler.api.update_schedule_row_entries`

#### `getScheduleRowExpanded(scheduleRowId)`
Retrieves expanded schedule row entries in daily format.

**Parameters:**
- `scheduleRowId`: ID of the schedule row to retrieve

**Returns:**
- Success object with `dailyEntries` if successful
- Error object with message if failed

**API Call:** `erplite.scheduler.api.get_schedule_row_expanded`

### Selection Methods

#### `selectProject(rowIndex, project)`
Handles project selection for a schedule row.

**Process:**
1. Updates row with project information
2. Clears activity, role, and resource selections
3. Adds new blank row below
4. Re-renders schedule rows
5. Shows success toast

**Parameters:**
- `rowIndex`: Index of the row to update
- `project`: Project object with name and project_name

#### `selectActivity(rowIndex, activity)`
Handles activity selection for a schedule row.

**Process:**
1. Updates row with activity information
2. Creates schedule row in backend automatically
3. Stores schedule row ID for future operations
4. Adds new blank row with same project
5. Re-renders schedule rows
6. Shows success/warning toast

**Parameters:**
- `rowIndex`: Index of the row to update
- `activity`: Activity object with name and subject

#### `selectRole(rowIndex, role)`
Handles role selection for a schedule row.

**Process:**
1. Updates row with role information
2. Updates backend if schedule row exists
3. Shows success/warning toast based on backend result
4. Re-renders schedule rows

**Parameters:**
- `rowIndex`: Index of the row to update
- `role`: Role object (can be null for "Any Role")

#### `selectResource(rowIndex, resource)`
Handles resource selection for a schedule row.

**Process:**
1. Updates row with resource information
2. Creates or updates schedule row in backend if project/activity exist
3. Shows success/warning toast based on result
4. Re-renders schedule rows

**Parameters:**
- `rowIndex`: Index of the row to update
- `resource`: Resource object (can be null for "Unassigned")

### Time Entry Management

#### `addSingleTimeEntry(rowIndex, date)`
Adds a single 8-hour time entry to a schedule row.

**Default Entry:**
- Hours: 8
- Start time: 09:00
- End time: 17:00
- Status: planned

**Process:**
1. Validates schedule row exists
2. Creates time entry object
3. Updates local daily entries
4. Saves to backend via API
5. Updates local state with optimized entries
6. Re-renders schedule rows

#### `addMultipleTimeEntries(rowIndex, dates)`
Adds time entries for multiple dates (used with drag selection).

**Process:**
1. Validates schedule row exists
2. Creates time entries for all dates
3. Updates local daily entries
4. Saves to backend via API
5. Updates local state with optimized entries
6. Re-renders schedule rows

#### `updateTimeEntry(scheduleRowId, date, hours)`
Updates an existing time entry with new hours.

**Process:**
1. Finds the schedule row by ID
2. Updates the specific date entry
3. Saves to backend via API
4. Updates local state with optimized entries
5. Re-renders schedule rows

### Template Handling

#### `handleTemplateDrop(template, rowIndex, date)`
Handles dropping a template card onto a day cell.

**Process:**
1. Validates project and activity are selected
2. Gets template configuration
3. Creates time entry with template settings
4. Saves to backend if schedule row exists
5. Re-renders schedule and time block cards

**Template Types:**
- `8h`: 8-hour standard shift
- `12h`: 12-hour extended shift
- `leave`: Leave/time off

### Row Management

#### `deleteRow(rowIndex)`
Deletes a schedule row from the local state.

**Process:**
1. Removes row from scheduleRows array
2. Re-renders schedule rows
3. Shows success toast

**Note:** This only removes from local state, not backend

#### `copyActivityDown(rowIndex)`
Creates a duplicate activity row below the current one.

**Process:**
1. Creates copy of source row with same project/activity/role/resource
2. Inserts copy below current row
3. Adds additional blank row for new assignments
4. Re-renders schedule rows
5. Shows success toast

## Usage Examples

### Creating Schedule Rows
```javascript
// Create schedule row when activity is selected
const result = await rowManager.createScheduleRow(
    'PROJECT-001',
    'TASK-001',
    'RESOURCE-001',
    'ROLE-001'
);

if (result.success) {
    console.log('Schedule row created:', result.scheduleRowId);
}
```

### Managing Time Entries
```javascript
// Add single time entry
await rowManager.addSingleTimeEntry(rowIndex, '2024-01-15');

// Add multiple time entries
await rowManager.addMultipleTimeEntries(rowIndex, [
    '2024-01-15',
    '2024-01-16',
    '2024-01-17'
]);

// Update existing entry
await rowManager.updateTimeEntry(scheduleRowId, '2024-01-15', 6);
```

### Selection Handling
```javascript
// Handle project selection
rowManager.selectProject(0, {
    name: 'PROJECT-001',
    project_name: 'Sample Project'
});

// Handle activity selection
rowManager.selectActivity(0, {
    name: 'TASK-001',
    subject: 'Sample Task'
});

// Handle resource selection
rowManager.selectResource(0, {
    name: 'RESOURCE-001',
    resource_name: 'John Doe'
});
```

## API Integration

### Backend Methods Used
- `erplite.scheduler.api.create_schedule_row_entry`
- `erplite.scheduler.api.update_schedule_row_role`
- `erplite.scheduler.api.update_schedule_row_resource`
- `erplite.scheduler.api.update_schedule_row_entries`
- `erplite.scheduler.api.get_schedule_row_expanded`

### Data Formats

#### Time Entry Format
```javascript
{
    hours: 8,
    start_time: "09:00",
    end_time: "17:00",
    description: "",
    status: "planned"
}
```

#### Daily Entries Format
```javascript
{
    "2024-01-15": {
        hours: 8,
        start_time: "09:00",
        end_time: "17:00",
        description: "",
        status: "planned"
    },
    "2024-01-16": {
        hours: 8,
        start_time: "09:00",
        end_time: "17:00",
        description: "",
        status: "planned"
    }
}
```

## Error Handling

All API methods include comprehensive error handling:
- Try-catch blocks for API calls
- Success/error return objects
- User-friendly toast notifications
- Fallback to local-only updates when backend fails
- Console logging for debugging

## Dependencies
- SchedulerApp: Main application reference
- Frappe API: Backend integration
- Toast notifications: User feedback
- Schedule rendering: UI updates

## Integration
The ScheduleRowManager is instantiated by the main SchedulerApp and handles all schedule row operations. It maintains the connection between the frontend state and backend data, ensuring consistency and providing fallback behavior when needed.
