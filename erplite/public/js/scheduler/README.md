# Scheduler JavaScript Documentation

## Overview
This directory contains the JavaScript files and documentation for the ERPLite Scheduler system. The scheduler is a comprehensive project and resource scheduling application built with a modular architecture for maintainability and extensibility.

## Architecture
The scheduler follows a component-based architecture with clear separation of concerns:

- **Main Controller** - Orchestrates all components and manages application state
- **Data Layer** - Handles API communication and data processing
- **UI Components** - Manages user interface elements and interactions
- **Rendering Engine** - Creates and updates visual elements
- **Utility Libraries** - Provides common functionality across components

## File Structure and Documentation

### Core Components

#### [Scheduler.js](./Scheduler.md)
**Main Application Controller**
- Central orchestrator for the entire scheduler system
- Manages application state and component coordination
- Handles user interactions and event routing
- Provides global functions for HTML template integration

**Key Features:**
- State management for projects, resources, and schedule data
- Component manager initialization and coordination
- Date navigation and range management
- Time entry creation and management
- Drag and drop functionality
- Modal management for entry creation/editing

---

#### [data/DataManager.js](./data/DataManager.md)
**Data Layer and API Integration**
- Handles all API calls to the Frappe backend
- Processes and transforms data for frontend consumption
- Manages both legacy schedule entries and new schedule rows
- Provides data validation and error handling

**Key Features:**
- Parallel API requests for optimal performance
- Data processing and transformation
- CRUD operations for schedule entries
- Navigation and refresh functionality
- Data validation and access methods

---

### User Interface Components

#### [DropdownManager.js](./DropdownManager.md)
**Dropdown Interface Management**
- Professional dropdown components with search and filtering
- Handles project, activity, role, and resource selection
- Provides keyboard navigation and accessibility features
- Manages dropdown positioning and outside click detection

**Key Features:**
- Search functionality with real-time filtering
- Resource type filtering (People, Equipment, etc.)
- Keyboard navigation support
- Avatar and icon integration
- Mobile/touch device support

---

#### [toolbar/ToolbarManager.js](./toolbar/ToolbarManager.md)
**Toolbar Interface and Actions**
- Manages navigation buttons and date range controls
- Handles template cards with drag and drop functionality
- Provides action buttons (refresh, export, add row)
- Implements keyboard shortcuts for power users

**Key Features:**
- Template system with drag and drop
- Date range navigation
- Loading states and visual feedback
- Keyboard shortcuts (Ctrl+Arrow, Ctrl+R, etc.)
- Mobile-friendly interactions

---

### Rendering and Visual Components

#### [rendering/RowRenderer.js](./rendering/RowRenderer.md)
**Schedule Grid Rendering**
- Creates and renders schedule rows, cells, and entries
- Handles both project headers and activity rows
- Manages visual states and interactive elements
- Provides drag and drop support for entries

**Key Features:**
- Fixed and scrollable column rendering
- Project header summaries with resource counts
- Activity row interactions and controls
- Day cell creation with weekend/today highlighting
- Entry element creation and styling

---

#### [timeblocks/TimeBlockManager.js](./timeblocks/TimeBlockManager.md)
**Time Block Cards and Interactions**
- Renders visual time blocks that span multiple days
- Provides drag and resize functionality
- Groups consecutive entries into blocks
- Manages time block editing and updates

**Key Features:**
- Visual time block cards with project colors
- Resize handles with mouse interaction
- Entry grouping and block optimization
- Real-time visual feedback during resize
- API integration for persistence

---

### Business Logic Components

#### [ScheduleRowManager.js](./ScheduleRowManager.md)
**Schedule Row Operations**
- Manages schedule row creation and updates
- Handles project/activity/resource selection
- Provides time entry management
- Integrates with backend APIs for persistence

**Key Features:**
- Schedule row lifecycle management
- Selection workflow (project → activity → role → resource)
- Time entry CRUD operations
- Template handling and application
- Row management (copy, delete, duplicate)

---

### Utility Libraries

#### [utils/SchedulerUtils.js](./utils/SchedulerUtils.md)
**General Utility Functions**
- Date manipulation and validation
- Color conversion and formatting
- Entry grouping and processing
- Function optimization (debounce, throttle)
- Template configurations

**Key Features:**
- Comprehensive date utilities
- Color and visual helpers
- Entry grouping algorithms
- Performance optimization functions
- Input validation and sanitization

---

#### [utils/ResourceUtils.js](./utils/ResourceUtils.md)
**Resource Management Utilities**
- Resource avatar creation and styling
- Resource type management and icons
- Resource grouping and analysis
- Consistent visual representation

**Key Features:**
- Avatar generation with initials and colors
- Resource type icons and indicators
- Resource validation and display names
- Type-based grouping and summaries
- Consistent color palette

---

## Component Relationships

```
SchedulerApp (Main Controller)
├── DataManager (Data Layer)
├── ToolbarManager (Toolbar UI)
├── DropdownManager (Dropdown UI)
├── ScheduleRowManager (Business Logic)
├── RowRenderer (Visual Rendering)
├── TimeBlockManager (Time Blocks)
├── SchedulerUtils (General Utilities)
└── ResourceUtils (Resource Utilities)
```

## Key Concepts

### Schedule Rows
The core data structure representing project/activity/resource assignments:
- **Project Headers**: Summary rows showing project totals and resource counts
- **Activity Rows**: Individual assignments with time entries

### Time Entries
Individual time allocations with properties:
- Hours, start time, end time
- Status (planned, confirmed, completed)
- Description and metadata

### Time Blocks
Visual representations of time entries:
- Single-day blocks for individual entries
- Multi-day blocks for consecutive identical entries
- Resizable and interactive

### Templates
Pre-configured time entry templates:
- **8h**: Standard 8-hour shift (09:00-17:00)
- **12h**: Extended 12-hour shift (07:00-19:00)
- **Leave**: Time off template (00:00-23:59)

## Development Guidelines

### Adding New Features
1. Identify the appropriate component for the feature
2. Follow the existing patterns and architecture
3. Update relevant documentation
4. Ensure proper error handling and validation
5. Add appropriate CSS classes and styling

### API Integration
- Use DataManager for all API calls
- Follow the existing error handling patterns
- Provide user feedback through toast notifications
- Handle loading states appropriately

### UI Components
- Follow the established visual design patterns
- Use Material Design Icons for consistency
- Implement proper accessibility features
- Support both mouse and keyboard interactions

### Performance Considerations
- Use utility functions for common operations
- Implement proper cleanup in component destructors
- Minimize DOM manipulations
- Use event delegation where appropriate

## Browser Support
- Modern browsers with ES6+ support
- Drag and drop API support
- CSS Grid and Flexbox support
- Material Design Icons compatibility

## Dependencies
- **Frappe Framework**: Backend API integration
- **Material Design Icons**: Icon library
- **Native Browser APIs**: Drag/drop, DOM manipulation
- **No external JavaScript libraries**: Pure vanilla JavaScript implementation

## Getting Started
1. Review the main [Scheduler.js documentation](./Scheduler.md) for overall architecture
2. Examine [DataManager.js documentation](./data/DataManager.md) for API integration
3. Study component-specific documentation for detailed implementation
4. Follow the usage examples in each documentation file

## Contributing
When contributing to the scheduler system:
1. Maintain the existing architectural patterns
2. Update documentation for any changes
3. Follow the established coding conventions
4. Ensure backward compatibility where possible
5. Test thoroughly across different browsers and devices

---

*This documentation covers the complete scheduler system as of the current implementation. For specific implementation details, refer to the individual component documentation files.*
