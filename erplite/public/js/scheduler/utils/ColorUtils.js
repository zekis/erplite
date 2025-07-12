/**
 * ColorUtils - Color manipulation utilities for the scheduler
 * Handles color conversion, validation, and palette generation
 */
class ColorUtils {
    /**
     * Convert hex color to rgba with alpha
     * @param {string} hex - Hex color string (with or without #)
     * @param {number} alpha - Alpha value (0-1)
     * @returns {string} RGBA color string
     */
    static hexToRgba(hex, alpha = 1) {
        let c = hex.replace('#', '');
        if (c.length === 3) {
            c = c.split('').map(x => x + x).join('');
        }
        const num = parseInt(c, 16);
        const r = (num >> 16) & 255;
        const g = (num >> 8) & 255;
        const b = num & 255;
        return `rgba(${r},${g},${b},${alpha})`;
    }

    /**
     * Convert RGB values to hex
     * @param {number} r - Red value (0-255)
     * @param {number} g - Green value (0-255)
     * @param {number} b - Blue value (0-255)
     * @returns {string} Hex color string
     */
    static rgbToHex(r, g, b) {
        return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }

    /**
     * Parse color string to RGB values
     * @param {string} color - Color string (hex, rgb, rgba)
     * @returns {Object} RGB values {r, g, b, a}
     */
    static parseColor(color) {
        // Handle hex colors
        if (color.startsWith('#')) {
            const hex = color.replace('#', '');
            let r, g, b;
            
            if (hex.length === 3) {
                r = parseInt(hex[0] + hex[0], 16);
                g = parseInt(hex[1] + hex[1], 16);
                b = parseInt(hex[2] + hex[2], 16);
            } else if (hex.length === 6) {
                r = parseInt(hex.substr(0, 2), 16);
                g = parseInt(hex.substr(2, 2), 16);
                b = parseInt(hex.substr(4, 2), 16);
            } else {
                return null;
            }
            
            return { r, g, b, a: 1 };
        }
        
        // Handle rgb/rgba colors
        const rgbMatch = color.match(/rgba?\(([^)]+)\)/);
        if (rgbMatch) {
            const values = rgbMatch[1].split(',').map(v => parseFloat(v.trim()));
            return {
                r: values[0] || 0,
                g: values[1] || 0,
                b: values[2] || 0,
                a: values[3] !== undefined ? values[3] : 1
            };
        }
        
        return null;
    }

    /**
     * Validate if a string is a valid color
     * @param {string} color - Color string to validate
     * @returns {boolean} True if valid color
     */
    static isValidColor(color) {
        if (!color || typeof color !== 'string') {
            return false;
        }
        
        // Check hex format
        if (color.startsWith('#')) {
            const hex = color.replace('#', '');
            return /^[0-9A-Fa-f]{3}$|^[0-9A-Fa-f]{6}$/.test(hex);
        }
        
        // Check rgb/rgba format
        if (color.startsWith('rgb')) {
            return /^rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(,\s*[0-1]?\.?\d+)?\s*\)$/.test(color);
        }
        
        // Check named colors (basic set)
        const namedColors = [
            'red', 'green', 'blue', 'yellow', 'orange', 'purple', 'pink',
            'brown', 'black', 'white', 'gray', 'grey', 'cyan', 'magenta'
        ];
        
        return namedColors.includes(color.toLowerCase());
    }

    /**
     * Lighten a color by a percentage
     * @param {string} color - Color string
     * @param {number} percent - Percentage to lighten (0-100)
     * @returns {string} Lightened color
     */
    static lighten(color, percent) {
        const rgb = this.parseColor(color);
        if (!rgb) return color;
        
        const factor = percent / 100;
        const r = Math.min(255, Math.round(rgb.r + (255 - rgb.r) * factor));
        const g = Math.min(255, Math.round(rgb.g + (255 - rgb.g) * factor));
        const b = Math.min(255, Math.round(rgb.b + (255 - rgb.b) * factor));
        
        return this.rgbToHex(r, g, b);
    }

    /**
     * Darken a color by a percentage
     * @param {string} color - Color string
     * @param {number} percent - Percentage to darken (0-100)
     * @returns {string} Darkened color
     */
    static darken(color, percent) {
        const rgb = this.parseColor(color);
        if (!rgb) return color;
        
        const factor = 1 - (percent / 100);
        const r = Math.max(0, Math.round(rgb.r * factor));
        const g = Math.max(0, Math.round(rgb.g * factor));
        const b = Math.max(0, Math.round(rgb.b * factor));
        
        return this.rgbToHex(r, g, b);
    }

    /**
     * Get contrast color (black or white) for a given background color
     * @param {string} backgroundColor - Background color
     * @returns {string} Contrast color (#000000 or #ffffff)
     */
    static getContrastColor(backgroundColor) {
        const rgb = this.parseColor(backgroundColor);
        if (!rgb) return '#000000';
        
        // Calculate luminance
        const luminance = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255;
        
        return luminance > 0.5 ? '#000000' : '#ffffff';
    }

    /**
     * Generate a color palette
     * @param {number} count - Number of colors to generate
     * @param {Object} options - Generation options
     * @returns {Array} Array of hex color strings
     */
    static generatePalette(count, options = {}) {
        const {
            saturation = 70,
            lightness = 50,
            startHue = 0
        } = options;
        
        const colors = [];
        const hueStep = 360 / count;
        
        for (let i = 0; i < count; i++) {
            const hue = (startHue + (i * hueStep)) % 360;
            const color = this.hslToHex(hue, saturation, lightness);
            colors.push(color);
        }
        
        return colors;
    }

    /**
     * Convert HSL to hex
     * @param {number} h - Hue (0-360)
     * @param {number} s - Saturation (0-100)
     * @param {number} l - Lightness (0-100)
     * @returns {string} Hex color string
     */
    static hslToHex(h, s, l) {
        h = h / 360;
        s = s / 100;
        l = l / 100;
        
        const hue2rgb = (p, q, t) => {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1/6) return p + (q - p) * 6 * t;
            if (t < 1/2) return q;
            if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
            return p;
        };
        
        let r, g, b;
        
        if (s === 0) {
            r = g = b = l; // achromatic
        } else {
            const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            const p = 2 * l - q;
            r = hue2rgb(p, q, h + 1/3);
            g = hue2rgb(p, q, h);
            b = hue2rgb(p, q, h - 1/3);
        }
        
        const toHex = (c) => {
            const hex = Math.round(c * 255).toString(16);
            return hex.length === 1 ? '0' + hex : hex;
        };
        
        return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
    }

    /**
     * Get default project color palette
     * @returns {Array} Array of hex color strings
     */
    static getDefaultProjectColors() {
        return [
            '#3b82f6', // Blue
            '#ef4444', // Red
            '#10b981', // Green
            '#f59e0b', // Amber
            '#8b5cf6', // Purple
            '#06b6d4', // Cyan
            '#84cc16', // Lime
            '#f97316', // Orange
            '#ec4899', // Pink
            '#6366f1', // Indigo
            '#14b8a6', // Teal
            '#eab308', // Yellow
            '#dc2626', // Red-600
            '#059669', // Green-600
            '#7c3aed', // Purple-600
            '#0891b2', // Cyan-600
            '#65a30d', // Lime-600
            '#ea580c', // Orange-600
            '#db2777', // Pink-600
            '#4f46e5'  // Indigo-600
        ];
    }

    /**
     * Assign colors to projects automatically
     * @param {Array} projects - Array of project objects
     * @returns {Object} Object mapping project names to colors
     */
    static assignProjectColors(projects) {
        const colors = this.getDefaultProjectColors();
        const colorMap = {};
        
        projects.forEach((project, index) => {
            const colorIndex = index % colors.length;
            colorMap[project.name] = colors[colorIndex];
        });
        
        return colorMap;
    }

    /**
     * Get color variations for a base color
     * @param {string} baseColor - Base color hex string
     * @returns {Object} Object with color variations
     */
    static getColorVariations(baseColor) {
        return {
            base: baseColor,
            light: this.lighten(baseColor, 20),
            lighter: this.lighten(baseColor, 40),
            dark: this.darken(baseColor, 20),
            darker: this.darken(baseColor, 40),
            contrast: this.getContrastColor(baseColor),
            alpha50: this.hexToRgba(baseColor, 0.5),
            alpha25: this.hexToRgba(baseColor, 0.25),
            alpha10: this.hexToRgba(baseColor, 0.1)
        };
    }

    /**
     * Blend two colors
     * @param {string} color1 - First color
     * @param {string} color2 - Second color
     * @param {number} ratio - Blend ratio (0-1, 0 = all color1, 1 = all color2)
     * @returns {string} Blended color
     */
    static blendColors(color1, color2, ratio = 0.5) {
        const rgb1 = this.parseColor(color1);
        const rgb2 = this.parseColor(color2);
        
        if (!rgb1 || !rgb2) return color1;
        
        const r = Math.round(rgb1.r + (rgb2.r - rgb1.r) * ratio);
        const g = Math.round(rgb1.g + (rgb2.g - rgb1.g) * ratio);
        const b = Math.round(rgb1.b + (rgb2.b - rgb1.b) * ratio);
        
        return this.rgbToHex(r, g, b);
    }
}

// Export for use in other modules
window.SchedulerColorUtils = ColorUtils;
