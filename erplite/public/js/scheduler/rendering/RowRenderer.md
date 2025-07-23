# RowRenderer.js Documentation

## Overview
Handles the creation and rendering of schedule rows, cells, and entries. Responsible for the visual representation of the scheduler grid including project headers, activity rows, day cells, and time entries.

## Class: RowRenderer

### Constructor
```javascript
constructor(app)
```
Initializes the row renderer with reference to the main scheduler app.

**Properties:**
- `app`: Reference to the main SchedulerApp instance

### Main Rendering Methods

#### `createScheduleRow(row, index)`
Creates a complete schedule row with separate fixed columns and day columns.

**Parameters:**
- `row`: Row data object
- `index`: Row index in the schedule

**Returns:**
- Object with `fixedColumns` and `dayColumns` DOM elements

**Process:**
1. Creates fixed columns row (project/activity, role, resource)
2. Creates day columns row (scrollable date cells)
3. Applies row type styling (project-header or activity-row)
4. Sets project color background for headers
5. Creates day cells for the date range

**Row Types:**
- `project-header`: Summary row for project with totals
- `activity-row`: Individual activity assignment row

### Fixed Column Creation

#### `createProjectActivityCell(row, index)`
Creates the project/activity cell (first fixed column).

**Project Header Behavior:**
- Shows project name and work type
- Displays project color border
- Non-interactive (no dropdowns)

**Activity Row Behavior:**
- Shows activity name if selected
- Shows "Select Activity" if project selected but no activity
- Shows "Select Project First" if no project selected
- Includes row controls (copy, delete) for completed rows
- Click handler for activity dropdown

**Row Controls:**
- Copy Down: Duplicates activity row below current
- Delete: Removes activity row with confirmation

#### `createRoleCell(row, index)`
Creates the role selection cell (second fixed column).

**Project Header Behavior:**
- Shows "Roles" label
- Non-interactive summary display

**Activity Row Behavior:**
- Disabled if no activity selected
- Shows role name with icon if selected
- Shows "Any" with icon if no specific role
- Click handler for role dropdown

#### `createResourceCell(row, index)`
Creates the resource selection cell (third fixed column).

**Project Header Behavior:**
- Shows resource type summary
- Counts resources by type (People, Equipment, etc.)
- Uses ResourceUtils for grouping and display

**Activity Row Behavior:**
- Disabled if no activity selected
- Shows resource avatar and name if assigned
- Shows "Select Resource" if unassigned
- Click handler for resource dropdown

### Day Cell Creation

#### `createDayCell(row, date, rowIndex)`
Creates a day cell for a specific date.

**Features:**
- Weekend styling for Saturday/Sunday
- Drag and drop support for templates and entries
- Entry containers for time entries or project totals
- Hover effects for valid cells
- Click handlers for entry creation

**Project Header Cells:**
- Show daily project totals
- Calculate hours from all activity rows
- Display "0" if no entries
- Non-interactive (disabled cursor)

**Activity Row Cells:**
- Show time entries if present
- Support drag selection for multiple days
- Interactive for entry creation
- Validation for project/activity requirements

### Entry Creation

#### `createScheduleEntry(entry)`
Creates a legacy schedule entry element.

**Features:**
- Project color styling
- Duration display
- Edit and delete controls
- Drag event listeners for moving entries
- Click handlers for entry management

#### `createTimeEntry(entry, date, row)`
Creates a time entry element for Schedule Row daily entries.

**Features:**
- Project color styling
- Hours and time range display
- Click handler for editing
- Consistent visual design

## Usage Examples

### Creating Schedule Rows
```javascript
// Create a complete schedule row
const { fixedColumns, dayColumns } = rowRenderer.createScheduleRow(row, index);

// Add to containers
fixedLeftContainer.appendChild(fixedColumns);
scrollableRightContainer.appendChild(dayColumns);
```

### Individual Cell Creation
```javascript
// Create project/activity cell
const projectCell = rowRenderer.createProjectActivityCell(row, index);

// Create role cell
const roleCell = rowRenderer.createRoleCell(row, index);

// Create resource cell
const resourceCell = rowRenderer.createResourceCell(row, index);

// Create day cell
const dayCell = rowRenderer.createDayCell(row, date, index);
```

### Entry Elements
```javascript
// Create schedule entry
const entryElement = rowRenderer.createScheduleEntry(entry);

// Create time entry
const timeEntryElement = rowRenderer.createTimeEntry(entry, date, row);
```

## Visual Features

### Project Headers
- Light background tint using project color
- Project name and work type display
- Resource type summaries with icons
- Daily total calculations
- Non-interactive design

### Activity Rows
- Clean, minimal design
- Interactive cells with hover effects
- Row controls for management actions
- Validation states (disabled/enabled)
- Drag and drop support

### Day Cells
- Weekend highlighting
- Today highlighting (handled by parent)
- Entry containers with proper spacing
- Hover effects for valid interactions
- Drop zone indicators

### Time Entries
- Project color theming
- Hours and time range display
- Consistent sizing and spacing
- Interactive click areas
- Visual feedback on hover

## Event Handling

### Click Events
- Project/activity cell: Shows activity dropdown
- Role cell: Shows role dropdown
- Resource cell: Shows resource dropdown
- Day cell: Creates new entry (if valid)
- Entry elements: Opens edit interface

### Drag and Drop
- Day cells accept template drops
- Day cells accept entry moves
- Visual feedback during drag operations
- Drop zone highlighting
- Validation before accepting drops

### Row Controls
- Copy Down: Duplicates activity row
- Delete: Removes row with confirmation
- Hover states for better UX
- Icon-based design for clarity

## Styling Classes

### Row Structure
- `.schedule-row`: Base row container
- `.project-header`: Project header row styling
- `.activity-row`: Activity row styling
- `.schedule-cell`: Individual cell styling
- `.schedule-days`: Day cells container

### Cell Types
- `.project-activity-cell`: First column styling
- `.role-cell`: Second column styling
- `.resource-cell`: Third column styling
- `.day-cell`: Date cell styling

### Cell States
- `.filled`: Cell with selected value
- `.empty`: Cell awaiting selection
- `.disabled`: Non-interactive cell
- `.valid-cell`: Interactive cell
- `.has-entry`: Cell with time entries

### Interactive Elements
- `.row-controls`: Control buttons container
- `.row-control-btn`: Individual control button
- `.copy-down-btn`: Copy button styling
- `.delete-row-btn`: Delete button styling

### Entry Elements
- `.schedule-entry`: Legacy entry styling
- `.time-entry`: Time entry styling
- `.entry-duration`: Duration display
- `.entry-controls`: Entry control buttons

### Visual Effects
- `.weekend`: Weekend cell styling
- `.hover-landing-zone`: Hover effect
- `.drop-zone`: Drop target highlighting
- `.dragging`: Element being dragged

## Dependencies
- SchedulerApp: Main application reference
- SchedulerUtils: Date and utility functions
- ResourceUtils: Resource-related utilities
- Material Design Icons: Icon classes
- CSS: Styling and animations

## Integration
The RowRenderer is instantiated by the main SchedulerApp and handles all visual rendering of the schedule grid. It works closely with other managers to provide interactive elements while maintaining clean separation of concerns between rendering and business logic.

## Performance Considerations
- Efficient DOM creation and manipulation
- Minimal re-rendering through targeted updates
- Event delegation where appropriate
- Lazy loading of complex elements
- Optimized cell creation for large date ranges
