import { ref } from 'vue'

// Global drag state (singleton pattern)
const globalDragState = {
  isDragSelecting: ref(false),
  isDragOver: ref(false),
  dragSelection: ref(null),
  dragTooltip: ref({
    isVisible: false,
    position: { x: 0, y: 0 },
    selectedDates: []
  })
}

export function useDragDrop() {
  // Use global state
  const isDragSelecting = globalDragState.isDragSelecting
  const isDragOver = globalDragState.isDragOver
  const dragSelection = globalDragState.dragSelection
  const dragTooltip = globalDragState.dragTooltip

  // Start drag selection for multi-day entries
  const startDragSelection = (event, rowIndex, startDate, showContextMenuCallback) => {
    isDragSelecting.value = true
    
    // Create bound functions that we can properly remove later
    const boundHandleDragSelection = (e) => handleDragSelection(e)
    const boundEndDragSelection = (e) => {
      // Remove event listeners first
      document.removeEventListener('mousemove', boundHandleDragSelection)
      document.removeEventListener('mouseup', boundEndDragSelection)
      
      // Then call the actual end function
      endDragSelection(e, showContextMenuCallback)
    }
    
    dragSelection.value = {
      active: true,
      rowIndex: rowIndex,
      startDate: startDate,
      currentDate: startDate,
      selectedDates: [startDate],
      startX: event.clientX,
      startY: event.clientY,
      showContextMenuCallback: showContextMenuCallback,
      boundHandleDragSelection: boundHandleDragSelection,
      boundEndDragSelection: boundEndDragSelection
    }

    document.addEventListener('mousemove', boundHandleDragSelection)
    document.addEventListener('mouseup', boundEndDragSelection)

    // Show initial tooltip
    dragTooltip.value.isVisible = true
    dragTooltip.value.position = { x: event.clientX + 15, y: event.clientY - 50 }
    dragTooltip.value.selectedDates = [startDate]

    // Prevent text selection
    document.body.style.userSelect = 'none'
  }

  // Handle drag selection movement
  const handleDragSelection = (event) => {
    if (!dragSelection.value || !dragSelection.value.active) return

    // Find the day cell under the mouse (could be EmptyDayCell or TimeEntryCell)
    const elementUnderMouse = document.elementFromPoint(event.clientX, event.clientY)
    const cell = elementUnderMouse ? elementUnderMouse.closest('[data-date][data-row-index]') : null

    if (!cell || !cell.dataset.date || !cell.dataset.rowIndex) return

    const rowIndex = parseInt(cell.dataset.rowIndex)
    const date = cell.dataset.date

    // Only allow selection within the same row
    if (rowIndex !== dragSelection.value.rowIndex) return

    // Update current date
    dragSelection.value.currentDate = date

    // Clear previous selection styling - only for this specific row
    const previousSelected = document.querySelectorAll(`.empty-day-cell.drag-selected[data-row-index="${dragSelection.value.rowIndex}"]`)
    previousSelected.forEach(cell => {
      cell.classList.remove('drag-selected')
    })

    // Calculate date range between start and current
    const startDate = new Date(dragSelection.value.startDate)
    const currentDate = new Date(date)
    const minDate = startDate < currentDate ? startDate : currentDate
    const maxDate = startDate > currentDate ? startDate : currentDate

    // Update selected dates array
    dragSelection.value.selectedDates = []
    const iterDate = new Date(minDate)

    while (iterDate <= maxDate) {
      const dateStr = iterDate.toISOString().split('T')[0]
      dragSelection.value.selectedDates.push(dateStr)
      iterDate.setDate(iterDate.getDate() + 1)
    }

    // Mark all empty cells in range as selected (only empty cells can be selected for creation)
    dragSelection.value.selectedDates.forEach(dateStr => {
      const emptyCell = document.querySelector(`.empty-day-cell[data-date="${dateStr}"][data-row-index="${rowIndex}"]`)
      if (emptyCell) {
        emptyCell.classList.add('drag-selected')
      }
    })

    // Update tooltip with current selection - update properties individually for reactivity
    dragTooltip.value.isVisible = true
    dragTooltip.value.position = { x: event.clientX + 15, y: event.clientY - 50 }
    dragTooltip.value.selectedDates = [...dragSelection.value.selectedDates]
  }

  // End drag selection
  const endDragSelection = (event, showContextMenuCallback) => {
    if (!dragSelection.value || !dragSelection.value.active) return

    // Clean up event listeners
    document.removeEventListener('mousemove', handleDragSelection)
    document.removeEventListener('mouseup', endDragSelection)

    // Restore text selection
    document.body.style.userSelect = ''

    // Clear selection styling - only for the specific row that was being dragged
    const rowIndex = dragSelection.value.rowIndex
    document.querySelectorAll(`.empty-day-cell.drag-selected[data-row-index="${rowIndex}"]`).forEach(cell => {
      cell.classList.remove('drag-selected')
    })

    const selectedDates = dragSelection.value.selectedDates
    // Use the callback stored in dragSelection, not the parameter
    const callback = dragSelection.value.showContextMenuCallback

    // Hide tooltip
    dragTooltip.value.isVisible = false

    // Show context menu if we have selected dates
    if (selectedDates.length > 0 && callback) {
      const position = {
        x: event.clientX,
        y: event.clientY
      }
      console.log('🎯 Step 1 - useDragDrop calling callback:', { selectedDates, position })
      callback(selectedDates, position)
    }

    // Reset drag selection
    isDragSelecting.value = false
    dragSelection.value = null
  }

  // Template drag handlers
  const handleTemplateDragStart = (event, template) => {
    event.dataTransfer.setData('text/plain', JSON.stringify({
      type: 'template',
      template: template
    }))
    
    event.dataTransfer.effectAllowed = 'copy'
    event.target.classList.add('dragging')
  }

  const handleTemplateDragEnd = (event) => {
    event.target.classList.remove('dragging')
  }

  // Time block drag handlers
  const handleTimeBlockDragStart = (event, entryData) => {
    event.dataTransfer.setData('text/plain', JSON.stringify({
      type: 'time-block',
      entryId: entryData.id,
      entry: entryData
    }))
    
    event.dataTransfer.effectAllowed = 'move'
    event.target.classList.add('dragging')
  }

  const handleTimeBlockDragEnd = (event) => {
    event.target.classList.remove('dragging')
  }

  return {
    // State
    isDragSelecting,
    isDragOver,
    dragSelection,
    dragTooltip,
    
    // Methods
    startDragSelection,
    handleDragSelection,
    endDragSelection,
    handleTemplateDragStart,
    handleTemplateDragEnd,
    handleTimeBlockDragStart,
    handleTimeBlockDragEnd
  }
}
