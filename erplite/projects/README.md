# ERPLite Projects Module

A simple project task and timesheet management system for ERPLite.

## Features

### Project Management
- Create and manage projects with basic information
- Assign project managers
- Track project status (Active, On Hold, Completed, Cancelled)
- Link projects to customers

### Task Management
- Create tasks linked to projects
- Assign tasks to users
- Track task progress and status
- Set priorities and due dates
- Define task locations/areas

### Timesheet System
- Simple check-in/check-out workflow
- Select project and task for time tracking
- Manual time entry for corrections
- Duration auto-calculation
- Simple approval workflow (no complex Frappe workflows)

## Core DocTypes

1. **Project** - Main project container
2. **Task** - Individual work items within projects
3. **Timesheet Entry** - Time tracking records

## User Workflow

### For Employees:
1. **Check-In**: Select project → task → check in
2. **Work**: Perform the task
3. **Check-Out**: Add work description and check out
4. **Manual Entry**: Create/edit timesheet entries if needed

### For Project Managers:
1. **Review**: View submitted timesheets for their projects
2. **Approve/Reject**: Simple button click with optional notes
3. **Track**: Monitor project progress and time spent

## Key Features

### Simple Check-In/Out
- Quick check-in dialog from anywhere in the system
- Prevents multiple active timesheets per user
- Auto-calculates duration on check-out
- Auto-submits completed timesheets

### Smart Filtering
- Tasks filtered by selected project
- Location auto-filled from task
- User-specific timesheet views

### Approval System
- Project managers can approve timesheets for their projects
- Simple approve/reject buttons (no workflow complexity)
- Approval notes and timestamps
- Read-only fields after approval

### User Experience
- Dashboard widgets for quick access
- List view customizations with status indicators
- Quick action buttons in forms
- Mobile-friendly interface

## Installation

The system is automatically available once the ERPLite app is installed. The DocTypes will be created when you run:

```bash
bench migrate
```

**Important**: If you encounter workspace errors, clear the cache:

```bash
bench clear-cache
bench restart
```

Or access the modules directly via:
- `/app/project` - Projects
- `/app/task` - Tasks  
- `/app/timesheet-entry` - Timesheet Entries
- `/timesheet-dashboard` - Dashboard

## Usage

1. **Create Projects**: Go to Project list and create your first project
2. **Add Tasks**: Create tasks within projects, specify locations if needed
3. **Start Tracking**: Use Quick Check-In from timesheet list or dashboard
4. **Manage Time**: Check in/out as you work on different tasks
5. **Approve Time**: Project managers approve submitted timesheets

## Permissions

- **System Manager**: Full access to all features
- **Projects Manager**: Can manage projects and approve timesheets
- **Projects User**: Can create timesheets and view own data

## Dashboard

Access the timesheet dashboard at: `/timesheet-dashboard`

Features:
- Quick check-in button
- Active timesheet display
- Recent timesheet history
- Pending approvals (for project managers)

## API Methods

### Check-In
```javascript
frappe.call({
    method: 'erplite.projects.doctype.timesheet_entry.timesheet_entry.check_in',
    args: {
        project: 'PROJECT-2025-001',
        task: 'TASK-2025-001',
        location: 'Office'
    }
});
```

### Check-Out
```javascript
frappe.call({
    method: 'erplite.projects.doctype.timesheet_entry.timesheet_entry.check_out',
    args: {
        timesheet_id: 'TS-2025-001',
        description: 'Completed the task'
    }
});
```

### Approve Timesheet
```javascript
frappe.call({
    method: 'erplite.projects.doctype.timesheet_entry.timesheet_entry.approve_timesheet',
    args: {
        timesheet_id: 'TS-2025-001',
        approval_notes: 'Good work'
    }
});
```

## Customization

The system is designed to be simple and extensible. You can:

- Add custom fields to any DocType
- Create additional reports
- Extend the dashboard
- Add more automation rules
- Integrate with billing systems

## Support

This is a simple, focused implementation designed for ease of use. The system avoids complex workflows in favor of straightforward functionality that gets the job done.
