# Scheduler Project Implementation Checklist

## Phase 1: Backend Setup & Doctypes

### 1.1 Create Division Doctype (NEW) ✅ COMPLETED
- [x] Create `erplite/scheduler/doctype/division/` directory
- [x] Create `division.json` (doctype definition)
- [x] Create `division.py` (controller)
- [x] Create `division.js` (client script)
- [x] Add fields:
  - [x] division_name (Data, Required) - "Technical Services", "Electrification"
  - [x] division_code (Data, Required) - "TS", "ELEC"
  - [x] description (Text Editor)
  - [x] is_active (Check, Default: 1)
  - [x] color (Color) - For visual identification

### 1.2 Create Scheduler Role Doctype (NEW) ✅ COMPLETED
- [x] Create `erplite/scheduler/doctype/scheduler_role/` directory (renamed to avoid conflict)
- [x] Create `scheduler_role.json` (doctype definition)
- [x] Create `scheduler_role.py` (controller)
- [x] Create `scheduler_role.js` (client script)
- [x] Add fields:
  - [x] role_name (Data, Required) - "Supervisor", "Electrician"
  - [x] role_code (Data, Required) - "SUP", "ELEC"
  - [x] description (Text Editor)
  - [x] is_active (Check, Default: 1)
  - [x] color (Color) - For visual identification
  - [x] hourly_rate (Currency) - Default rate for costing

### 1.3 Create Schedule Template Doctype (NEW) ✅ COMPLETED
- [x] Create `erplite/scheduler/doctype/schedule_template/` directory
- [x] Create `schedule_template.json` (doctype definition)
- [x] Create `schedule_template.py` (controller)
- [x] Create `schedule_template.js` (client script)
- [x] Add fields:
  - [x] template_name (Data, Required) - "8 Hour Shift", "12 Hour Shift"
  - [x] template_code (Data, Required) - "8h", "12h", "leave"
  - [x] hours (Float, Required) - Default hours (8, 12, 0)
  - [x] start_time (Time) - Default start time
  - [x] end_time (Time) - Default end time
  - [x] description (Text Editor)
  - [x] status (Select) - "planned", "leave", "overtime"
  - [x] is_active (Check, Default: 1)
  - [x] color (Color) - Template card color
  - [x] sort_order (Int) - Display order in scheduler

### 1.4 Create Resource Doctype (UPDATED) ✅ COMPLETED
- [x] Create `erplite/scheduler/` directory structure
- [x] Create `erplite/scheduler/doctype/resource/` directory
- [x] Create `resource.json` (doctype definition)
- [x] Create `resource.py` (controller)
- [x] Create `resource.js` (client script)
- [x] Add fields:
  - [x] resource_name (Data, Required)
  - [x] resource_type (Select: Person/Equipment/Other)
  - [x] status (Select: Active/Inactive)
  - [x] capacity (Float, default 8.0)
  - [x] default_role (Link to Scheduler Role) - NEW field added
  - [x] description (Text Editor)

### 1.5 Create Schedule Entry Doctype (UPDATED - Task→Activity) ✅ COMPLETED
- [x] Create `erplite/scheduler/doctype/schedule_entry/` directory
- [x] Create `schedule_entry.json` (doctype definition)
- [x] Create `schedule_entry.py` (controller)
- [x] Create `schedule_entry.js` (client script)
- [x] Update fields (Task→Activity rename):
  - [x] project (Link to Project, Required)
  - [x] activity (Link to Activity, Required) - RENAMED from task
  - [x] resource (Link to Resource)
  - [x] role (Link to Scheduler Role) - NEW field
  - [x] schedule_date (Date, Required)
  - [x] duration (Float, default 1.0)
  - [x] status (Select: Planned/In Progress/Completed/Cancelled)
  - [x] description (Text Editor)
  - [x] priority (Select: Low/Medium/High)

### 1.6 Update Schedule Row Doctype (UPDATED - Task→Activity) ✅ COMPLETED
- [x] Existing doctype structure
- [x] Update fields (Task→Activity rename):
  - [x] project (Link to Project)
  - [x] activity (Link to Activity) - RENAMED from task
  - [x] activity_name (Data) - RENAMED from task_name
  - [x] resource (Link to Resource)
  - [x] resource_name (Data)
  - [x] role (Link to Scheduler Role) - NEW field
  - [x] role_name (Data) - NEW field
  - [x] entries_json (Long Text)

### 1.7 Update Project Doctype (UPDATED)
- [ ] Add new fields:
  - [ ] division (Link to Division) - NEW field
  - [ ] work_type (Data) - NEW field
- [ ] Rename tasks to activities:
  - [ ] Update all task references to activity

### 1.8 Backend API (UPDATED)
- [x] Create `erplite/scheduler/api.py`
- [x] Implement `get_scheduler_data()` function
- [x] Implement `create_schedule_entry()` function
- [x] Implement `update_schedule_entry()` function
- [x] Implement `delete_schedule_entry()` function
- [x] Implement `get_resources()` function
- [ ] Update `get_projects_and_tasks()` → `get_projects_and_activities()`
- [ ] Add new API functions:
  - [ ] `get_divisions()` - Get all divisions
  - [ ] `get_roles()` - Get all roles
  - [ ] `get_schedule_templates()` - Get template configurations
  - [ ] `get_resources_by_role(role=None)` - Filter resources by role
  - [ ] Update `create_schedule_row_entry()` to include role parameter

### 1.9 Module Setup
- [x] Create `erplite/scheduler/__init__.py`
- [x] Update `erplite/hooks.py` to include scheduler routes
- [x] Add scheduler to `erplite/modules.txt`

## Phase 2: Frontend Structure (UPDATED)

### 2.1 Directory Structure
- [x] Create `erplite/www/scheduler/` directory
- [x] Create `erplite/public/js/scheduler/` directory
- [x] Create `erplite/public/js/scheduler/components/` directory
- [x] Create `erplite/public/js/scheduler/managers/` directory

### 2.2 Main Application Files
- [x] Create `erplite/www/scheduler/index.html` (main template)
- [x] Create `erplite/www/scheduler/index.css` (styles)
- [x] Create `erplite/www/scheduler/index.js` (initialization)
- [x] Create `erplite/www/scheduler/index.py` (web page controller)
- [x] Create `erplite/public/js/scheduler/Scheduler.js` (main controller)

### 2.3 Update Column Structure (NEW) ✅ COMPLETED
- [x] Update scheduler grid layout:
  - [x] OLD: Project | Task | Resource | Days...
  - [x] NEW: Project | Activity | Role | Resource | Days...
- [x] Update HTML templates for new column structure
- [ ] Update CSS for new column widths and styling
- [ ] Align all columns

## Phase 3: Core Components (UPDATED)

### 3.1 Project/Activity Selector Component (UPDATED - Task→Activity)
- [ ] Create `ProjectActivitySelector.js` (renamed from ProjectTaskSelector.js)
- [ ] Implement project dropdown with division filtering
- [ ] Implement activity filtering by project (renamed from task)
- [ ] Add project color coding
- [ ] Add expand/collapse functionality
- [ ] Add division grouping support

### 3.2 Role Selector Component (NEW)
- [ ] Create `RoleSelector.js`
- [ ] Implement role dropdown
- [ ] Add role color coding
- [ ] Implement role filtering
- [ ] Add "Any Role" option

### 3.3 Resource Selector Component (UPDATED)
- [ ] Create `ResourceSelector.js`
- [ ] Implement resource dropdown
- [ ] Add "Unassigned" option
- [ ] Implement resource filtering by role
- [ ] Add resource type indicators
- [ ] Show multiple roles per resource

### 3.4 Schedule Grid Component (UPDATED)
- [ ] Create `ScheduleGrid.js`
- [ ] Implement 30-day horizontal scrolling grid
- [ ] Create day column headers
- [ ] Update for new column structure: Project | Activity | Role | Resource | Days
- [ ] Implement project/activity row grouping (renamed from task)
- [ ] Add empty cell click handlers
- [ ] Implement responsive design

### 3.5 Schedule Entry Component
- [ ] Create `ScheduleEntry.js`
- [ ] Implement entry rendering
- [ ] Add drag handles
- [ ] Implement entry selection
- [ ] Add context menu support
- [ ] Implement entry editing modal

### 3.6 Template Cards Component (UPDATED)
- [ ] Update template system to load from Schedule Template doctype
- [ ] Dynamic template cards based on database configuration
- [ ] Configurable colors and properties
- [ ] Sort templates by sort_order field

## Phase 4: Managers (UPDATED)

### 4.1 Schedule Manager (UPDATED - Task→Activity)
- [ ] Create `ScheduleManager.js`
- [ ] Update CRUD operations for schedule entries (include role)
- [ ] Handle drag and drop logic
- [ ] Manage entry grouping and sorting
- [ ] Implement date range navigation
- [ ] Update all task references to activity

### 4.2 Resource Manager (UPDATED)
- [ ] Create `ResourceManager.js`
- [ ] Handle resource assignment/unassignment
- [ ] Implement resource capacity tracking
- [ ] Manage resource filtering by role
- [ ] Handle multiple roles per resource

### 4.3 Storage Manager
- [ ] Create `StorageManager.js`
- [ ] Implement API communication
- [ ] Handle data caching
- [ ] Manage optimistic updates
- [ ] Implement error handling

### 4.4 Division Manager (NEW)
- [ ] Create `DivisionManager.js`
- [ ] Handle division-based project filtering
- [ ] Manage division color coding
- [ ] Implement division-based grouping

## Phase 5: UI Features (UPDATED)

### 5.1 Drag & Drop Functionality
- [ ] Implement entry dragging between dates
- [ ] Implement entry dragging between resources
- [ ] Implement entry dragging between roles
- [ ] Add visual drag feedback
- [ ] Handle drop validation
- [ ] Implement drag cancellation

### 5.2 Entry Management (UPDATED - Task→Activity)
- [ ] Create entry creation modal (update for activity/role)
- [ ] Create entry editing modal (update for activity/role)
- [ ] Implement entry deletion
- [ ] Add entry duplication
- [ ] Implement bulk operations
- [ ] Update all task references to activity

### 5.3 Visual Enhancements (UPDATED)
- [ ] Implement project color coding
- [ ] Add division color coding
- [ ] Add role color coding
- [ ] Add status indicators
- [ ] Implement priority visual cues
- [ ] Add hover effects
- [ ] Implement selection highlighting

## Phase 6: Advanced Features (UPDATED)

### 6.1 Grouping & Filtering (UPDATED)
- [ ] Implement project grouping with expand/collapse
- [ ] Add division-based filtering
- [ ] Add role-based filtering
- [ ] Add resource filtering
- [ ] Implement date range filtering
- [ ] Add status filtering
- [ ] Implement search functionality

### 6.2 Navigation & Scrolling
- [ ] Implement horizontal date scrolling
- [ ] Add date navigation controls
- [ ] Implement "today" indicator
- [ ] Add keyboard navigation
- [ ] Implement smooth scrolling

### 6.3 Unassigned Entries
- [ ] Create unassigned entries section
- [ ] Implement assignment from unassigned pool
- [ ] Add visual indicators for unassigned entries
- [ ] Implement bulk assignment

## Phase 7: Integration & Polish (UPDATED)

### 7.1 Data Integration (UPDATED - Task→Activity)
- [ ] Integrate with existing Project doctype (add division field)
- [ ] Integrate with existing Activity doctype (renamed from Task)
- [ ] Handle project/activity permissions (renamed from task)
- [ ] Implement data validation
- [ ] Handle division and role relationships

### 7.2 User Experience
- [ ] Add loading states
- [ ] Implement error messages
- [ ] Add success notifications
- [ ] Implement keyboard shortcuts
- [ ] Add tooltips and help text

### 7.3 Performance Optimization
- [ ] Implement virtual scrolling for large datasets
- [ ] Add data pagination
- [ ] Optimize rendering performance
- [ ] Implement caching strategies

## Phase 8: Testing & Documentation (UPDATED)

### 8.1 Testing (UPDATED - Task→Activity)
- [ ] Test CRUD operations with new doctypes
- [ ] Test drag and drop functionality with roles
- [ ] Test responsive design with new column structure
- [ ] Test data validation for activities/roles
- [ ] Test error handling
- [ ] Test template system with configurable templates

### 8.2 Documentation (UPDATED)
- [ ] Update user documentation for new terminology
- [ ] Document new API endpoints
- [ ] Update setup instructions
- [ ] Document new configuration options
- [ ] Document division/role/template management


---

## Current Status: Phase 1 Backend Complete - Ready for Frontend Implementation

**Completed**: ✅ All new doctypes created, Task→Activity migration complete, dummy data created
**Next Step**: Start with Phase 2.3 - Update frontend column structure for new scheduler layout

## Key Changes Summary
- **✅ COMPLETED**: Division, Scheduler Role, Schedule Template doctypes created
- **✅ COMPLETED**: Task → Activity throughout system (Task doctype removed)
- **✅ COMPLETED**: Activity doctype created with enhanced functionality
- **✅ COMPLETED**: All scheduler doctypes updated for new column structure
- **✅ COMPLETED**: Timesheet integration updated for Activity
- **✅ COMPLETED**: Workspace navigation updated
- **NEW COLUMN**: Role column between Activity and Resource
- **UPDATED**: Template system now configurable via database
- **UPDATED**: Resources have default roles
- **READY**: Projects can have divisions and work types (pending implementation)

## Backend Status: ✅ COMPLETE
- All new doctypes created and working
- Task→Activity migration successful
- Validation errors fixed
- Dummy data created and tested
- Database schema ready for frontend integration

## Notes
- This is a development environment, so we can make breaking changes
- Focus on new doctypes first, then update existing ones
- UI should reflect new Project | Activity | Role | Resource | Days structure
- Template cards should load from Schedule Template doctype
- All "task" terminology updated to "activity"
