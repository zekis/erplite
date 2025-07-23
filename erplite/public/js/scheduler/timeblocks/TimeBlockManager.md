# TimeBlockManager.js Documentation

## Overview
Handles rendering, resizing, and interaction with time block cards. Manages the visual representation of time entries as draggable and resizable blocks that span across multiple days, providing an intuitive interface for schedule management.

## Class: TimeBlockManager

### Constructor
```javascript
constructor(app)
```
Initializes the time block manager with reference to the main scheduler app.

**Properties:**
- `app`: Reference to the main SchedulerApp instance
- `resizeState`: Current resize operation state
- `boundHandleResize`: Bound resize event handler
- `boundEndResize`: Bound resize end handler

### Core Rendering Methods

#### `renderTimeBlockCards()`
Renders time block cards for all schedule rows.

**Process:**
1. Removes existing time block cards
2. Iterates through all schedule rows
3. Parses daily entries (string or object format)
4. Handles both optimized and simple entry formats
5. Groups consecutive entries into blocks
6. Renders individual cards for each block

**Entry Formats Supported:**
- Optimized format: `{ blocks: [], individual_days: {} }`
- Simple format: `{ "2024-01-15": { hours: 8, ... } }`

#### `renderTimeBlockCard(rowIndex, blockData, type, row)`
Renders a single time block card.

**Parameters:**
- `rowIndex`: Index of the schedule row
- `blockData`: Block data with start/end dates and properties
- `type`: 'block' (multi-day) or 'individual' (single day)
- `row`: Schedule row data

**Features:**
- Calculates position and width based on date cells
- Sets project color theming
- Creates content with hours and time display
- Adds resize handles for interaction
- Positions card relative to day cells container

### Time Block Interaction

#### `editTimeBlock(rowIndex, blockData, type)`
Opens edit interface for a time block.

**Block Type Handling:**
- Multi-day blocks: Shows day count and date range
- Single-day blocks: Shows specific date
- Prompts for new hours value
- Validates input and updates if valid

#### `updateTimeBlock(rowIndex, blockData, updates)`
Updates a time block with new properties.

**Process:**
1. Validates schedule row exists
2. Gets expanded daily entries from backend
3. Updates affected dates with new properties
4. Saves updated entries to backend
5. Updates local state with optimized entries
6. Re-renders time block cards

**API Integration:**
- `get_schedule_row_expanded`: Gets daily format entries
- `update_schedule_row_entries`: Saves updated entries

### Resize Functionality

#### `startResize(event, card, direction, rowIndex, blockData)`
Initiates resize operation for a time block.

**Parameters:**
- `event`: Mouse event
- `card`: Time block card element
- `direction`: 'left' or 'right'
- `rowIndex`: Schedule row index
- `blockData`: Original block data

**Setup:**
- Stores resize state
- Adds visual feedback (resizing class)
- Binds mouse event handlers
- Prevents text selection during resize

#### `handleResize(event)`
Handles mouse movement during resize operation.

**Process:**
1. Finds day cell under mouse cursor
2. Calculates new date range based on resize direction
3. Validates date range (start ≤ end)
4. Highlights affected date range
5. Updates card visual appearance
6. Stores new dates for completion

#### `endResize(event)`
Completes resize operation and applies changes.

**Process:**
1. Cleans up event listeners
2. Removes visual feedback
3. Applies resize if dates changed
4. Updates data model with new date range
5. Re-renders schedule and time blocks

#### `applyResize(rowIndex, originalBlockData, newStartDate, newEndDate)`
Applies resize changes to the data model.

**Process:**
1. Removes entries from original date range
2. Adds entries for new date range
3. Preserves original entry properties
4. Re-renders schedule and time blocks
5. Shows success notification

### Visual Feedback

#### `highlightDateRange(rowIndex, startDate, endDate)`
Highlights date range during resize operation.

**Features:**
- Clears previous highlights
- Adds resize-target class to affected cells
- Provides visual feedback for resize boundaries

#### `updateCardVisualDuringResize(card, daysContainer, startDate, endDate)`
Updates card appearance during resize.

**Updates:**
- Card position and width
- Content to show new day count
- Hours display with multiplier for multi-day blocks

### Entry Grouping

#### `groupConsecutiveEntries(entries)`
Groups consecutive entries by delegating to SchedulerUtils.

**Delegates to:** `SchedulerUtils.groupConsecutiveEntries(entries)`

**See:** [SchedulerUtils.md](../utils/SchedulerUtils.md#groupConsecutiveEntries) for entry grouping algorithm

#### `canEntriesBeGrouped(block, entry)`
Checks if entries can be grouped by delegating to SchedulerUtils.

**Delegates to:** `SchedulerUtils.canEntriesBeGrouped(block, entry)`

**See:** [SchedulerUtils.md](../utils/SchedulerUtils.md#canEntriesBeGrouped) for grouping criteria

### Time Entry Management

#### `addSingleTimeEntry(rowIndex, date)`
Adds a single 8-hour time entry to a schedule row.

**Default Properties:**
- Hours: 8
- Start time: 09:00
- End time: 17:00
- Status: planned

#### `addMultipleTimeEntries(rowIndex, dates)`
Adds time entries for multiple dates (drag selection).

#### `updateTimeEntry(scheduleRowId, date, hours)`
Updates an existing time entry with new hours.

#### `editTimeEntry(scheduleRowId, date, entry)`
Opens edit interface for a time entry (currently uses prompt).

### Cleanup

#### `cleanup()`
Cleans up time block manager resources.

**Process:**
- Stops active resize operations
- Removes event listeners
- Restores text selection
- Removes all time block cards
- Resets state

## Usage Examples

### Rendering Time Blocks
```javascript
// Render all time block cards
timeBlockManager.renderTimeBlockCards();

// Render specific time block
timeBlockManager.renderTimeBlockCard(rowIndex, blockData, 'block', row);
```

### Time Block Interaction
```javascript
// Edit time block
timeBlockManager.editTimeBlock(rowIndex, blockData, 'block');

// Update time block
await timeBlockManager.updateTimeBlock(rowIndex, blockData, { hours: 6 });
```

### Resize Operations
```javascript
// Start resize (typically called from event handler)
timeBlockManager.startResize(event, card, 'right', rowIndex, blockData);

// The resize process is handled automatically through mouse events
```

### Entry Management
```javascript
// Add single entry
await timeBlockManager.addSingleTimeEntry(rowIndex, '2024-01-15');

// Add multiple entries
await timeBlockManager.addMultipleTimeEntries(rowIndex, [
    '2024-01-15', '2024-01-16', '2024-01-17'
]);
```

## Visual Features

### Time Block Cards
- Project color theming
- Responsive width based on date span
- Hours and time range display
- Resource name display (if assigned)
- Resize handles on left and right edges

### Card Types
- **Single Day**: Shows hours and time range
- **Multi-Day Block**: Shows hours × days and time range
- **Different Styling**: Based on block type and duration

### Resize Interaction
- Visual feedback during resize
- Date range highlighting
- Real-time card updates
- Snap-to-cell positioning

### Content Display
```javascript
// Single day card
"8h"
"9:00-17:00"
"John Doe"

// Multi-day card
"8h × 3"
"9:00-17:00"
"John Doe"
```

## CSS Classes

### Time Block Elements
- `.time-block-card`: Main card container
- `.card-content`: Card content area
- `.card-hours`: Hours display
- `.card-time`: Time range display
- `.card-resource`: Resource name display

### Card States
- `.single-day`: Single day card styling
- `.start-day`: Multi-day block start styling
- `.resizing`: Card being resized
- `.dragging`: Card being dragged (if implemented)

### Resize Elements
- `.resize-handle`: Resize handle styling
- `.resize-handle.left`: Left resize handle
- `.resize-handle.right`: Right resize handle
- `.resize-target`: Date cell resize target

## Event Handling

### Mouse Events
- `mousedown`: Start resize operation
- `mousemove`: Handle resize movement
- `mouseup`: End resize operation
- `click`: Edit time block (on content area)

### Resize State Management
```javascript
resizeState = {
    active: boolean,
    card: HTMLElement,
    direction: 'left' | 'right',
    rowIndex: number,
    blockData: object,
    originalStartDate: string,
    originalEndDate: string,
    newStartDate: string,
    newEndDate: string,
    startX: number
}
```

## API Integration

### Backend Methods
- `erplite.scheduler.api.get_schedule_row_expanded`
- `erplite.scheduler.api.update_schedule_row_entries`

### Data Formats

#### Block Data Format
```javascript
{
    start_date: "2024-01-15",
    end_date: "2024-01-17",
    hours: 8,
    start_time: "09:00",
    end_time: "17:00",
    description: "",
    status: "planned"
}
```

#### Optimized Entries Format
```javascript
{
    blocks: [
        {
            start_date: "2024-01-15",
            end_date: "2024-01-17",
            hours: 8,
            start_time: "09:00",
            end_time: "17:00"
        }
    ],
    individual_days: {
        "2024-01-20": {
            hours: 6,
            start_time: "10:00",
            end_time: "16:00"
        }
    }
}
```

## Performance Considerations

### Efficient Rendering
- Removes existing cards before re-rendering
- Calculates positions based on actual DOM elements
- Minimizes DOM queries through caching
- Uses relative positioning for smooth interactions

### Memory Management
- Proper cleanup of event listeners
- State reset after operations
- Removal of DOM elements when not needed

## Dependencies
- SchedulerApp: Main application reference
- SchedulerUtils: Date and utility functions
- DOM APIs: Element positioning and manipulation
- CSS: Visual styling and animations

## Integration
The TimeBlockManager is instantiated by the main SchedulerApp and provides visual time block functionality. It works closely with the RowRenderer for positioning and the DataManager for persistence, creating an intuitive drag-and-resize interface for schedule management.
