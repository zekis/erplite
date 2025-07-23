# Event Handling Patterns Reference

## Overview
This document consolidates common event handling patterns used throughout the scheduler system. It serves as a reference for consistent event management across all components.

## Common Event Types

### Mouse Events

#### Click Events
**Pattern:** Standard click handling with event delegation
```javascript
element.addEventListener('click', (event) => {
    // Prevent event bubbling if needed
    event.stopPropagation();
    
    // Handle the click
    this.handleClick(event);
});
```

**Used in:**
- DropdownManager: Dropdown item selection
- ToolbarManager: Button clicks, template clicks
- TimeBlockManager: Time block editing
- RowRenderer: Cell interactions, row controls

#### Mouse Down/Up/Move Events
**Pattern:** Complex interaction handling (drag, resize)
```javascript
// Start interaction
element.addEventListener('mousedown', (event) => {
    event.preventDefault();
    event.stopPropagation();
    
    // Store initial state
    this.interactionState = {
        active: true,
        startX: event.clientX,
        startY: event.clientY
    };
    
    // Bind movement and end handlers
    this.boundHandleMove = this.handleMove.bind(this);
    this.boundEndInteraction = this.endInteraction.bind(this);
    
    document.addEventListener('mousemove', this.boundHandleMove);
    document.addEventListener('mouseup', this.boundEndInteraction);
    
    // Prevent text selection
    document.body.style.userSelect = 'none';
});

// Handle movement
handleMove(event) {
    if (!this.interactionState?.active) return;
    
    // Calculate movement
    const deltaX = event.clientX - this.interactionState.startX;
    const deltaY = event.clientY - this.interactionState.startY;
    
    // Update visual state
    this.updateVisualState(deltaX, deltaY);
}

// End interaction
endInteraction(event) {
    if (!this.interactionState?.active) return;
    
    // Clean up event listeners
    document.removeEventListener('mousemove', this.boundHandleMove);
    document.removeEventListener('mouseup', this.boundEndInteraction);
    
    // Restore text selection
    document.body.style.userSelect = '';
    
    // Apply changes
    this.applyChanges();
    
    // Reset state
    this.interactionState = null;
}
```

**Used in:**
- TimeBlockManager: Resize operations
- Scheduler: Drag selection for multiple days

#### Mouse Enter/Leave Events
**Pattern:** Hover effects and visual feedback
```javascript
element.addEventListener('mouseenter', () => {
    element.classList.add('hover-state');
});

element.addEventListener('mouseleave', () => {
    element.classList.remove('hover-state');
});
```

**Used in:**
- RowRenderer: Day cell hover effects
- DropdownManager: Item hover states
- ToolbarManager: Button hover feedback

### Keyboard Events

#### Key Down Events
**Pattern:** Keyboard navigation and shortcuts
```javascript
element.addEventListener('keydown', (event) => {
    // Handle specific keys
    switch (event.key) {
        case 'Enter':
        case ' ':
            event.preventDefault();
            this.activate();
            break;
        case 'ArrowDown':
            event.preventDefault();
            this.navigateDown();
            break;
        case 'ArrowUp':
            event.preventDefault();
            this.navigateUp();
            break;
        case 'Escape':
            event.preventDefault();
            this.cancel();
            break;
    }
});
```

**Used in:**
- DropdownManager: Dropdown navigation
- ToolbarManager: Button keyboard support, global shortcuts

#### Global Keyboard Shortcuts
**Pattern:** Application-wide keyboard shortcuts
```javascript
document.addEventListener('keydown', (event) => {
    // Ignore shortcuts when in input fields
    if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
        return;
    }
    
    // Handle modifier key combinations
    if (event.ctrlKey || event.metaKey) {
        switch (event.key) {
            case 'r':
                event.preventDefault();
                this.refresh();
                break;
            case 'ArrowLeft':
                event.preventDefault();
                this.navigateLeft();
                break;
            case 'ArrowRight':
                event.preventDefault();
                this.navigateRight();
                break;
        }
    }
});
```

**Used in:**
- ToolbarManager: Global application shortcuts

### Drag and Drop Events

#### Drag Start/End Pattern
**Pattern:** Initiating and completing drag operations
```javascript
// Make element draggable
element.draggable = true;

// Handle drag start
element.addEventListener('dragstart', (event) => {
    // Set drag data
    event.dataTransfer.setData('text/plain', JSON.stringify({
        type: 'item-type',
        id: this.id,
        data: this.data
    }));
    
    // Add visual feedback
    element.classList.add('dragging');
    
    // Optional: Custom drag image
    const dragImage = this.createDragImage();
    event.dataTransfer.setDragImage(dragImage, 20, 20);
});

// Handle drag end
element.addEventListener('dragend', (event) => {
    // Remove visual feedback
    element.classList.remove('dragging');
    
    // Clean up any temporary elements
    this.cleanup();
});
```

**Used in:**
- ToolbarManager: Template card dragging
- RowRenderer: Schedule entry dragging

#### Drop Zone Pattern
**Pattern:** Accepting dropped items
```javascript
// Handle drag over (required for drop)
dropZone.addEventListener('dragover', (event) => {
    event.preventDefault(); // Allow drop
});

// Handle drag enter
dropZone.addEventListener('dragenter', (event) => {
    event.preventDefault();
    
    // Validate drop target
    if (this.canAcceptDrop(event)) {
        dropZone.classList.add('drop-zone');
    }
});

// Handle drag leave
dropZone.addEventListener('dragleave', (event) => {
    event.preventDefault();
    dropZone.classList.remove('drop-zone');
});

// Handle drop
dropZone.addEventListener('drop', (event) => {
    event.preventDefault();
    event.stopPropagation();
    
    // Remove visual feedback
    dropZone.classList.remove('drop-zone');
    
    try {
        // Parse drop data
        const data = JSON.parse(event.dataTransfer.getData('text/plain'));
        
        // Handle different drop types
        switch (data.type) {
            case 'template':
                this.handleTemplateDrop(data);
                break;
            case 'entry':
                this.handleEntryDrop(data);
                break;
        }
    } catch (error) {
        console.error('Error handling drop:', error);
    }
});
```

**Used in:**
- RowRenderer: Day cell drop zones
- Scheduler: Cell drop handling

## Event Management Patterns

### Event Listener Cleanup
**Pattern:** Proper cleanup to prevent memory leaks
```javascript
class ComponentManager {
    constructor() {
        this.boundHandlers = new Map();
    }
    
    addEventListeners() {
        // Store bound handlers for cleanup
        this.boundHandlers.set('click', this.handleClick.bind(this));
        this.boundHandlers.set('keydown', this.handleKeydown.bind(this));
        
        // Add listeners
        this.element.addEventListener('click', this.boundHandlers.get('click'));
        document.addEventListener('keydown', this.boundHandlers.get('keydown'));
    }
    
    cleanup() {
        // Remove all event listeners
        this.boundHandlers.forEach((handler, event) => {
            if (event === 'keydown') {
                document.removeEventListener(event, handler);
            } else {
                this.element.removeEventListener(event, handler);
            }
        });
        
        // Clear references
        this.boundHandlers.clear();
    }
}
```

**Used in:**
- All manager classes for proper cleanup

### Outside Click Detection
**Pattern:** Detecting clicks outside a component
```javascript
setupOutsideClickHandler() {
    this.boundHandleOutsideClick = this.handleOutsideClick.bind(this);
    
    // Delay attachment to avoid immediate triggering
    setTimeout(() => {
        document.addEventListener('click', this.boundHandleOutsideClick);
    }, 100);
}

handleOutsideClick(event) {
    // Check if click is outside the component
    if (!event.target.closest('.component-selector')) {
        this.close();
        this.removeOutsideClickHandler();
    }
}

removeOutsideClickHandler() {
    if (this.boundHandleOutsideClick) {
        document.removeEventListener('click', this.boundHandleOutsideClick);
        this.boundHandleOutsideClick = null;
    }
}
```

**Used in:**
- DropdownManager: Closing dropdowns on outside click

### Event Delegation
**Pattern:** Handling events on dynamically created elements
```javascript
// Add single listener to parent container
container.addEventListener('click', (event) => {
    // Find the actual target element
    const targetElement = event.target.closest('.target-selector');
    if (!targetElement) return;
    
    // Get data from element
    const itemId = targetElement.dataset.itemId;
    const action = targetElement.dataset.action;
    
    // Handle based on action
    switch (action) {
        case 'edit':
            this.editItem(itemId);
            break;
        case 'delete':
            this.deleteItem(itemId);
            break;
    }
});
```

**Used in:**
- RowRenderer: Row control buttons
- DropdownManager: Dynamic dropdown items

## State Management During Events

### Loading States
**Pattern:** Managing loading states during async operations
```javascript
async handleAsyncAction(event) {
    const button = event.target;
    
    try {
        // Set loading state
        this.setLoadingState(button, true);
        
        // Perform async operation
        const result = await this.performOperation();
        
        // Handle result
        if (result.success) {
            this.showSuccess('Operation completed');
        } else {
            this.showError(result.message);
        }
        
    } catch (error) {
        this.showError('Operation failed: ' + error.message);
    } finally {
        // Always restore state
        this.setLoadingState(button, false);
    }
}

setLoadingState(button, loading) {
    button.disabled = loading;
    button.classList.toggle('loading', loading);
    
    const icon = button.querySelector('i');
    if (icon) {
        if (loading) {
            icon.classList.remove('mdi-refresh');
            icon.classList.add('mdi-loading', 'mdi-spin');
        } else {
            icon.classList.remove('mdi-loading', 'mdi-spin');
            icon.classList.add('mdi-refresh');
        }
    }
}
```

**Used in:**
- ToolbarManager: Button loading states
- DataManager: API call states

### Visual Feedback
**Pattern:** Providing immediate visual feedback
```javascript
handleInteraction(event) {
    const element = event.target;
    
    // Immediate visual feedback
    element.classList.add('clicked');
    
    // Remove feedback after animation
    setTimeout(() => {
        element.classList.remove('clicked');
    }, 200);
    
    // Perform actual action
    this.performAction();
}
```

**Used in:**
- ToolbarManager: Button click feedback
- DropdownManager: Item selection feedback

## Error Handling in Events

### Try-Catch Pattern
**Pattern:** Robust error handling in event handlers
```javascript
handleEvent(event) {
    try {
        // Validate event data
        if (!this.validateEventData(event)) {
            throw new Error('Invalid event data');
        }
        
        // Process event
        this.processEvent(event);
        
    } catch (error) {
        // Log error for debugging
        console.error('Error handling event:', error);
        
        // Show user-friendly message
        this.showToast('An error occurred: ' + error.message, 'error');
        
        // Restore UI state if needed
        this.restoreUIState();
    }
}
```

**Used throughout all components for robust error handling**

## Performance Considerations

### Debouncing
**Pattern:** Limiting rapid event firing
```javascript
// Create debounced handler
this.debouncedHandler = this.debounce((event) => {
    this.handleEvent(event);
}, 300);

// Use debounced handler
element.addEventListener('input', this.debouncedHandler);

// Debounce utility
debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
```

**Used in:**
- DropdownManager: Search input handling

### Throttling
**Pattern:** Limiting event frequency
```javascript
// Create throttled handler
this.throttledHandler = this.throttle((event) => {
    this.handleEvent(event);
}, 100);

// Use throttled handler
element.addEventListener('scroll', this.throttledHandler);

// Throttle utility
throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}
```

**Used in:**
- TimeBlockManager: Resize movement handling

## Best Practices

### 1. Always Clean Up
- Remove event listeners in cleanup methods
- Clear timeouts and intervals
- Reset state variables

### 2. Prevent Default When Needed
- Use `event.preventDefault()` for custom behavior
- Use `event.stopPropagation()` to prevent bubbling

### 3. Validate Event Data
- Check for required properties
- Validate data types and ranges
- Handle edge cases gracefully

### 4. Provide Visual Feedback
- Show loading states for async operations
- Provide hover effects for interactive elements
- Give immediate feedback for user actions

### 5. Handle Errors Gracefully
- Use try-catch blocks in event handlers
- Log errors for debugging
- Show user-friendly error messages

### 6. Optimize Performance
- Use debouncing for rapid events
- Use throttling for high-frequency events
- Minimize DOM queries in event handlers

This reference document provides consistent patterns for event handling across the entire scheduler system, ensuring maintainable and reliable code.
