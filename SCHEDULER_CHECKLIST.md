# Scheduler Project Implementation Checklist

## Phase 1: Backend Setup & Doctypes

### 1.1 Create Resource Doctype
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
  - [x] description (Text Editor)

### 1.2 Create Schedule Entry Doctype
- [x] Create `erplite/scheduler/doctype/schedule_entry/` directory
- [x] Create `schedule_entry.json` (doctype definition)
- [x] Create `schedule_entry.py` (controller)
- [x] Create `schedule_entry.js` (client script)
- [x] Add fields:
  - [x] project (Link to Project, Required)
  - [x] task (Link to Task, Required)
  - [x] resource (Link to Resource)
  - [x] schedule_date (Date, Required)
  - [x] duration (Float, default 1.0)
  - [x] status (Select: Planned/In Progress/Completed/Cancelled)
  - [x] description (Text Editor)
  - [x] priority (Select: Low/Medium/High)

### 1.3 Backend API
- [x] Create `erplite/scheduler/api.py`
- [x] Implement `get_scheduler_data()` function
- [x] Implement `create_schedule_entry()` function
- [x] Implement `update_schedule_entry()` function
- [x] Implement `delete_schedule_entry()` function
- [x] Implement `get_resources()` function
- [x] Implement `get_projects_and_tasks()` function

### 1.4 Module Setup
- [x] Create `erplite/scheduler/__init__.py`
- [x] Update `erplite/hooks.py` to include scheduler routes
- [x] Add scheduler to `erplite/modules.txt`

## Phase 2: Frontend Structure

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

## Phase 3: Core Components

### 3.1 Project/Task Selector Component
- [ ] Create `ProjectTaskSelector.js`
- [ ] Implement project dropdown
- [ ] Implement task filtering by project
- [ ] Add project color coding
- [ ] Add expand/collapse functionality

### 3.2 Resource Selector Component
- [ ] Create `ResourceSelector.js`
- [ ] Implement resource dropdown
- [ ] Add "Unassigned" option
- [ ] Implement resource filtering/search
- [ ] Add resource type indicators

### 3.3 Schedule Grid Component
- [ ] Create `ScheduleGrid.js`
- [ ] Implement 30-day horizontal scrolling grid
- [ ] Create day column headers
- [ ] Implement project/task row grouping
- [ ] Add empty cell click handlers
- [ ] Implement responsive design

### 3.4 Schedule Entry Component
- [ ] Create `ScheduleEntry.js`
- [ ] Implement entry rendering
- [ ] Add drag handles
- [ ] Implement entry selection
- [ ] Add context menu support
- [ ] Implement entry editing modal

## Phase 4: Managers

### 4.1 Schedule Manager
- [ ] Create `ScheduleManager.js`
- [ ] Implement CRUD operations for schedule entries
- [ ] Handle drag and drop logic
- [ ] Manage entry grouping and sorting
- [ ] Implement date range navigation

### 4.2 Resource Manager
- [ ] Create `ResourceManager.js`
- [ ] Handle resource assignment/unassignment
- [ ] Implement resource capacity tracking
- [ ] Manage resource filtering

### 4.3 Storage Manager
- [ ] Create `StorageManager.js`
- [ ] Implement API communication
- [ ] Handle data caching
- [ ] Manage optimistic updates
- [ ] Implement error handling

## Phase 5: UI Features

### 5.1 Drag & Drop Functionality
- [ ] Implement entry dragging between dates
- [ ] Implement entry dragging between resources
- [ ] Add visual drag feedback
- [ ] Handle drop validation
- [ ] Implement drag cancellation

### 5.2 Entry Management
- [ ] Create entry creation modal
- [ ] Create entry editing modal
- [ ] Implement entry deletion
- [ ] Add entry duplication
- [ ] Implement bulk operations

### 5.3 Visual Enhancements
- [ ] Implement project color coding
- [ ] Add status indicators
- [ ] Implement priority visual cues
- [ ] Add hover effects
- [ ] Implement selection highlighting

## Phase 6: Advanced Features

### 6.1 Grouping & Filtering
- [ ] Implement project grouping with expand/collapse
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

## Phase 7: Integration & Polish

### 7.1 Data Integration
- [ ] Integrate with existing Project doctype
- [ ] Integrate with existing Task doctype
- [ ] Handle project/task permissions
- [ ] Implement data validation

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

## Phase 8: Testing & Documentation

### 8.1 Testing
- [ ] Test CRUD operations
- [ ] Test drag and drop functionality
- [ ] Test responsive design
- [ ] Test data validation
- [ ] Test error handling

### 8.2 Documentation
- [ ] Create user documentation
- [ ] Document API endpoints
- [ ] Create setup instructions
- [ ] Document configuration options

## Phase 9: Deployment

### 9.1 Final Setup
- [ ] Update module hooks
- [ ] Create sample data
- [ ] Test installation process
- [ ] Verify all dependencies

### 9.2 Launch Preparation
- [ ] Final testing
- [ ] Performance verification
- [ ] Security review
- [ ] Documentation review

---

## Current Status: Ready to Begin
**Next Step**: Start with Phase 1.1 - Create Resource Doctype

## Notes
- This is a prototype, so permissions are not implemented
- Focus on core functionality first
- UI should be intuitive and responsive
- Leverage existing timesheet-calendar patterns where possible
