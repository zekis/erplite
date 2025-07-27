# Active Context - Timesheet Calendar Bug Fix

## Current Task - COMPLETED
Fixed critical bug in timesheet-calendar app where creating timesheet entries resulted in "Error: Value missing for Timesheet Entry: Activity".

## Root Cause Analysis
The issue was a mismatch between frontend and backend field naming:
- **Frontend**: Sending `activity` field in timesheet entry data
- **Backend**: Expecting and using `task` field instead of `activity`
- **Result**: Backend received `null` for activity field, causing validation error

## Changes Made

### 1. Backend API Updates (`erplite/projects/api.py`)
- ✅ Updated `save_timesheet_entries()` method to use `activity` instead of `task`
- ✅ Fixed both create and update entry logic
- ✅ Updated response data to return `activity` instead of `task`
- ✅ Added missing API methods:
  - `get_projects_and_activities()` - Get project/activity data for dropdowns
  - `get_week_timesheets()` - Load existing timesheet entries for a week
  - `export_timesheet_data()` - Export timesheet data in CSV/JSON format
  - `save_user_preferences()` - Save user preferences
  - `get_user_preferences()` - Load user preferences

### 2. Field Mapping Fix
**Before:**
```python
task = entry.get('task')  # Frontend sends 'activity', so this was None
timesheet_doc.task = task  # Saving None to database
```

**After:**
```python
activity = entry.get('activity')  # Correctly get 'activity' field
timesheet_doc.activity = activity  # Save to correct field
```

## Current Status
- ✅ Backend API completely updated to use `activity` field
- ✅ All missing API methods implemented
- ✅ Frontend-backend field mapping aligned
- ✅ Main bug fix complete - timesheet entries can be created
- ✅ Edit dialog activity dropdown fix implemented

## Additional Fix - Edit Dialog Activity Dropdown
**Issue**: Edit dialog showed empty activity select box when editing existing timesheet entries.

**Root Cause**: The `updateActivityOptions()` method in ModalComponent was trying to get activities from sidebar DOM elements instead of using API data.

**Solution**: 
- Updated ModalComponent to use `this.app.state.projectsData` from API instead of DOM elements
- Added `loadProjectsData()` method to TimesheetCalendar to fetch projects/activities data on initialization
- Modal now properly populates activity dropdown based on selected project

## Next Steps
1. ✅ Test timesheet entry creation in the calendar interface
2. ✅ Verify that entries save successfully without validation errors
3. ✅ Test edit dialog activity dropdown population
4. Test loading existing entries for a week

## Additional Update - Calendar View Hours
**Request**: Update the calendar view to show 6am to 6pm as the half day view instead of 8am to 6pm.

**Changes Made**:
- Updated `CalendarManager.toggleHourRange()` to use 6-18 hours for half day view
- Updated `CalendarManager.highlightCurrentTime()` to use 6am start time for current time line
- Updated `CalendarManager.forceFullDayView()` tooltip to reflect new 6am-6pm range
- Updated `TimesheetCalendar.initializeExistingTimeBlocks()` to check for entries outside 6-18 hours
- Updated `TimesheetCalendar.addQuickTime()` to use 6am minimum start time
- **Fixed HTML Template**: Updated `erplite/www/timesheet-calendar/index.html` to show hours 6-19 instead of 8-18 in the initial calendar rendering
- **Fixed Range Issue**: Updated all JavaScript ranges from 6-18 to 6-19 to include the full 6pm hour (18:00-18:59)

**Result**: Half day view now shows 6am to 6pm instead of 8am to 6pm, providing 2 additional hours in the morning for timesheet entries. The calendar properly displays the complete 6am-6pm range including the full 6pm hour on initial page load and when toggling views.

## Additional Update - Sidebar Collapse Consolidation
**Request**: Consolidate the duplicate collapse buttons in the projects and activities list - there was a project-level collapse and another activity-level collapse when there were many tasks.

**Changes Made**:
- Removed the redundant activity-level collapse system (`addActivityToggle()`, `toggleActivitys()` methods)
- Enhanced the main project toggle to show activity count: `▼ 5 activities` instead of just `▼`
- Updated `enhanceProjectToggles()` to display activity counts in the toggle text
- Updated `toggleProject()` to maintain activity count in both collapsed and expanded states
- Projects with more than 5 activities are initially collapsed to reduce clutter
- Single, consistent collapse mechanism for better UX

**Result**: Cleaner sidebar interface with a single, informative collapse button per project that shows the activity count and eliminates confusion from having multiple collapse mechanisms.

## Technical Notes
- Frontend was already correctly updated to use `activity` terminology
- Backend needed to catch up with the Task→Activity migration
- All API methods now consistently use `activity` field
- Maintained backward compatibility where possible
