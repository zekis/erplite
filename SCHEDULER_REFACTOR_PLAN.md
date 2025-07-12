# Scheduler Refactor Plan

## Current Issues
- **Monolithic File**: Single 1000+ line file handling everything
- **Mixed Responsibilities**: Data management, UI rendering, event handling all in one class
- **Legacy Code**: Old backend integration mixed with new frontend-only code
- **Poor Maintainability**: Hard to debug, test, and extend
- **Code Duplication**: Similar patterns repeated throughout

## Refactor Goals
1. **Modular Architecture**: Split into focused, single-responsibility modules
2. **Clean Separation**: Separate data, UI, and interaction concerns
3. **Remove Legacy**: Clean out old backend integration code
4. **Modern Patterns**: Use consistent patterns throughout
5. **Maintainable**: Easy to understand, debug, and extend

## New Architecture

```
erplite/public/js/scheduler/
├── Scheduler.js                 # Main controller (150-200 lines)
├── core/
│   ├── StateManager.js         # Application state management
│   ├── DataProcessor.js        # Data transformation and grouping
│   └── EventBus.js             # Event communication between modules
├── components/
│   ├── GridRenderer.js         # Schedule grid rendering
│   ├── TimeBlockRenderer.js    # Time block card rendering
│   ├── DropdownManager.js      # Project/task/resource dropdowns
│   └── ModalManager.js         # Modal dialogs
├── interactions/
│   ├── DragDropManager.js      # Template and entry drag & drop
│   ├── ResizeManager.js        # Time block resizing
│   └── SelectionManager.js     # Multi-day selection
├── templates/
│   └── TemplateManager.js      # Template configurations and handling
└── utils/
    ├── DateUtils.js            # Date manipulation utilities
    ├── ColorUtils.js           # Color conversion utilities
    └── DOMUtils.js             # DOM manipulation helpers
```

## Refactor Checklist

### Phase 1: Core Infrastructure
- [ ] Create `StateManager.js` - Centralized state management
- [ ] Create `EventBus.js` - Event communication system
- [ ] Create `DateUtils.js` - Date manipulation utilities
- [ ] Create `ColorUtils.js` - Color conversion utilities
- [ ] Create `DOMUtils.js` - DOM manipulation helpers

### Phase 2: Data Layer
- [ ] Create `DataProcessor.js` - Data transformation and grouping
- [ ] Move data processing methods from main class
- [ ] Remove legacy backend integration code
- [ ] Implement frontend-only data structures

### Phase 3: UI Components
- [ ] Create `GridRenderer.js` - Schedule grid rendering
  - [ ] Move `renderScheduleRows()` method
  - [ ] Move `createScheduleRow()` method
  - [ ] Move `createDayCell()` method
  - [ ] Move `renderDateColumns()` method
- [ ] Create `TimeBlockRenderer.js` - Time block card rendering
  - [ ] Move `renderTimeBlockCards()` method
  - [ ] Move `renderTimeBlockCard()` method
  - [ ] Move `groupConsecutiveEntries()` method
- [ ] Create `DropdownManager.js` - Dropdown handling
  - [ ] Move `showProjectDropdown()` method
  - [ ] Move `showTaskDropdown()` method
  - [ ] Move `showPersonDropdown()` method
  - [ ] Move dropdown event handlers

### Phase 4: Interaction Managers
- [ ] Create `DragDropManager.js` - Drag & drop functionality
  - [ ] Move `initializeTemplateDragDrop()` method
  - [ ] Move `handleTemplateDrop()` method
  - [ ] Move `handleCellDrop()` method
  - [ ] Move template configuration methods
- [ ] Create `ResizeManager.js` - Time block resizing
  - [ ] Move `startResize()` method
  - [ ] Move `handleResize()` method
  - [ ] Move `endResize()` method
  - [ ] Move resize utility methods
- [ ] Create `SelectionManager.js` - Multi-day selection
  - [ ] Move `startDragSelection()` method
  - [ ] Move `handleDragSelection()` method
  - [ ] Move `endDragSelection()` method

### Phase 5: Template System
- [ ] Create `TemplateManager.js` - Template handling
  - [ ] Move `getTemplateConfig()` method
  - [ ] Move template-related constants
  - [ ] Implement template validation

### Phase 6: Main Controller Cleanup
- [ ] Refactor main `Scheduler.js` to orchestrate modules
- [ ] Remove duplicate code
- [ ] Clean up method signatures
- [ ] Implement proper error handling
- [ ] Add comprehensive logging

### Phase 7: Testing & Validation
- [ ] Test template drag & drop functionality
- [ ] Test time block rendering
- [ ] Test resize functionality
- [ ] Test dropdown interactions
- [ ] Test multi-day selection
- [ ] Verify no regressions

### Phase 8: Documentation
- [ ] Update code comments
- [ ] Create module documentation
- [ ] Update architecture diagrams
- [ ] Create developer guide

## Implementation Strategy

### 1. Incremental Refactor
- Extract one module at a time
- Test after each extraction
- Maintain working functionality throughout

### 2. Event-Driven Architecture
- Use EventBus for module communication
- Decouple modules from direct dependencies
- Enable easier testing and debugging

### 3. State Management
- Centralize all application state
- Implement state change notifications
- Enable state debugging and inspection

### 4. Modern JavaScript Patterns
- Use ES6+ features consistently
- Implement proper error handling
- Use async/await for consistency

## Benefits After Refactor

### Developer Experience
- **Easier Debugging**: Isolated modules with clear responsibilities
- **Faster Development**: Focused files, easier to navigate
- **Better Testing**: Modules can be tested independently
- **Cleaner Code**: Consistent patterns and structure

### Maintainability
- **Single Responsibility**: Each module has one clear purpose
- **Loose Coupling**: Modules communicate through events
- **High Cohesion**: Related functionality grouped together
- **Extensibility**: Easy to add new features

### Performance
- **Lazy Loading**: Modules can be loaded as needed
- **Better Caching**: Smaller files cache more efficiently
- **Optimized Bundling**: Build tools can optimize better

## File Size Targets

| File | Current | Target | Purpose |
|------|---------|--------|---------|
| Scheduler.js | 1000+ lines | 150-200 lines | Main controller |
| StateManager.js | - | 100-150 lines | State management |
| GridRenderer.js | - | 200-250 lines | Grid rendering |
| TimeBlockRenderer.js | - | 150-200 lines | Time block cards |
| DragDropManager.js | - | 150-200 lines | Drag & drop |
| ResizeManager.js | - | 100-150 lines | Resize functionality |

## Migration Path

1. **Create infrastructure** (StateManager, EventBus, Utils)
2. **Extract data layer** (DataProcessor)
3. **Extract UI components** (GridRenderer, TimeBlockRenderer)
4. **Extract interactions** (DragDropManager, ResizeManager)
5. **Clean up main controller**
6. **Test and validate**

This refactor will transform the scheduler from a monolithic application into a modern, modular, maintainable codebase that's easy to understand, debug, and extend.
