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
3. Test edit dialog activity dropdown population
4. Test loading existing entries for a week

## Technical Notes
- Frontend was already correctly updated to use `activity` terminology
- Backend needed to catch up with the Task→Activity migration
- All API methods now consistently use `activity` field
- Maintained backward compatibility where possible
