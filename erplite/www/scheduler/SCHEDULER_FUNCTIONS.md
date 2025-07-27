# Scheduler JavaScript Functions Reference

This document provides a comprehensive overview of all functions across the scheduler JavaScript files to help identify duplications and ensure proper organization.

## Core Application Files

### **Scheduler.js** - Main Application Controller
- `init()` - Initialize the scheduler application
- `loadInitialData()` - Load initial data from window object (delegates to DataManager)
- `loadSchedulerData()` - Load scheduler data from API (delegates to DataManager)
- `renderAll()` - Render all components (date columns, schedule rows)
- `updateDateRange()` - Update date range display in toolbar
- `renderDateColumns()` - Render date column headers
- `renderScheduleRows()` - Render all schedule rows using RowRenderer
- `setupScrollSynchronization()` - Sync scroll between left and right sections
- `navigateDate(days)` - Navigate to different date range
- `refreshData()` - Reload scheduler data
- `exportSchedule()` - Export schedule (placeholder)
- `addNewRow()` - Add new empty schedule row
- `setLoading(loading)` - Show/hide loading overlay
- `showToast(message, type)` - Show toast notification
- `cleanup()` - Cleanup event listeners and resources
- `handleResize()` - Handle window resize events

#### **Dropdown Management (Delegates to DropdownManager)**
- `showProjectDropdown(cell, rowIndex)` - Show project selection dropdown
- `showActivityDropdown(cell, rowIndex)` - Show activity selection dropdown
- `showRoleDropdown(cell, rowIndex)` - Show role selection dropdown
- `showPersonDropdown(cell, rowIndex)` - Show resource selection dropdown
- `hideAllDropdowns()` - Hide all open dropdowns

#### **Row Management (Delegates to ScheduleRowManager)**
- `selectProject(rowIndex, project)` - Select project for a row
- `selectActivity(rowIndex, activity)` - Select activity for a row
- `selectRole(rowIndex, role)` - Select role for a row
- `selectPerson(rowIndex, resource)` - Select resource for a row
- `deleteRow(rowIndex)` - Delete a schedule row
- `copyActivityDown(rowIndex)` - Copy activity row below current

#### **Time Entry Management (Delegates to TimeBlockManager)**
- `createTimeEntry(entry, date, row)` - Create time entry display element
- `addSingleTimeEntry(rowIndex, date)` - Add single time entry
- `addMultipleTimeEntries(rowIndex, dates)` - Add time entries for multiple dates
- `editTimeEntry(scheduleRowId, date, entry)` - Edit existing time entry
- `updateTimeEntry(scheduleRowId, date, hours)` - Update time entry hours

#### **Shift Creation (New Drag-to-Select Feature)**
- `handleCellClick(event, rowIndex, date)` - Handle single cell click
- `handleCellMouseDown(event, rowIndex, date)` - Start drag selection
- `handleDragSelection(event)` - Handle drag selection movement
- `endDragSelection(event)` - End drag selection and show context menu
- `showShiftContextMenu(x, y)` - Show shift creation context menu
- `hideShiftContextMenu()` - Hide context menu and clear selection
- `openCreateShiftDialog()` - Open shift configuration dialog
- `closeShiftModal()` - Close shift dialog and clear selection
- `calculateShiftHours()` - Calculate hours from start/end times
- `timeToMinutes(timeString)` - Convert time string to minutes
- `saveShift()` - Save configured shift to database
- `formatDateForDisplay(dateString)` - Format date for display

#### **Legacy Entry Modal Management**
- `openEntryModal(entry, prefill)` - Open entry creation/edit modal
- `closeEntryModal()` - Close entry modal
- `populateModalSelectors()` - Populate modal dropdowns
- `populateModalWithEntry(entry)` - Fill modal with entry data
- `prefillModal(prefill)` - Pre-fill modal with data
- `updateEntryActivityOptions()` - Update activity options based on project
- `clearModal()` - Clear modal form
- `saveEntry()` - Save entry from modal

#### **Utility Functions (Should be moved to SchedulerUtils)**
- `getTodayString()` - Get today's date string
- `addDays(dateString, days)` - Add days to date string
- `calculateDaysBetween(startDate, endDate)` - Calculate days between dates
- `hexToRgba(hex, alpha)` - Convert hex color to rgba
- `generateEntryId()` - Generate unique entry ID
- `formatDateForDisplay(dateString)` - Format date for display

#### **Delegation Methods (Should be removed - duplicates)**
- `editTimeBlock(rowIndex, blockData, type)` - Delegates to TimeBlockManager
- `updateTimeBlock(rowIndex, blockData, updates)` - Delegates to TimeBlockManager
- `startResize(event, card, direction, rowIndex, blockData)` - Delegates to TimeBlockManager
- `groupConsecutiveEntries(entries)` - Delegates to SchedulerUtils
- `canEntriesBeGrouped(block, entry)` - Delegates to SchedulerUtils
- `isConsecutiveDate(date1, date2)` - Delegates to SchedulerUtils
- `createResourceAvatar(resource)` - Delegates to ResourceUtils
- `getResourceColor(name)` - Delegates to ResourceUtils
- `getResourceTypeIcon(resourceType)` - Delegates to ResourceUtils

## Manager Classes

### **DataManager.js** - Data Loading and API Management
- `loadInitialData()` - Load data from window object
- `loadSchedulerData()` - Load data from API
- `processScheduleRowsFromAPI(scheduleRowsData)` - Process API response
- `processScheduleRows()` - Process schedule rows for display
- `addDefaultProjectsToGroups(projectGroups)` - Add default projects
- `addDefaultProjects(projectGroups)` - Add default projects (duplicate?)
- `getResourceName(resourceId)` - Get resource name by ID
- `createScheduleEntry(formData)` - Create new schedule entry
- `updateScheduleEntry(entryId, formData)` - Update schedule entry
- `deleteScheduleEntry(entryId)` - Delete schedule entry
- `refreshData()` - Refresh all data
- `navigateDate(days)` - Navigate date range
- `apiCall(method, args)` - Make API calls to backend
- `getTodayString()` - Get today's date (duplicate of SchedulerUtils)
- `addDays(dateString, days)` - Add days to date (duplicate of SchedulerUtils)
- `validateScheduleEntry(formData)` - Validate entry data
- `getProject(projectId)` - Get project by ID
- `getActivity(projectId, activityId)` - Get activity by ID
- `getResource(resourceId)` - Get resource by ID
- `getRole(roleId)` - Get role by ID
- `getActiveProjects()` - Get active projects
- `getProjectColor(projectId)` - Get project color
- `isDataLoaded()` - Check if data is loaded
- `getDataSummary()` - Get data summary

### **ScheduleRowManager.js** - Schedule Row Operations
- `createScheduleRow(project, activity, resource, role)` - Create new schedule row
- `updateScheduleRowRole(scheduleRowId, role)` - Update row role
- `updateScheduleRowResource(scheduleRowId, resource)` - Update row resource
- `updateScheduleRowEntries(scheduleRowId, entriesJson)` - Update row entries
- `getScheduleRowExpanded(scheduleRowId)` - Get expanded row data
- `selectProject(rowIndex, project)` - Select project for row
- `selectActivity(rowIndex, activity)` - Select activity for row
- `selectRole(rowIndex, role)` - Select role for row
- `selectResource(rowIndex, resource)` - Select resource for row
- `addSingleTimeEntry(rowIndex, date)` - Add single time entry (duplicate of TimeBlockManager)
- `addMultipleTimeEntries(rowIndex, dates)` - Add multiple time entries (duplicate of TimeBlockManager)
- `updateTimeEntry(scheduleRowId, date, hours)` - Update time entry (duplicate of TimeBlockManager)
- `updateTimeBlock(rowIndex, blockData, updates)` - Update time block (duplicate of TimeBlockManager)
- `handleTemplateDrop(template, rowIndex, date)` - Handle template drop
- `deleteRow(rowIndex)` - Delete schedule row
- `copyActivityDown(rowIndex)` - Copy activity down

### **DropdownManager.js** - Dropdown UI Management
- `showProjectDropdown(cell, rowIndex)` - Show project dropdown
- `showActivityDropdown(cell, rowIndex)` - Show activity dropdown
- `showRoleDropdown(cell, rowIndex)` - Show role dropdown
- `showResourceDropdown(cell, rowIndex)` - Show resource dropdown
- `createDropdown(type, cell)` - Create dropdown element
- `createSearchInput(placeholder)` - Create search input
- `createProjectItem(project, rowIndex)` - Create project dropdown item
- `createActivityItem(activity, rowIndex)` - Create activity dropdown item
- `createRoleItem(role, rowIndex)` - Create role dropdown item
- `createResourceItem(resource, rowIndex)` - Create resource dropdown item
- `createResourceAvatar(resource)` - Create resource avatar (duplicate of ResourceUtils)
- `getAvailabilityStatus(resource)` - Get resource availability
- `createResourceFilters()` - Create resource filter buttons
- `setupSearch(searchInput, listContainer, type)` - Setup search functionality
- `setupResourceFilters(filtersContainer, listContainer)` - Setup resource filters
- `handleKeyboardNavigation(e, listContainer)` - Handle keyboard navigation
- `updateNoResultsMessage(listContainer, searchTerm)` - Update no results message
- `positionDropdown(dropdown, cell)` - Position dropdown relative to cell
- `adjustDropdownPosition(dropdown)` - Adjust dropdown position for viewport
- `setupOutsideClickHandler()` - Setup outside click handling
- `handleOutsideClick(event)` - Handle outside click
- `hideAllDropdowns()` - Hide all dropdowns
- `cleanup()` - Cleanup dropdown resources

### **RowRenderer.js** - Row Rendering
- `createScheduleRow(row, index)` - Create complete schedule row
- `createProjectActivityCell(row, index)` - Create project/activity cell
- `createRoleCell(row, index)` - Create role cell
- `createResourceCell(row, index)` - Create resource cell
- `createDayCell(row, date, rowIndex)` - Create day cell with interactions
- `createScheduleEntry(entry)` - Create schedule entry element
- `createTimeEntry(entry, date, row)` - Create time entry element

### **TimeBlockManager.js** - Time Block Management
- `renderTimeBlockCards()` - Render all time block cards
- `renderTimeBlockCard(rowIndex, blockData, type, row)` - Render single time block
- `editTimeBlock(rowIndex, blockData, type)` - Edit time block
- `updateTimeBlock(rowIndex, blockData, updates)` - Update time block
- `startResize(event, card, direction, rowIndex, blockData)` - Start resize operation
- `handleResize(event)` - Handle resize movement
- `endResize(event)` - End resize operation
- `highlightDateRange(rowIndex, startDate, endDate)` - Highlight date range during resize
- `updateCardVisualDuringResize(card, daysContainer, startDate, endDate)` - Update card during resize
- `applyResize(rowIndex, originalBlockData, newStartDate, newEndDate)` - Apply resize changes
- `groupConsecutiveEntries(entries)` - Group consecutive entries (delegates to SchedulerUtils)
- `canEntriesBeGrouped(block, entry)` - Check if entries can be grouped (delegates to SchedulerUtils)
- `addMultipleTimeEntries(rowIndex, dates)` - Add multiple time entries
- `addSingleTimeEntry(rowIndex, date)` - Add single time entry
- `updateTimeEntry(scheduleRowId, date, hours)` - Update time entry
- `editTimeEntry(scheduleRowId, date, entry)` - Edit time entry
- `darkenColor(color, percent)` - Darken color for night shifts
- `cleanup()` - Cleanup time block resources

### **ToolbarManager.js** - Toolbar Management
- `init()` - Initialize toolbar
- `initializeTemplateCards()` - Initialize template cards
- `initializeNavigationButtons()` - Initialize navigation buttons
- `initializeActionButtons()` - Initialize action buttons
- `initializeDateDisplay()` - Initialize date display
- `handleTemplateDragStart(event, card)` - Handle template drag start
- `handleTemplateDragEnd(event, card)` - Handle template drag end
- `handleTemplateClick(event, card)` - Handle template click
- `showTemplateInfo(card, config)` - Show template information
- `getTemplateConfig(template)` - Get template configuration (delegates to SchedulerUtils)
- `navigateDate(days)` - Navigate date range
- `updateDateDisplay()` - Update date display
- `refreshData()` - Refresh data
- `exportSchedule()` - Export schedule
- `addNewRow()` - Add new row
- `setLoading(loading)` - Set loading state
- `updateToolbarState()` - Update toolbar state
- `initializeKeyboardShortcuts()` - Initialize keyboard shortcuts
- `cleanup()` - Cleanup toolbar resources

## Utility Classes

### **SchedulerUtils.js** - General Utilities
- `getTodayString()` - Get today's date string
- `addDays(dateString, days)` - Add days to date string
- `calculateDaysBetween(startDate, endDate)` - Calculate days between dates
- `isConsecutiveDate(date1, date2)` - Check if dates are consecutive
- `isValidDateString(dateString)` - Validate date string
- `isWeekend(dateString)` - Check if date is weekend
- `isToday(dateString)` - Check if date is today
- `formatDate(dateString, options)` - Format date with options
- `hexToRgba(hex, alpha)` - Convert hex to rgba
- `generateUniqueId(prefix)` - Generate unique ID
- `getTemplateConfig(template)` - Get template configuration
- `debounce(func, wait)` - Debounce function calls
- `throttle(func, limit)` - Throttle function calls
- `deepClone(obj)` - Deep clone object
- `sanitizeHtml(str)` - Sanitize HTML string
- `canEntriesBeGrouped(entry1, entry2)` - Check if entries can be grouped
- `groupConsecutiveEntries(entries)` - Group consecutive entries
- `createDateRange(startDate, days)` - Create date range array
- `getDateRangeDisplay(startDate, days)` - Get date range display string
- `isValidTimeString(timeString)` - Validate time string
- `formatTime(timeString)` - Format time string
- `calculateDuration(startTime, endTime)` - Calculate duration between times

### **ResourceUtils.js** - Resource-Specific Utilities
- `createResourceAvatar(resource, size)` - Create resource avatar element
- `createDefaultAvatar(size)` - Create default avatar
- `getResourceInitials(name)` - Get initials from name
- `getResourceColor(name)` - Get color for resource
- `getResourceTypeIcon(resourceType)` - Get icon for resource type
- `createResourceTypeIndicator(resourceType, count)` - Create type indicator
- `createNoResourcesIndicator()` - Create no resources indicator
- `groupResourcesByType(resources, scheduleRows, projectFilter)` - Group resources by type
- `createResourceSummary(resourceTypeCounts)` - Create resource summary display
- `isValidResource(resource)` - Validate resource object
- `getResourceDisplayName(resource)` - Get display name for resource
- `getResourceTypeDisplayName(resourceType)` - Get display name for resource type

## Identified Issues and Recommendations

### **Function Duplications**
1. **Date/Time utilities** - Multiple files have `getTodayString()`, `addDays()`, etc. → Consolidate in SchedulerUtils
2. **Time entry management** - Functions exist in both ScheduleRowManager and TimeBlockManager → Consolidate in TimeBlockManager
3. **Resource avatar creation** - Exists in both DropdownManager and ResourceUtils → Use ResourceUtils only
4. **Template configuration** - Exists in both ToolbarManager and SchedulerUtils → Use SchedulerUtils only

### **Delegation Issues**
1. **Scheduler.js** has many delegation methods that just call other classes → Remove these wrapper methods
2. **API calls** - Should be centralized in DataManager, not scattered across files
3. **DOM manipulation** - Should be in appropriate renderer classes, not in manager classes

### **Recommended Refactoring**
1. **Remove delegation methods** from Scheduler.js that just call other classes
2. **Consolidate time entry functions** in TimeBlockManager.js
3. **Move all utility functions** to appropriate Utils classes
4. **Centralize API calls** in DataManager.js
5. **Separate concerns** - Keep rendering in RowRenderer, data in DataManager, interactions in managers
