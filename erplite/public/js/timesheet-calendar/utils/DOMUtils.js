/**
 * DOM manipulation utility functions
 */
class DOMUtils {
    /**
     * Create element with attributes and content
     */
    static createElement(tag, attributes = {}, content = '') {
        const element = document.createElement(tag);
        
        Object.entries(attributes).forEach(([key, value]) => {
            if (key === 'className') {
                element.className = value;
            } else if (key === 'dataset') {
                Object.entries(value).forEach(([dataKey, dataValue]) => {
                    element.dataset[dataKey] = dataValue;
                });
            } else if (key === 'style') {
                Object.entries(value).forEach(([styleKey, styleValue]) => {
                    element.style[styleKey] = styleValue;
                });
            } else {
                element.setAttribute(key, value);
            }
        });
        
        if (content) {
            element.innerHTML = content;
        }
        
        return element;
    }
    
    /**
     * Remove all children from element
     */
    static clearElement(element) {
        while (element.firstChild) {
            element.removeChild(element.firstChild);
        }
    }
    
    /**
     * Add event listener with automatic cleanup
     */
    static addEventListenerWithCleanup(element, event, handler, options = {}) {
        element.addEventListener(event, handler, options);
        
        // Return cleanup function
        return () => {
            element.removeEventListener(event, handler, options);
        };
    }
    
    /**
     * Get element position relative to viewport
     */
    static getElementPosition(element) {
        const rect = element.getBoundingClientRect();
        return {
            top: rect.top,
            left: rect.left,
            bottom: rect.bottom,
            right: rect.right,
            width: rect.width,
            height: rect.height
        };
    }
    
    /**
     * Check if element is visible in viewport
     */
    static isElementVisible(element) {
        const rect = element.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    }
    
    /**
     * Scroll element into view smoothly
     */
    static scrollIntoView(element, options = {}) {
        const defaultOptions = {
            behavior: 'smooth',
            block: 'nearest',
            inline: 'nearest'
        };
        
        element.scrollIntoView({ ...defaultOptions, ...options });
    }
    
    /**
     * Find closest parent with specific selector
     */
    static findClosestParent(element, selector) {
        return element.closest(selector);
    }
    
    /**
     * Get all siblings of an element
     */
    static getSiblings(element) {
        return Array.from(element.parentNode.children).filter(child => child !== element);
    }
    
    /**
     * Insert element after another element
     */
    static insertAfter(newElement, referenceElement) {
        referenceElement.parentNode.insertBefore(newElement, referenceElement.nextSibling);
    }
    
    /**
     * Replace element with new element
     */
    static replaceElement(oldElement, newElement) {
        oldElement.parentNode.replaceChild(newElement, oldElement);
    }
    
    /**
     * Toggle class on element
     */
    static toggleClass(element, className, force = null) {
        if (force !== null) {
            element.classList.toggle(className, force);
        } else {
            element.classList.toggle(className);
        }
    }
    
    /**
     * Add multiple classes to element
     */
    static addClasses(element, ...classNames) {
        element.classList.add(...classNames);
    }
    
    /**
     * Remove multiple classes from element
     */
    static removeClasses(element, ...classNames) {
        element.classList.remove(...classNames);
    }
    
    /**
     * Check if element has class
     */
    static hasClass(element, className) {
        return element.classList.contains(className);
    }
    
    /**
     * Get or set element data attribute
     */
    static data(element, key, value = undefined) {
        if (value !== undefined) {
            element.dataset[key] = value;
        }
        return element.dataset[key];
    }
    
    /**
     * Show element (remove display: none)
     */
    static show(element) {
        element.style.display = '';
    }
    
    /**
     * Hide element (set display: none)
     */
    static hide(element) {
        element.style.display = 'none';
    }
    
    /**
     * Check if element is hidden
     */
    static isHidden(element) {
        return element.style.display === 'none' || 
               getComputedStyle(element).display === 'none';
    }
    
    /**
     * Fade in element
     */
    static fadeIn(element, duration = 300) {
        element.style.opacity = '0';
        element.style.display = '';
        
        const start = performance.now();
        
        function animate(currentTime) {
            const elapsed = currentTime - start;
            const progress = Math.min(elapsed / duration, 1);
            
            element.style.opacity = progress;
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        }
        
        requestAnimationFrame(animate);
    }
    
    /**
     * Fade out element
     */
    static fadeOut(element, duration = 300) {
        const start = performance.now();
        const startOpacity = parseFloat(getComputedStyle(element).opacity);
        
        function animate(currentTime) {
            const elapsed = currentTime - start;
            const progress = Math.min(elapsed / duration, 1);
            
            element.style.opacity = startOpacity * (1 - progress);
            
            if (progress >= 1) {
                element.style.display = 'none';
            } else {
                requestAnimationFrame(animate);
            }
        }
        
        requestAnimationFrame(animate);
    }
    
    /**
     * Get element's offset position relative to document
     */
    static getOffset(element) {
        const rect = element.getBoundingClientRect();
        return {
            top: rect.top + window.pageYOffset,
            left: rect.left + window.pageXOffset
        };
    }
    
    /**
     * Debounce function calls
     */
    static debounce(func, wait, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func(...args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func(...args);
        };
    }
    
    /**
     * Throttle function calls
     */
    static throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
}

// Export to global scope
window.DOMUtils = DOMUtils;
