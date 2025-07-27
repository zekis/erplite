/**
 * Everything Search Application
 * Modern web interface for Everything HTTP API
 */

class EverythingSearchApp {
    constructor() {
        // Configuration (server settings are hardcoded in backend)
        this.config = {
            resultsPerPage: 50,
            autoSearch: true,
            searchDelay: 300
        };
        
        // State
        this.state = {
            isConnected: false,
            currentQuery: '',
            currentResults: [],
            totalResults: 0,
            currentOffset: 0,
            isLoading: false,
            currentView: 'list', // 'list' or 'grid'
            searchOptions: {
                case: false,
                wholeWord: false,
                path: false,
                regex: false
            },
            sortBy: 'name',
            sortAscending: true
        };
        
        // Timers
        this.searchTimer = null;
        this.connectionTimer = null;
        
        // Elements
        this.elements = {};
        
        this.init();
    }
    
    /**
     * Initialize the application
     */
    init() {
        this.loadSettings();
        this.initializeElements();
        this.setupEventListeners();
        this.checkConnection();
        
        console.log('Everything Search initialized');
    }
    
    /**
     * Load settings from localStorage
     */
    loadSettings() {
        const saved = localStorage.getItem('everything-search-settings');
        if (saved) {
            try {
                const settings = JSON.parse(saved);
                this.config = { ...this.config, ...settings };
            } catch (error) {
                console.error('Failed to load settings:', error);
            }
        }
    }
    
    /**
     * Save settings to localStorage
     */
    saveSettings() {
        try {
            localStorage.setItem('everything-search-settings', JSON.stringify(this.config));
        } catch (error) {
            console.error('Failed to save settings:', error);
        }
    }
    
    /**
     * Initialize DOM elements
     */
    initializeElements() {
        this.elements = {
            // Status
            statusIndicator: document.getElementById('statusIndicator'),
            statusText: document.getElementById('statusText'),
            
            // Search
            searchInput: document.getElementById('searchInput'),
            clearSearchBtn: document.getElementById('clearSearchBtn'),
            
            // Options
            caseOption: document.getElementById('caseOption'),
            wholeWordOption: document.getElementById('wholeWordOption'),
            pathOption: document.getElementById('pathOption'),
            regexOption: document.getElementById('regexOption'),
            
            // Sort
            sortOption: document.getElementById('sortOption'),
            sortDirectionBtn: document.getElementById('sortDirectionBtn'),
            
            // Results
            resultsHeader: document.getElementById('resultsHeader'),
            resultsCount: document.getElementById('resultsCount'),
            searchTime: document.getElementById('searchTime'),
            listViewBtn: document.getElementById('listViewBtn'),
            gridViewBtn: document.getElementById('gridViewBtn'),
            
            // States
            welcomeState: document.getElementById('welcomeState'),
            loadingState: document.getElementById('loadingState'),
            resultsList: document.getElementById('resultsList'),
            noResultsState: document.getElementById('noResultsState'),
            errorState: document.getElementById('errorState'),
            errorDescription: document.getElementById('errorDescription'),
            
            // Load more
            loadMoreContainer: document.getElementById('loadMoreContainer'),
            loadMoreBtn: document.getElementById('loadMoreBtn'),
            
            // Context menu
            contextMenu: document.getElementById('contextMenu'),
            openFileBtn: document.getElementById('openFileBtn'),
            openFolderBtn: document.getElementById('openFolderBtn'),
            downloadFileBtn: document.getElementById('downloadFileBtn'),
            copyPathBtn: document.getElementById('copyPathBtn'),
            copyNameBtn: document.getElementById('copyNameBtn'),
            
            // Other
            retryBtn: document.getElementById('retryBtn')
        };
    }
    
    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Search input
        this.elements.searchInput.addEventListener('input', (e) => {
            this.handleSearchInput(e.target.value);
        });
        
        this.elements.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.performSearch();
            } else if (e.key === 'Escape') {
                this.clearSearch();
            }
        });
        
        // Clear search
        this.elements.clearSearchBtn.addEventListener('click', () => {
            this.clearSearch();
        });
        
        // Search options
        this.elements.caseOption.addEventListener('change', (e) => {
            this.state.searchOptions.case = e.target.checked;
            this.performSearch();
        });
        
        this.elements.wholeWordOption.addEventListener('change', (e) => {
            this.state.searchOptions.wholeWord = e.target.checked;
            this.performSearch();
        });
        
        this.elements.pathOption.addEventListener('change', (e) => {
            this.state.searchOptions.path = e.target.checked;
            this.performSearch();
        });
        
        this.elements.regexOption.addEventListener('change', (e) => {
            this.state.searchOptions.regex = e.target.checked;
            this.performSearch();
        });
        
        // Sort options
        this.elements.sortOption.addEventListener('change', (e) => {
            this.state.sortBy = e.target.value;
            this.performSearch();
        });
        
        this.elements.sortDirectionBtn.addEventListener('click', () => {
            this.toggleSortDirection();
        });
        
        // View options
        this.elements.listViewBtn.addEventListener('click', () => {
            this.setView('list');
        });
        
        this.elements.gridViewBtn.addEventListener('click', () => {
            this.setView('grid');
        });
        
        // Load more
        this.elements.loadMoreBtn.addEventListener('click', () => {
            this.loadMoreResults();
        });
        
        // Retry connection
        this.elements.retryBtn.addEventListener('click', () => {
            this.checkConnection();
        });
        
        // Context menu
        document.addEventListener('click', () => {
            this.hideContextMenu();
        });
        
        this.elements.openFileBtn.addEventListener('click', () => {
            this.openSelectedFile();
        });
        
        this.elements.openFolderBtn.addEventListener('click', () => {
            this.openSelectedFolder();
        });
        
        this.elements.downloadFileBtn.addEventListener('click', () => {
            this.downloadSelectedFile();
        });
        
        this.elements.copyPathBtn.addEventListener('click', () => {
            this.copySelectedPath();
        });
        
        this.elements.copyNameBtn.addEventListener('click', () => {
            this.copySelectedName();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });
    }
    
    /**
     * Handle search input with debouncing
     */
    handleSearchInput(query) {
        this.state.currentQuery = query;
        
        // Show/hide clear button
        if (query.length > 0) {
            this.elements.clearSearchBtn.classList.add('visible');
        } else {
            this.elements.clearSearchBtn.classList.remove('visible');
        }
        
        // Clear existing timer
        if (this.searchTimer) {
            clearTimeout(this.searchTimer);
        }
        
        // Auto search if enabled
        if (this.config.autoSearch && query.length > 0) {
            this.searchTimer = setTimeout(() => {
                this.performSearch();
            }, this.config.searchDelay);
        } else if (query.length === 0) {
            this.showWelcomeState();
        }
    }
    
    /**
     * Clear search
     */
    clearSearch() {
        this.elements.searchInput.value = '';
        this.state.currentQuery = '';
        this.elements.clearSearchBtn.classList.remove('visible');
        this.showWelcomeState();
        this.elements.searchInput.focus();
    }
    
    /**
     * Perform search
     */
    async performSearch(offset = 0) {
        if (!this.state.currentQuery.trim()) {
            this.showWelcomeState();
            return;
        }
        
        if (!this.state.isConnected) {
            this.showErrorState('Not connected to Everything server');
            return;
        }
        
        // Reset offset for new search
        if (offset === 0) {
            this.state.currentOffset = 0;
            this.state.currentResults = [];
        }
        
        this.showLoadingState();
        
        const startTime = Date.now();
        
        try {
            const results = await this.searchEverything(this.state.currentQuery, offset);
            const searchTime = Date.now() - startTime;
            
            if (offset === 0) {
                this.state.currentResults = results.results || [];
                this.state.totalResults = results.totalResults || 0;
            } else {
                this.state.currentResults.push(...(results.results || []));
            }
            
            this.state.currentOffset = offset + this.config.resultsPerPage;
            
            this.displayResults(searchTime);
            
        } catch (error) {
            console.error('Search failed:', error);
            this.showErrorState(error.message);
        }
    }
    
    /**
     * Search Everything via backend API
     */
    async searchEverything(query, offset = 0) {
        // Build request parameters
        const params = {
            query: query,
            offset: offset.toString(),
            count: this.config.resultsPerPage.toString(),
            sort: this.state.sortBy,
            ascending: this.state.sortAscending ? '1' : '0'
        };
        
        // Add search options
        if (this.state.searchOptions.case) params.case = '1';
        if (this.state.searchOptions.wholeWord) params.wholeword = '1';
        if (this.state.searchOptions.path) params.path = '1';
        if (this.state.searchOptions.regex) params.regex = '1';
        
        // Make request to backend API
        const response = await frappe.call({
            method: 'erplite.everything_search.api.search_everything',
            args: params
        });
        
        if (!response.message.success) {
            throw new Error(response.message.error || 'Search failed');
        }
        
        return {
            results: response.message.results || [],
            totalResults: response.message.totalResults || 0
        };
    }
    
    /**
     * Display search results
     */
    displayResults(searchTime) {
        if (this.state.currentResults.length === 0) {
            this.showNoResultsState();
            return;
        }
        
        // Update results header
        this.elements.resultsCount.textContent = `${this.state.currentResults.length} of ${this.state.totalResults} results`;
        this.elements.searchTime.textContent = `(${searchTime}ms)`;
        
        // Show results header
        this.elements.resultsHeader.style.display = 'flex';
        
        // Render results
        this.renderResults();
        
        // Show/hide load more button
        const hasMore = this.state.currentResults.length < this.state.totalResults;
        this.elements.loadMoreContainer.style.display = hasMore ? 'block' : 'none';
        
        this.showResultsState();
    }
    
    /**
     * Render results list
     */
    renderResults() {
        this.elements.resultsList.innerHTML = '';
        
        // Apply view class
        this.elements.resultsList.className = `results-list ${this.state.currentView === 'grid' ? 'grid-view' : ''}`;
        
        this.state.currentResults.forEach((result, index) => {
            const resultElement = this.createResultElement(result, index);
            this.elements.resultsList.appendChild(resultElement);
        });
    }
    
    /**
     * Create result element
     */
    createResultElement(result, index) {
        const div = document.createElement('div');
        div.className = 'result-item';
        div.dataset.index = index;
        div.dataset.path = result.path;
        div.dataset.name = result.name;
        div.dataset.isFolder = result.type === 'folder' ? 'true' : 'false';
        
        const isFolder = result.type === 'folder';
        const icon = isFolder ? 'mdi-folder' : this.getFileIcon(result.name);
        const iconClass = isFolder ? 'folder' : 'file';
        
        div.innerHTML = `
            <div class="result-header">
                <i class="mdi ${icon} result-icon ${iconClass}"></i>
                <div class="result-name">${this.escapeHtml(result.name)}</div>
                ${!isFolder && result.size ? `<div class="result-size">${this.formatFileSize(result.size)}</div>` : ''}
            </div>
            <div class="result-path">${this.escapeHtml(result.path)}</div>
            ${result.date_modified ? `
                <div class="result-meta">
                    <div class="result-date">
                        <i class="mdi mdi-clock-outline"></i>
                        ${this.formatDate(result.date_modified)}
                    </div>
                </div>
            ` : ''}
        `;
        
        // Add event listeners
        div.addEventListener('click', () => {
            this.selectResult(div);
        });
        
        div.addEventListener('dblclick', () => {
            this.openResult(result);
        });
        
        div.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.showContextMenu(e, div);
        });
        
        return div;
    }
    
    /**
     * Get file icon based on extension
     */
    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        
        const iconMap = {
            // Documents
            'pdf': 'mdi-file-pdf-box',
            'doc': 'mdi-file-word-box',
            'docx': 'mdi-file-word-box',
            'xls': 'mdi-file-excel-box',
            'xlsx': 'mdi-file-excel-box',
            'ppt': 'mdi-file-powerpoint-box',
            'pptx': 'mdi-file-powerpoint-box',
            'txt': 'mdi-file-document-outline',
            
            // Images
            'jpg': 'mdi-file-image',
            'jpeg': 'mdi-file-image',
            'png': 'mdi-file-image',
            'gif': 'mdi-file-image',
            'bmp': 'mdi-file-image',
            'svg': 'mdi-file-image',
            
            // Videos
            'mp4': 'mdi-file-video',
            'avi': 'mdi-file-video',
            'mkv': 'mdi-file-video',
            'mov': 'mdi-file-video',
            'wmv': 'mdi-file-video',
            
            // Audio
            'mp3': 'mdi-file-music',
            'wav': 'mdi-file-music',
            'flac': 'mdi-file-music',
            'aac': 'mdi-file-music',
            
            // Archives
            'zip': 'mdi-folder-zip',
            'rar': 'mdi-folder-zip',
            '7z': 'mdi-folder-zip',
            'tar': 'mdi-folder-zip',
            'gz': 'mdi-folder-zip',
            
            // Code
            'js': 'mdi-language-javascript',
            'html': 'mdi-language-html5',
            'css': 'mdi-language-css3',
            'py': 'mdi-language-python',
            'java': 'mdi-language-java',
            'cpp': 'mdi-language-cpp',
            'c': 'mdi-language-c',
            'php': 'mdi-language-php',
            'json': 'mdi-code-json',
            'xml': 'mdi-file-xml-box',
            
            // Executables
            'exe': 'mdi-application',
            'msi': 'mdi-application',
            'app': 'mdi-application',
            'deb': 'mdi-application',
            'rpm': 'mdi-application'
        };
        
        return iconMap[ext] || 'mdi-file-outline';
    }
    
    /**
     * Format file size
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
    
    /**
     * Format date
     */
    formatDate(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        } catch (error) {
            return dateString;
        }
    }
    
    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Select result
     */
    selectResult(element) {
        // Clear previous selection
        document.querySelectorAll('.result-item.selected').forEach(item => {
            item.classList.remove('selected');
        });
        
        // Select current
        element.classList.add('selected');
        this.selectedResult = element;
    }
    
    /**
     * Open result (double-click)
     */
    openResult(result) {
        const path = result.path;
        
        // Try to open the file/folder
        if (navigator.platform.indexOf('Win') !== -1) {
            // Windows
            window.open(`file:///${path.replace(/\\/g, '/')}`);
        } else {
            // Other platforms
            window.open(`file://${path}`);
        }
    }
    
    /**
     * Load more results
     */
    async loadMoreResults() {
        if (this.state.isLoading) return;
        
        await this.performSearch(this.state.currentOffset);
    }
    
    /**
     * Toggle sort direction
     */
    toggleSortDirection() {
        this.state.sortAscending = !this.state.sortAscending;
        
        const icon = this.elements.sortDirectionBtn.querySelector('i');
        icon.className = this.state.sortAscending ? 'mdi mdi-sort-ascending' : 'mdi mdi-sort-descending';
        
        this.performSearch();
    }
    
    /**
     * Set view mode
     */
    setView(view) {
        this.state.currentView = view;
        
        // Update buttons
        this.elements.listViewBtn.classList.toggle('active', view === 'list');
        this.elements.gridViewBtn.classList.toggle('active', view === 'grid');
        
        // Re-render results
        if (this.state.currentResults.length > 0) {
            this.renderResults();
        }
    }
    
    /**
     * Show context menu
     */
    showContextMenu(event, element) {
        this.selectResult(element);
        
        const menu = this.elements.contextMenu;
        menu.style.display = 'block';
        menu.style.left = event.pageX + 'px';
        menu.style.top = event.pageY + 'px';
        
        // Adjust position if menu goes off screen
        const rect = menu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            menu.style.left = (event.pageX - rect.width) + 'px';
        }
        if (rect.bottom > window.innerHeight) {
            menu.style.top = (event.pageY - rect.height) + 'px';
        }
    }
    
    /**
     * Hide context menu
     */
    hideContextMenu() {
        this.elements.contextMenu.style.display = 'none';
    }
    
    /**
     * Open selected file
     */
    openSelectedFile() {
        if (!this.selectedResult) return;
        
        const path = this.selectedResult.dataset.path;
        this.openPath(path);
        this.hideContextMenu();
    }
    
    /**
     * Open selected folder
     */
    openSelectedFolder() {
        if (!this.selectedResult) return;
        
        const path = this.selectedResult.dataset.path;
        const isFolder = this.selectedResult.dataset.isFolder === 'true';
        
        if (isFolder) {
            this.openPath(path);
        } else {
            // Open parent folder
            const parentPath = path.substring(0, path.lastIndexOf('\\'));
            this.openPath(parentPath);
        }
        
        this.hideContextMenu();
    }
    
    /**
     * Download selected file
     */
    async downloadSelectedFile() {
        if (!this.selectedResult) return;
        
        const path = this.selectedResult.dataset.path;
        const name = this.selectedResult.dataset.name;
        const isFolder = this.selectedResult.dataset.isFolder === 'true';
        
        // Don't allow downloading folders
        if (isFolder) {
            this.showToast('Cannot download folders', 'warning');
            this.hideContextMenu();
            return;
        }
        
        try {
            this.showToast('Starting download...', 'info');
            
            // Create a temporary form to trigger the download
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/api/method/erplite.everything_search.api.download_file';
            form.target = '_blank';
            form.style.display = 'none';
            
            // Add CSRF token
            const csrfToken = document.querySelector('meta[name="csrf-token"]');
            if (csrfToken) {
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                csrfInput.value = csrfToken.getAttribute('content');
                form.appendChild(csrfInput);
            }
            
            // Add file path parameter
            const pathInput = document.createElement('input');
            pathInput.type = 'hidden';
            pathInput.name = 'file_path';
            pathInput.value = path;
            form.appendChild(pathInput);
            
            // Submit form to trigger download
            document.body.appendChild(form);
            form.submit();
            document.body.removeChild(form);
            
            this.showToast(`Downloading ${name}...`, 'success');
            
        } catch (error) {
            console.error('Failed to download file:', error);
            this.showToast('Failed to download file: ' + error.message, 'error');
        }
        
        this.hideContextMenu();
    }
    
    /**
     * Copy selected path
     */
    async copySelectedPath() {
        if (!this.selectedResult) return;
        
        const path = this.selectedResult.dataset.path;
        
        try {
            await navigator.clipboard.writeText(path);
            this.showToast('Path copied to clipboard');
        } catch (error) {
            console.error('Failed to copy path:', error);
            this.showToast('Failed to copy path', 'error');
        }
        
        this.hideContextMenu();
    }
    
    /**
     * Copy selected name
     */
    async copySelectedName() {
        if (!this.selectedResult) return;
        
        const name = this.selectedResult.dataset.name;
        
        try {
            await navigator.clipboard.writeText(name);
            this.showToast('Name copied to clipboard');
        } catch (error) {
            console.error('Failed to copy name:', error);
            this.showToast('Failed to copy name', 'error');
        }
        
        this.hideContextMenu();
    }
    
    /**
     * Open path
     */
    openPath(path) {
        if (navigator.platform.indexOf('Win') !== -1) {
            // Windows - use file:// protocol
            window.open(`file:///${path.replace(/\\/g, '/')}`);
        } else {
            // Other platforms
            window.open(`file://${path}`);
        }
    }
    
    /**
     * Check connection to Everything server via backend API
     */
    async checkConnection() {
        this.updateConnectionStatus('connecting', 'Connecting...');
        
        try {
            const response = await frappe.call({
                method: 'erplite.everything_search.api.test_connection',
                args: {}
            });
            
            if (response.message.success) {
                this.state.isConnected = true;
                this.updateConnectionStatus('online', 'Connected');
            } else {
                throw new Error(response.message.error || 'Connection failed');
            }
        } catch (error) {
            this.state.isConnected = false;
            this.updateConnectionStatus('offline', 'Offline');
            console.error('Connection failed:', error);
        }
    }
    
    /**
     * Update connection status
     */
    updateConnectionStatus(status, text) {
        this.elements.statusIndicator.className = `status-indicator ${status}`;
        this.elements.statusText.textContent = text;
    }
    
    /**
     * Show different states
     */
    showWelcomeState() {
        this.hideAllStates();
        this.elements.welcomeState.style.display = 'flex';
        this.elements.resultsHeader.style.display = 'none';
    }
    
    showLoadingState() {
        this.state.isLoading = true;
        this.hideAllStates();
        this.elements.loadingState.style.display = 'flex';
    }
    
    showResultsState() {
        this.state.isLoading = false;
        this.hideAllStates();
        this.elements.resultsList.style.display = 'flex';
    }
    
    showNoResultsState() {
        this.state.isLoading = false;
        this.hideAllStates();
        this.elements.noResultsState.style.display = 'flex';
        this.elements.resultsHeader.style.display = 'flex';
        this.elements.resultsCount.textContent = '0 results';
    }
    
    showErrorState(message) {
        this.state.isLoading = false;
        this.hideAllStates();
        this.elements.errorState.style.display = 'flex';
        this.elements.errorDescription.textContent = message;
        this.elements.resultsHeader.style.display = 'none';
    }
    
    hideAllStates() {
        this.elements.welcomeState.style.display = 'none';
        this.elements.loadingState.style.display = 'none';
        this.elements.resultsList.style.display = 'none';
        this.elements.noResultsState.style.display = 'none';
        this.elements.errorState.style.display = 'none';
        this.elements.loadMoreContainer.style.display = 'none';
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(event) {
        // Ctrl/Cmd + K: Focus search
        if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
            event.preventDefault();
            this.elements.searchInput.focus();
            this.elements.searchInput.select();
        }
        
        // F5: Refresh connection
        if (event.key === 'F5') {
            event.preventDefault();
            this.checkConnection();
        }
        
        // Escape: Clear search
        if (event.key === 'Escape') {
            if (this.state.currentQuery) {
                this.clearSearch();
            }
        }
    }
    
    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="mdi ${this.getToastIcon(type)}"></i>
            <span>${message}</span>
        `;
        
        // Add to page
        document.body.appendChild(toast);
        
        // Position toast
        toast.style.position = 'fixed';
        toast.style.bottom = '2rem';
        toast.style.right = '2rem';
        toast.style.zIndex = '10002';
        toast.style.background = type === 'error' ? 'var(--danger-color)' : 'var(--gray-800)';
        toast.style.color = 'white';
        toast.style.padding = '0.75rem 1rem';
        toast.style.borderRadius = 'var(--border-radius)';
        toast.style.boxShadow = 'var(--shadow-lg)';
        toast.style.display = 'flex';
        toast.style.alignItems = 'center';
        toast.style.gap = '0.5rem';
        toast.style.fontSize = '0.875rem';
        toast.style.fontWeight = '500';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'transform 0.3s ease';
        
        // Show toast
        setTimeout(() => {
            toast.style.transform = 'translateX(0)';
        }, 100);
        
        // Hide and remove toast after 3 seconds
        setTimeout(() => {
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }
    
    /**
     * Get toast icon
     */
    getToastIcon(type) {
        switch (type) {
            case 'success': return 'mdi-check-circle';
            case 'error': return 'mdi-alert-circle';
            case 'warning': return 'mdi-alert';
            case 'info': 
            default: return 'mdi-information';
        }
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.everythingSearch = new EverythingSearchApp();
});

// Export for potential external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EverythingSearchApp;
}
