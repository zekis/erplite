# ResourceUtils.js Documentation

## Overview
Handles resource-related operations like avatars, colors, and icons. Provides static methods for creating visual representations of resources, managing resource types, and generating consistent styling across the scheduler application.

## Class: ResourceUtils

### Constants

#### `AVATAR_COLORS`
Color palette for resource avatars with consistent, visually distinct colors.
```javascript
static AVATAR_COLORS = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b',
    '#8b5cf6', '#06b6d4', '#84cc16', '#f97316',
    '#ec4899', '#6366f1', '#14b8a6', '#eab308'
];
```

#### `RESOURCE_TYPE_ICONS`
Mapping of resource types to Material Design Icon classes.
```javascript
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
```

### Avatar Creation

#### `createResourceAvatar(resource, size)`
Creates a resource avatar with initials and background color.

**Parameters:**
- `resource`: Resource object with resource_name property
- `size`: Avatar size in pixels (default: 24)

**Returns:** `string` - HTML string for avatar element

**Features:**
- Circular design with initials
- Consistent color based on name hash
- Responsive sizing
- Fallback for invalid resources

**Example:**
```javascript
const avatar = ResourceUtils.createResourceAvatar({
    resource_name: 'John Doe'
}, 32);
// Returns: <div class="resource-avatar" style="...">JD</div>
```

#### `createDefaultAvatar(size)`
Creates a default avatar for unassigned resources.

**Parameters:**
- `size`: Avatar size in pixels (default: 24)

**Returns:** `string` - HTML string for default avatar

**Features:**
- Gray background color
- Account-off icon
- Consistent with resource avatars

### Name and Color Processing

#### `getResourceInitials(name)`
Extracts initials from a resource name.

**Parameters:**
- `name`: Resource name string

**Returns:** `string` - Initials (max 2 characters, uppercase)

**Algorithm:**
1. Splits name by spaces
2. Takes first letter of each word
3. Joins and limits to 2 characters
4. Converts to uppercase

**Example:**
```javascript
const initials = ResourceUtils.getResourceInitials('John Doe Smith'); // "JD"
const single = ResourceUtils.getResourceInitials('Madonna'); // "M"
```

#### `getResourceColor(name)`
Generates consistent color for a resource based on name hash.

**Parameters:**
- `name`: Resource name string

**Returns:** `string` - Hex color code

**Algorithm:**
1. Creates hash from name characters
2. Uses modulo to select from color palette
3. Returns consistent color for same name

**Example:**
```javascript
const color = ResourceUtils.getResourceColor('John Doe'); // "#3b82f6" (always same for "John Doe")
```

### Resource Type Management

#### `getResourceTypeIcon(resourceType)`
Returns Material Design Icon class for a resource type.

**Parameters:**
- `resourceType`: Type of resource (string)

**Returns:** `string` - Material Design Icon class

**Fallback:** Returns 'mdi-account' for unknown types

**Example:**
```javascript
const icon = ResourceUtils.getResourceTypeIcon('equipment'); // "mdi-tools"
const person = ResourceUtils.getResourceTypeIcon('employee'); // "mdi-account"
```

#### `createResourceTypeIndicator(resourceType, count)`
Creates a visual indicator showing resource type and count.

**Parameters:**
- `resourceType`: Type of resource
- `count`: Number of resources of this type

**Returns:** `string` - HTML string for type indicator

**Example:**
```javascript
const indicator = ResourceUtils.createResourceTypeIndicator('person', 3);
// Returns: <div class="resource-type-indicator">
//            <i class="mdi mdi-account"></i>
//            <span>3</span>
//          </div>
```

#### `createNoResourcesIndicator()`
Creates indicator for when no resources are assigned.

**Returns:** `string` - HTML string for no resources indicator

**Example:**
```javascript
const indicator = ResourceUtils.createNoResourcesIndicator();
// Returns: <div class="no-resources-indicator">
//            <i class="mdi mdi-account-off-outline"></i>
//            <span>No Resources</span>
//          </div>
```

### Resource Grouping and Analysis

#### `groupResourcesByType(resources, scheduleRows, projectFilter)`
Groups resources by type and counts them based on usage in schedule rows.

**Parameters:**
- `resources`: Array of resource objects
- `scheduleRows`: Array of schedule rows (default: [])
- `projectFilter`: Optional project filter (default: null)

**Returns:** `object` - Object with resource type counts

**Process:**
1. Filters schedule rows by project if specified
2. Finds unique resources in filtered rows
3. Groups by resource type
4. Counts occurrences of each type

**Example:**
```javascript
const counts = ResourceUtils.groupResourcesByType(resources, scheduleRows, 'PROJECT-001');
// Returns: { person: 2, equipment: 1, vehicle: 1 }
```

#### `createResourceSummary(resourceTypeCounts)`
Creates a visual summary of resource types and counts.

**Parameters:**
- `resourceTypeCounts`: Object with resource type counts

**Returns:** `string` - HTML string for resource summary

**Features:**
- Shows type indicators for each resource type
- Handles empty state with no resources indicator
- Responsive layout with flex wrapping

**Example:**
```javascript
const summary = ResourceUtils.createResourceSummary({ person: 2, equipment: 1 });
// Returns: <div class="resource-summary">
//            [person indicator] [equipment indicator]
//          </div>
```

### Resource Validation

#### `isValidResource(resource)`
Validates if an object is a valid resource.

**Parameters:**
- `resource`: Object to validate

**Returns:** `boolean` - True if valid resource

**Validation Criteria:**
- Object exists and is not null
- Has resource_name property
- resource_name is a non-empty string

**Example:**
```javascript
const valid = ResourceUtils.isValidResource({
    resource_name: 'John Doe',
    resource_type: 'person'
}); // true

const invalid = ResourceUtils.isValidResource({
    name: 'John Doe' // missing resource_name
}); // false
```

#### `getResourceDisplayName(resource)`
Gets the display name for a resource with fallback.

**Parameters:**
- `resource`: Resource object

**Returns:** `string` - Display name or fallback

**Example:**
```javascript
const name = ResourceUtils.getResourceDisplayName({
    resource_name: '  John Doe  '
}); // "John Doe" (trimmed)

const fallback = ResourceUtils.getResourceDisplayName(null); // "Unknown Resource"
```

#### `getResourceTypeDisplayName(resourceType)`
Gets formatted display name for a resource type.

**Parameters:**
- `resourceType`: Resource type string

**Returns:** `string` - Formatted display name

**Example:**
```javascript
const display = ResourceUtils.getResourceTypeDisplayName('equipment'); // "Equipment"
const fallback = ResourceUtils.getResourceTypeDisplayName(null); // "Person"
```

## Usage Examples

### Creating Avatars
```javascript
// Create resource avatar
const avatar = ResourceUtils.createResourceAvatar({
    resource_name: 'John Doe',
    resource_type: 'person'
}, 32);

// Create default avatar for unassigned
const defaultAvatar = ResourceUtils.createDefaultAvatar(24);
```

### Resource Analysis
```javascript
// Group resources by type for a project
const typeCounts = ResourceUtils.groupResourcesByType(
    resources, 
    scheduleRows, 
    'PROJECT-001'
);

// Create visual summary
const summary = ResourceUtils.createResourceSummary(typeCounts);
```

### Resource Information
```javascript
// Get resource details
const initials = ResourceUtils.getResourceInitials('John Doe Smith');
const color = ResourceUtils.getResourceColor('John Doe Smith');
const icon = ResourceUtils.getResourceTypeIcon('equipment');

// Validate resource
if (ResourceUtils.isValidResource(resource)) {
    const displayName = ResourceUtils.getResourceDisplayName(resource);
}
```

### Type Indicators
```javascript
// Create type indicator
const indicator = ResourceUtils.createResourceTypeIndicator('person', 5);

// Handle no resources
const noResources = ResourceUtils.createNoResourcesIndicator();
```

## Visual Design

### Avatar Styling
- Circular design with consistent sizing
- Color-coded backgrounds based on name hash
- White text for contrast
- Initials centered and properly sized
- Responsive to size parameter

### Type Indicators
- Icon and count display
- Consistent spacing and alignment
- Color-coded icons for different types
- Flexible layout for multiple types

### Color Palette
The avatar colors are carefully selected for:
- Visual distinction between resources
- Accessibility and contrast
- Professional appearance
- Consistent branding

## CSS Classes Generated

### Avatar Classes
- `.resource-avatar`: Main avatar container
- `.resource-avatar.default`: Default/unassigned avatar
- `.avatar-initials`: Initials text span

### Indicator Classes
- `.resource-type-indicator`: Type indicator container
- `.resource-summary`: Summary container
- `.no-resources-indicator`: No resources state

## Performance Considerations

### Efficient Processing
- Hash-based color selection for consistency
- Minimal DOM string generation
- Cached icon mappings
- Optimized string operations

### Memory Management
- Static methods with no instance state
- Minimal object creation
- Efficient string concatenation
- No memory leaks from closures

## Error Handling

All methods include robust error handling:
- Input validation with fallbacks
- Safe property access
- Default values for missing data
- Graceful degradation for edge cases

## Dependencies
- Material Design Icons: Icon classes
- No external libraries required
- Pure JavaScript implementation

## Integration
ResourceUtils is used throughout the scheduler system for consistent resource representation. It integrates with:
- DropdownManager: Resource selection dropdowns
- RowRenderer: Resource cells and displays
- Project headers: Resource summaries
- Schedule rows: Resource assignments

The utility class ensures consistent visual representation and behavior for all resource-related operations across the application.
