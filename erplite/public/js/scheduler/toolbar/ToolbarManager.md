# ToolbarManager.js Documentation

## Overview
Handles all toolbar functionality including navigation, templates, and actions. Manages the scheduler's toolbar interface with template cards, navigation buttons, action buttons, and keyboard shortcuts.

## Class: ToolbarManager

### Constructor
```javascript
constructor(app)
```
Initializes the toolbar manager with reference to the main scheduler app.

**Properties:**
- `app`: Reference to the main SchedulerApp instance
- `templateCards`: Array of template card references
- `navigationButtons`: Object mapping days to navigation buttons
- `actionButtons`: Object mapping action types to buttons
- `dateDisplay`: Reference to date display element

### Initialization Methods

#### `init()`
Initializes all toolbar functionality.

**Process:**
1. Initializes template cards with drag and drop
2. Sets up navigation buttons
3. Configures action buttons
4. Sets up date display
5. Logs initialization completion

#### `initializeTemplateCards()`
Sets up template cards with drag and drop functionality.

**Features:**
- Stores references to all template cards
- Adds drag event listeners
- Adds click handlers for mobile/touch devices
- Supports template types: 8h, 12h, leave

#### `initializeNavigationButtons()`
Sets up navigation buttons for date range movement.

**Process:**
1. Finds all navigation buttons
2. Extracts days parameter from onclick attributes
3. Replaces onclick with proper event listeners
4. Adds keyboard support (Enter/Space)
5. Maps buttons by days value for reference

#### `initializeActionButtons()`
Sets up action buttons (refresh, export, add row).

**Buttons Configured:**
- **Refresh**: Reloads scheduler data
- **Export**: Placeholder for export functionality
- **Add Row**: Adds new schedule row

**Features:**
- Removes onclick attributes
- Adds proper event listeners
- Includes keyboard support
- Loading state management

#### `initializeDateDisplay()`
Sets up reference to the date range display element.

### Template Management

#### `handleTemplateDragStart(event, card)`
Handles the start of template card dragging.

**Process:**
1. Sets drag data with template type
2. Adds visual dragging state
3. Creates custom drag image with rotation
4. Cleans up drag image after drag starts

#### `handleTemplateDragEnd(event, card)`
Handles the end of template card dragging.

**Process:**
- Removes dragging visual state
- Cleans up any remaining drag artifacts

#### `handleTemplateClick(event, card)`
Handles template card clicks for mobile/touch devices.

**Features:**
- Shows template information
- Provides visual feedback
- Displays tooltip with template details

#### `showTemplateInfo(card, config)`
Shows template information tooltip.

**Tooltip Content:**
- Template name
- Hours and time range
- Usage instructions
- Auto-removal after 3 seconds

#### `getTemplateConfig(template)`
Gets template configuration by delegating to SchedulerUtils.

**Delegates to:** `SchedulerUtils.getTemplateConfig(template)`

**See:** [SchedulerUtils.md](../utils/SchedulerUtils.md#getTemplateConfig) for template configurations

### Navigation Methods

#### `navigateDate(days)`
Navigates the date range by specified number of days.

**Process:**
1. Adds loading state to navigation button
2. Calculates new start date
3. Updates application state
4. Loads new scheduler data
5. Updates date display immediately for better UX
6. Removes loading state when complete

#### `updateDateDisplay()`
Updates the date range display in the toolbar.

**Format:**
- Start date - End date
- Example: "Jan 15, 2024 - Feb 13, 2024"
- Uses locale-specific formatting

### Action Methods

#### `refreshData()`
Refreshes scheduler data from the API.

**Process:**
1. Adds loading state to refresh button
2. Changes icon to spinning loader
3. Calls data loading method
4. Restores button state when complete
5. Updates button icon back to refresh

#### `exportSchedule()`
Placeholder for schedule export functionality.

**Current Implementation:**
- Shows loading state
- Displays "coming soon" message
- Simulates export process with timeout

#### `addNewRow()`
Adds a new schedule row to the scheduler.

**Process:**
1. Adds visual feedback to button
2. Calls main app's addNewRow method
3. Provides user feedback

### State Management

#### `setLoading(loading)`
Sets loading state for all toolbar elements.

**Effects:**
- Disables/enables template cards
- Adjusts opacity for visual feedback
- Disables navigation and action buttons
- Prevents interaction during loading

#### `updateToolbarState()`
Updates toolbar state based on scheduler state.

**Updates:**
- Date display with current range
- Navigation button states based on data availability
- Export button state based on data presence
- Visual feedback for data availability

### Keyboard Shortcuts

#### `initializeKeyboardShortcuts()`
Sets up keyboard shortcuts for toolbar actions.

**Shortcuts:**
- `Ctrl/Cmd + ←`: Navigate left 7 days
- `Ctrl/Cmd + →`: Navigate right 7 days
- `Ctrl/Cmd + R`: Refresh data
- `Ctrl/Cmd + E`: Export schedule
- `Ctrl/Cmd + N`: Add new row

**Features:**
- Ignores shortcuts when in input fields
- Cross-platform modifier key support
- Prevents default browser behavior

### Cleanup

#### `cleanup()`
Cleans up toolbar manager resources.

**Process:**
- Removes event listeners from template cards
- Clears all references
- Resets arrays and objects
- Logs cleanup completion

## Usage Examples

### Basic Initialization
```javascript
// Initialize toolbar
const toolbarManager = new ToolbarManager(schedulerApp);
toolbarManager.init();
```

### Navigation
```javascript
// Navigate forward 7 days
toolbarManager.navigateDate(7);

// Navigate backward 7 days
toolbarManager.navigateDate(-7);

// Update date display
toolbarManager.updateDateDisplay();
```

### Actions
```javascript
// Refresh data
toolbarManager.refreshData();

// Export schedule
toolbarManager.exportSchedule();

// Add new row
toolbarManager.addNewRow();
```

### State Management
```javascript
// Set loading state
toolbarManager.setLoading(true);

// Update toolbar state
toolbarManager.updateToolbarState();
```

## Template System

### Template Card Structure
```html
<div class="template-card" data-template="8h" draggable="true">
    <div class="template-icon">⏰</div>
    <div class="template-name">8 Hour</div>
    <div class="template-time">9:00 - 17:00</div>
</div>
```

### Template Configurations
```javascript
{
    '8h': {
        name: '8 Hour Shift',
        hours: 8,
        start_time: '09:00',
        end_time: '17:00',
        description: 'Standard 8-hour work day',
        status: 'planned'
    },
    '12h': {
        name: '12 Hour Shift',
        hours: 12,
        start_time: '07:00',
        end_time: '19:00',
        description: 'Extended 12-hour shift',
        status: 'planned'
    },
    'leave': {
        name: 'Leave',
        hours: 8,
        start_time: '00:00',
        end_time: '23:59',
        description: 'Time off / Leave',
        status: 'leave'
    }
}
```

## CSS Classes

### Template Elements
- `.template-card`: Template card container
- `.template-icon`: Template icon display
- `.template-name`: Template name text
- `.template-time`: Template time range
- `.dragging`: Card being dragged
- `.clicked`: Card click feedback

### Navigation Elements
- `.nav-btn`: Navigation button styling
- `.loading`: Loading state styling
- `.disabled`: Disabled button state

### Action Elements
- `.action-btn`: Action button styling
- `.refresh-btn`: Refresh button specific
- `.export-btn`: Export button specific
- `.add-row-btn`: Add row button specific

### Tooltip Elements
- `.template-tooltip`: Tooltip container
- `.tooltip-title`: Tooltip title
- `.tooltip-details`: Tooltip details
- `.tooltip-instruction`: Usage instruction

## Event Handling

### Drag and Drop Events
- `dragstart`: Template drag initiation
- `dragend`: Template drag completion
- `click`: Template click for mobile

### Button Events
- `click`: Button activation
- `keydown`: Keyboard support (Enter/Space)

### Keyboard Events
- `keydown`: Global keyboard shortcuts
- Modifier key detection (Ctrl/Cmd)
- Input field exclusion

## Integration Points

### Main Application
- Calls scheduler navigation methods
- Updates scheduler state
- Triggers data loading and rendering

### Template System
- Integrates with drag and drop system
- Provides template configurations
- Supports mobile interactions

### Date Management
- Updates date display
- Handles date range navigation
- Synchronizes with scheduler state

## Performance Considerations

### Event Management
- Proper event listener cleanup
- Efficient event delegation
- Minimal DOM queries

### State Updates
- Batched state updates
- Efficient re-rendering
- Loading state management

### Memory Management
- Reference cleanup on destroy
- Event listener removal
- Proper garbage collection

## Dependencies
- SchedulerApp: Main application reference
- SchedulerUtils: Date utilities
- Material Design Icons: Icon classes
- DOM APIs: Event handling and manipulation

## Integration
The ToolbarManager is instantiated by the main SchedulerApp and provides the primary user interface for scheduler interaction. It coordinates with other managers to provide seamless navigation, template usage, and action execution while maintaining consistent state and visual feedback.
