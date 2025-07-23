# ERPLite Scheduler Project Brief

## Project Overview
ERPLite is a Frappe-based ERP system with a custom scheduler module for resource planning and project management. The scheduler allows users to assign resources to project activities across a timeline view.

## Core Requirements

### Backend Architecture (COMPLETED)
- **Frappe Framework**: Built on ERPNext framework with custom doctypes
- **New Doctypes**: Division, Scheduler Role, Schedule Template, updated Resource/Schedule Entry/Schedule Row
- **Activity Migration**: Complete Task→Activity rename throughout system
- **Database Structure**: Project | Activity | Role | Resource | Days column layout

### Frontend Requirements (IN PROGRESS)
- **Column Structure**: Update from old Project|Task|Resource to new Project|Activity|Role|Resource
- **Template System**: Configurable templates from Schedule Template doctype
- **Drag & Drop**: Template cards and entry management
- **Time Blocks**: Visual time block cards spanning multiple days
- **Resource Management**: Role-based resource filtering

## Key Technical Decisions
1. **Naming Convention**: Task→Activity throughout to avoid conflicts
2. **Role Doctype**: Named "Scheduler Role" to avoid system conflicts
3. **Template System**: Database-driven instead of hardcoded
4. **Frontend Architecture**: Component-based with managers for different concerns

## Current Status
- **Phase 1**: Backend complete, all doctypes created and tested
- **Phase 2.3**: Updating frontend column structure (CURRENT TASK)
- **Next**: Component updates for new structure

## Success Criteria
- Seamless transition from 3-column to 4-column layout
- All existing functionality preserved
- New role-based filtering capabilities
- Configurable template system working
