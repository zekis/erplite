# SchedulerUtils.js Documentation

## Overview
General utility functions for the scheduler application. Provides static methods for date manipulation, validation, formatting, color conversion, and other common operations used throughout the scheduler system.

## Class: SchedulerUtils

### Constants

#### `DATE_REGEX`
Regular expression for validating YYYY-MM-DD date format.
```javascript
static DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;
```

#### `TEMPLATE_CONFIGS`
Configuration objects for drag and drop templates.
```javascript
static TEMPLATE_CONFIGS = {
    '8h': { name: '8 Hour Shift', hours: 8, start_time: '09:00', end_time: '17:00', ... },
    '12h': { name: '12 Hour Shift', hours: 12, start_time: '07:00', end_time: '19:00', ... },
    'leave': { name: 'Leave', hours: 8, start_time: '00:00', end_time: '23:59', ... }
}
```

### Date Utilities

#### `getTodayString()`
Returns today's date as YYYY-MM-DD string.

**Returns:** `string` - Today's date in ISO format

**Example:**
```javascript
const today = SchedulerUtils.getTodayString(); // "2024-01-15"
```

#### `addDays(dateString, days)`
Adds or subtracts days from a date string.

**Parameters:**
- `dateString`: Date in YYYY-MM-DD format
- `days`: Number of days to add (negative for subtraction)

**Returns:** `string` - New date in YYYY-MM-DD format

**Example:**
```javascript
const nextWeek = SchedulerUtils.addDays('2024-01-15', 7); // "2024-01-22"
const lastWeek = SchedulerUtils.addDays('2024-01-15', -7); // "2024-01-08"
```

#### `calculateDaysBetween(startDate, endDate)`
Calculates the number of days between two dates (inclusive).

**Parameters:**
- `startDate`: Start date in YYYY-MM-DD format
- `endDate`: End date in YYYY-MM-DD format

**Returns:** `number` - Number of days between dates (0 if invalid)

**Example:**
```javascript
const days = SchedulerUtils.calculateDaysBetween('2024-01-15', '2024-01-17'); // 2
```

#### `isConsecutiveDate(date1, date2)`
Checks if two dates are consecutive (date2 is one day after date1).

**Parameters:**
- `date1`: First date in YYYY-MM-DD format
- `date2`: Second date in YYYY-MM-DD format

**Returns:** `boolean` - True if dates are consecutive

**Example:**
```javascript
const consecutive = SchedulerUtils.isConsecutiveDate('2024-01-15', '2024-01-16'); // true
```

### Date Validation and Formatting

#### `isValidDateString(dateString)`
Validates if a string is in valid YYYY-MM-DD format.

**Parameters:**
- `dateString`: String to validate

**Returns:** `boolean` - True if valid date format

**Example:**
```javascript
const valid = SchedulerUtils.isValidDateString('2024-01-15'); // true
const invalid = SchedulerUtils.isValidDateString('01/15/2024'); // false
```

#### `isWeekend(dateString)`
Checks if a date falls on a weekend (Saturday or Sunday).

**Parameters:**
- `dateString`: Date in YYYY-MM-DD format

**Returns:** `boolean` - True if weekend

**Example:**
```javascript
const weekend = SchedulerUtils.isWeekend('2024-01-13'); // true (Saturday)
```

#### `isToday(dateString)`
Checks if a date is today.

**Parameters:**
- `dateString`: Date in YYYY-MM-DD format

**Returns:** `boolean` - True if date is today

#### `formatDate(dateString, options)`
Formats a date string for display.

**Parameters:**
- `dateString`: Date in YYYY-MM-DD format
- `options`: Intl.DateTimeFormat options (optional)

**Returns:** `string` - Formatted date string

**Example:**
```javascript
const formatted = SchedulerUtils.formatDate('2024-01-15'); // "Jan 15, 2024"
const custom = SchedulerUtils.formatDate('2024-01-15', { weekday: 'long' }); // "Monday"
```

### Color Utilities

#### `hexToRgba(hex, alpha)`
Converts hex color to RGBA with specified alpha.

**Parameters:**
- `hex`: Hex color code (with or without #)
- `alpha`: Alpha value 0-1 (default: 1)

**Returns:** `string` - RGBA color string

**Example:**
```javascript
const rgba = SchedulerUtils.hexToRgba('#3b82f6', 0.5); // "rgba(59,130,246,0.5)"
const rgb = SchedulerUtils.hexToRgba('3b82f6'); // "rgba(59,130,246,1)"
```

### ID Generation

#### `generateUniqueId(prefix)`
Generates a unique ID with optional prefix.

**Parameters:**
- `prefix`: Optional prefix for ID (default: 'id')

**Returns:** `string` - Unique ID

**Example:**
```javascript
const id = SchedulerUtils.generateUniqueId('entry'); // "entry_1642234567890_abc123def"
```

### Template Utilities

#### `getTemplateConfig(template)`
Returns configuration for a template type.

**Parameters:**
- `template`: Template key ('8h', '12h', 'leave')

**Returns:** `object` - Template configuration

**Example:**
```javascript
const config = SchedulerUtils.getTemplateConfig('8h');
// Returns: { name: '8 Hour Shift', hours: 8, start_time: '09:00', ... }
```

### Function Utilities

#### `debounce(func, wait)`
Creates a debounced version of a function.

**Parameters:**
- `func`: Function to debounce
- `wait`: Wait time in milliseconds

**Returns:** `function` - Debounced function

**Example:**
```javascript
const debouncedSearch = SchedulerUtils.debounce(searchFunction, 300);
```

#### `throttle(func, limit)`
Creates a throttled version of a function.

**Parameters:**
- `func`: Function to throttle
- `limit`: Time limit in milliseconds

**Returns:** `function` - Throttled function

**Example:**
```javascript
const throttledScroll = SchedulerUtils.throttle(scrollHandler, 100);
```

### Object Utilities

#### `deepClone(obj)`
Creates a deep clone of an object.

**Parameters:**
- `obj`: Object to clone

**Returns:** `object` - Cloned object

**Example:**
```javascript
const original = { a: 1, b: { c: 2 } };
const cloned = SchedulerUtils.deepClone(original);
```

#### `sanitizeHtml(str)`
Sanitizes HTML string to prevent XSS attacks.

**Parameters:**
- `str`: String to sanitize

**Returns:** `string` - Sanitized string

**Example:**
```javascript
const safe = SchedulerUtils.sanitizeHtml('<script>alert("xss")</script>'); // "&lt;script&gt;alert("xss")&lt;/script&gt;"
```

### Entry Grouping

#### `canEntriesBeGrouped(entry1, entry2)`
Checks if two entries can be grouped together based on identical properties.

**Parameters:**
- `entry1`: First entry object
- `entry2`: Second entry object

**Returns:** `boolean` - True if entries can be grouped

**Comparison Criteria:**
- Hours (default: 8)
- Start time (default: '09:00')
- End time (default: '17:00')
- Status (default: 'planned')

#### `groupConsecutiveEntries(entries)`
Groups consecutive entries with identical properties into blocks.

**Parameters:**
- `entries`: Object with date keys and entry values

**Returns:** `array` - Array of grouped blocks

**Example:**
```javascript
const entries = {
    '2024-01-15': { hours: 8, start_time: '09:00', end_time: '17:00' },
    '2024-01-16': { hours: 8, start_time: '09:00', end_time: '17:00' },
    '2024-01-18': { hours: 6, start_time: '10:00', end_time: '16:00' }
};

const blocks = SchedulerUtils.groupConsecutiveEntries(entries);
// Returns: [
//   { start_date: '2024-01-15', end_date: '2024-01-16', hours: 8, ... },
//   { start_date: '2024-01-18', end_date: '2024-01-18', hours: 6, ... }
// ]
```

### Date Range Utilities

#### `createDateRange(startDate, days)`
Creates an array of date strings for a range.

**Parameters:**
- `startDate`: Start date in YYYY-MM-DD format
- `days`: Number of days

**Returns:** `array` - Array of date strings

**Example:**
```javascript
const range = SchedulerUtils.createDateRange('2024-01-15', 3);
// Returns: ['2024-01-15', '2024-01-16', '2024-01-17']
```

#### `getDateRangeDisplay(startDate, days)`
Gets formatted date range display string.

**Parameters:**
- `startDate`: Start date
- `days`: Number of days

**Returns:** `string` - Formatted date range

**Example:**
```javascript
const display = SchedulerUtils.getDateRangeDisplay('2024-01-15', 7);
// Returns: "Jan 15, 2024 - Jan 21, 2024"
```

### Time Utilities

#### `isValidTimeString(timeString)`
Validates if a string is in valid HH:MM format.

**Parameters:**
- `timeString`: Time string to validate

**Returns:** `boolean` - True if valid time format

**Example:**
```javascript
const valid = SchedulerUtils.isValidTimeString('09:30'); // true
const invalid = SchedulerUtils.isValidTimeString('9:30 AM'); // false
```

#### `formatTime(timeString)`
Formats time string for display (converts to 12-hour format).

**Parameters:**
- `timeString`: Time in HH:MM format

**Returns:** `string` - Formatted time string

**Example:**
```javascript
const formatted = SchedulerUtils.formatTime('14:30'); // "2:30 PM"
const morning = SchedulerUtils.formatTime('09:00'); // "9:00 AM"
```

#### `calculateDuration(startTime, endTime)`
Calculates duration between two times in hours.

**Parameters:**
- `startTime`: Start time in HH:MM format
- `endTime`: End time in HH:MM format

**Returns:** `number` - Duration in hours

**Example:**
```javascript
const duration = SchedulerUtils.calculateDuration('09:00', '17:00'); // 8
const overnight = SchedulerUtils.calculateDuration('22:00', '06:00'); // 8 (handles overnight)
```

## Usage Examples

### Date Operations
```javascript
// Get today and calculate future dates
const today = SchedulerUtils.getTodayString();
const nextWeek = SchedulerUtils.addDays(today, 7);
const daysBetween = SchedulerUtils.calculateDaysBetween(today, nextWeek);

// Validate and format dates
if (SchedulerUtils.isValidDateString(dateInput)) {
    const formatted = SchedulerUtils.formatDate(dateInput);
    const isWeekend = SchedulerUtils.isWeekend(dateInput);
}
```

### Color and Visual
```javascript
// Convert colors and generate IDs
const rgba = SchedulerUtils.hexToRgba('#3b82f6', 0.3);
const uniqueId = SchedulerUtils.generateUniqueId('block');

// Sanitize user input
const safeHtml = SchedulerUtils.sanitizeHtml(userInput);
```

### Entry Processing
```javascript
// Group consecutive entries
const entries = { /* daily entries */ };
const blocks = SchedulerUtils.groupConsecutiveEntries(entries);

// Check if entries can be grouped
const canGroup = SchedulerUtils.canEntriesBeGrouped(entry1, entry2);
```

### Function Optimization
```javascript
// Debounce search function
const debouncedSearch = SchedulerUtils.debounce((query) => {
    // Search logic
}, 300);

// Throttle scroll handler
const throttledScroll = SchedulerUtils.throttle((event) => {
    // Scroll logic
}, 100);
```

## Error Handling

All utility functions include comprehensive error handling:
- Input validation with fallback values
- Try-catch blocks for complex operations
- Console warnings for invalid inputs
- Graceful degradation for edge cases

## Performance Considerations

- Static methods for optimal performance
- Minimal object creation
- Efficient algorithms for date calculations
- Cached regex patterns
- Optimized string operations

## Dependencies
- Native JavaScript Date API
- DOM APIs for HTML sanitization
- No external libraries required

## Integration
SchedulerUtils is used throughout the scheduler system as a static utility class. All methods are pure functions that don't modify global state, making them safe to use anywhere in the application.
