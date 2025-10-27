# Vue.js + Frappe Framework Integration Guide

A comprehensive guide for building modern Vue.js applications integrated with Frappe Framework, including authentication, build integration, and best practices.

## Table of Contents

1. [Project Structure](#project-structure)
2. [Dependencies & Setup](#dependencies--setup)
3. [Frappe Integration](#frappe-integration)
4. [Authentication System](#authentication-system)
5. [Build Configuration](#build-configuration)
6. [Development Workflow](#development-workflow)
7. [API Integration](#api-integration)
8. [Styling & UI Components](#styling--ui-components)
9. [Deployment](#deployment)
10. [Best Practices](#best-practices)

## Project Structure

```
your_app/
├── frontend/                    # Vue.js frontend
│   ├── src/
│   │   ├── components/         # Vue components
│   │   ├── pages/             # Page components
│   │   ├── composables/       # Vue composables
│   │   ├── router.js          # Vue Router config
│   │   ├── main.js            # App entry point
│   │   └── App.vue            # Root component
│   ├── package.json           # Frontend dependencies
│   ├── vite.config.js         # Vite configuration
│   ├── tailwind.config.js     # Tailwind CSS config
│   └── index.html             # HTML template
├── your_app/
│   ├── www/
│   │   ├── your_app.html      # Frappe HTML template
│   │   └── your_app.py        # Python context handler
│   ├── public/
│   │   └── frontend/          # Built assets (auto-generated)
│   └── hooks.py               # Frappe hooks configuration
└── pyproject.toml             # Python dependencies
```

## Dependencies & Setup

### Frontend Dependencies (package.json)

```json
{
  "name": "your-app-ui",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build && yarn copy-html-entry",
    "copy-html-entry": "cp ../your_app/public/frontend/index.html ../your_app/www/your_app.html",
    "serve": "vite preview"
  },
  "dependencies": {
    "frappe-ui": "^0.1.121",
    "vue": "^3.5.13",
    "vue-router": "^4.2.2",
    "pinia": "^2.0.33",
    "@vueuse/core": "^10.7.2",
    "@iconify/vue": "^4.1.1",
    "@iconify-json/lucide": "^1.1.120",
    "date-fns": "^3.2.0",
    "lodash": "^4.17.21",
    "primevue": "^4.3.6",
    "@primeuix/themes": "^1.2.1"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^4.2.3",
    "@vitejs/plugin-vue-jsx": "^3.0.1",
    "vite": "^4.4.9",
    "tailwindcss": "^3.4.15",
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.5"
  }
}
```

### Python Dependencies (pyproject.toml)

```toml
[project]
dependencies = [
    "frappe>=15.0.0"
]
```

## Frappe Integration

### 1. Vite Configuration (vite.config.js)

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import path from 'path'
import frappeui from 'frappe-ui/vite'

export default defineConfig({
  plugins: [
    frappeui({
      frappeProxy: true,           // Enable Frappe proxy for development
      lucideIcons: true,           // Include Lucide icons
      jinjaBootData: true,         // Enable Jinja boot data injection
      buildConfig: {
        indexHtmlPath: '../your_app/www/your_app.html',
        emptyOutDir: true,
        sourcemap: true,
      },
    }),
    vue(),
    vueJsx(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    outDir: '../your_app/public/frontend',
    emptyOutDir: true,
    sourcemap: false,
    minify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue'],
          icons: ['@iconify/vue'],
          primevue: ['primevue/config', 'primevue/button', 'primevue/card']
        }
      }
    },
    chunkSizeWarningLimit: 1000,
  },
  base: '/assets/your_app/frontend/',
})
```

### 2. Frappe Hooks Configuration (hooks.py)

```python
app_name = "your_app"
app_title = "Your App"
app_publisher = "Your Company"
app_description = "Your app description"
app_email = "support@yourcompany.com"
app_license = "mit"

# Add to apps screen
add_to_apps_screen = [
    {
        "name": "your_app",
        "logo": "/assets/your_app/images/logo.png",
        "title": "Your App",
        "route": "/your_app",
        "has_permission": "your_app.api.has_permission"  # Optional permission check
    }
]

# Website route rules for Vue.js frontend
website_route_rules = [
    {"from_route": "/your_app/<path:app_path>", "to_route": "your_app"},
]

# Optional: Include CSS/JS in Frappe desk
# app_include_css = "/assets/your_app/css/your_app.css"
# app_include_js = "/assets/your_app/js/your_app.js"
```

## Authentication System

### 1. Python Context Handler (www/your_app.py)

```python
import frappe
from frappe import _
import json
from datetime import datetime, date

def serialize_for_json(obj):
    """Recursively convert datetime objects to strings for JSON serialization"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat() if obj else None
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj

def get_context(context):
    """Get context for the Vue app"""
    
    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access Your App"), frappe.PermissionError)
    
    # Set basic context
    context.no_cache = 1
    context.show_sidebar = False
    
    # Add boot data for Vue app
    boot = frappe._dict()
    
    # Add user info
    boot.user = frappe.session.user
    user_doc = frappe.get_doc("User", frappe.session.user)
    boot.user_info = serialize_for_json(user_doc.as_dict())
    
    # Add site config
    boot.site_name = frappe.local.site
    boot.csrf_token = frappe.sessions.get_csrf_token()
    
    # Add system settings
    boot.system_settings = serialize_for_json(frappe.get_single("System Settings").as_dict())
    
    # Add app-specific settings
    boot.app_settings = {
        "app_name": "Your App",
        "version": "1.0.0"
    }
    
    # Serialize the entire boot object
    context.boot = serialize_for_json(boot)
    
    return context

@frappe.whitelist(allow_guest=False)
def get_context_for_dev():
    """Get context for development mode"""
    
    boot = frappe._dict()
    
    # Add user info
    boot.user = frappe.session.user
    user_doc = frappe.get_doc("User", frappe.session.user)
    boot.user_info = serialize_for_json(user_doc.as_dict())
    
    # Add site config
    boot.site_name = frappe.local.site
    boot.csrf_token = frappe.sessions.get_csrf_token()
    
    # Add system settings
    boot.system_settings = serialize_for_json(frappe.get_single("System Settings").as_dict())
    
    # Add app-specific settings
    boot.app_settings = {
        "app_name": "Your App",
        "version": "1.0.0"
    }
    
    return serialize_for_json(boot)
```

### 2. HTML Template (www/your_app.html)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/x-icon" href="/assets/your_app/images/logo.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Your App</title>
    
    <!-- Boot Data -->
    <script>
        window.frappe = {
            boot: {{ boot | tojson }}
        };
    </script>
    <!-- Vite will inject the built assets here -->
</head>
<body>
    <div id="app"></div>
</body>
</html>
```

### 3. Vue App Initialization (main.js)

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

// Frappe UI
import { frappeRequest, setConfig } from 'frappe-ui'

// UI Framework (PrimeVue example)
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'

import './index.css'

// Initialize Frappe UI
async function initializeApp() {
  let boot = {}
  
  // Get boot data - either from window (production) or API (development)
  if (window.frappe?.boot) {
    // Production mode - boot data injected by Jinja2
    boot = window.frappe.boot
  } else {
    // Development mode - fetch boot data from API
    try {
      const response = await frappeRequest({
        url: '/api/method/your_app.www.your_app.get_context_for_dev',
        type: 'GET'
      })
      boot = response
    } catch (error) {
      console.error('Failed to get boot data:', error)
      // Fallback for development without backend
      boot = {
        user: 'Administrator',
        csrf_token: 'development-token',
        site_name: 'localhost'
      }
    }
  }
  
  // Configure Frappe UI
  setConfig('resourceFetcher', frappeRequest)
  
  // Store boot data globally
  window.frappe = window.frappe || {}
  window.frappe.boot = boot
  
  // Create and configure Vue app
  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  app.use(router)
  app.use(PrimeVue, {
    theme: {
      preset: Aura,
      options: {
        prefix: 'p',
        darkModeSelector: false,
        cssLayer: {
          name: 'primevue',
          order: 'tailwind-base, primevue, tailwind-utilities'
        }
      }
    }
  })

  app.mount('#app')
}

// Initialize the app
initializeApp().catch(console.error)
```

## Build Configuration

### 1. PostCSS Configuration (postcss.config.js)

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

### 2. Tailwind CSS Configuration (tailwind.config.js)

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        frappe: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        }
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-in-out',
        'slide-in': 'slideIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
```

## Development Workflow

### 1. Development Commands

```bash
# Install dependencies
cd frontend
npm install  # or yarn install

# Start development server
npm run dev  # or yarn dev

# Build for production
npm run build  # or yarn build

# Preview production build
npm run serve  # or yarn serve
```

### 2. Development vs Production

**Development Mode:**
- Vue app runs on Vite dev server (usually port 5173)
- Frappe UI proxy handles API calls to Frappe backend
- Boot data fetched via API call
- Hot module replacement enabled

**Production Mode:**
- Vue app built and served from Frappe's static files
- Boot data injected directly into HTML template
- Optimized and minified assets
- Served through Frappe's web server

## API Integration

### 1. Using Frappe UI Resources

```javascript
// composables/useAPI.js
import { ref, computed } from 'vue'
import { createListResource, createDocumentResource, call } from 'frappe-ui'

export function useAPI() {
  // List resource for fetching multiple documents
  const itemsResource = createListResource({
    doctype: 'Your DocType',
    fields: ['name', 'title', 'status'],
    filters: { status: 'Active' },
    orderBy: 'creation desc',
    auto: true, // Auto-fetch on creation
    cache: ['items'] // Cache key
  })

  // Document resource for single document operations
  const createItem = async (itemData) => {
    const newItem = createDocumentResource({
      doctype: 'Your DocType'
    })

    Object.assign(newItem.doc, itemData)
    await newItem.save()
    
    // Refresh list after creation
    itemsResource.reload()
    
    return newItem.doc
  }

  // Update existing document
  const updateItem = async (itemId, updates) => {
    const item = createDocumentResource({
      doctype: 'Your DocType',
      name: itemId
    })

    await item.get() // Fetch current data
    Object.assign(item.doc, updates) // Apply updates
    await item.save()
    
    return item.doc
  }

  // Delete document
  const deleteItem = async (itemId) => {
    const item = createDocumentResource({
      doctype: 'Your DocType',
      name: itemId
    })

    await item.delete()
    itemsResource.reload() // Refresh list
  }

  // Call server methods
  const callServerMethod = async (methodName, args) => {
    return await call(methodName, args)
  }

  return {
    // Reactive data
    items: computed(() => itemsResource.data || []),
    isLoading: computed(() => itemsResource.loading),
    
    // Methods
    createItem,
    updateItem,
    deleteItem,
    callServerMethod,
    
    // Resources
    itemsResource
  }
}
```

### 2. Using in Components

```vue
<template>
  <div>
    <div v-if="isLoading">Loading...</div>
    <div v-else>
      <div v-for="item in items" :key="item.name">
        {{ item.title }}
        <button @click="updateItem(item.name, { status: 'Inactive' })">
          Deactivate
        </button>
        <button @click="deleteItem(item.name)">Delete</button>
      </div>
    </div>
    
    <button @click="createNewItem">Create Item</button>
  </div>
</template>

<script setup>
import { useAPI } from '@/composables/useAPI'

const { items, isLoading, createItem, updateItem, deleteItem } = useAPI()

const createNewItem = async () => {
  await createItem({
    title: 'New Item',
    status: 'Active'
  })
}
</script>
```

## Styling & UI Components

### 1. CSS Structure (index.css)

```css
@import 'tailwindcss/base';
@import 'tailwindcss/components';
@import 'tailwindcss/utilities';

/* Frappe UI base styles */
@import 'frappe-ui/style.css';

/* Custom app styles */
@layer base {
  html {
    @apply antialiased;
  }
  
  body {
    @apply bg-gray-50 text-gray-900;
  }
}

@layer components {
  .btn-primary {
    @apply bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg transition-colors;
  }
  
  .card {
    @apply bg-white rounded-lg shadow-sm border border-gray-200 p-6;
  }
}
```

### 2. Component Structure

```vue
<!-- components/BaseCard.vue -->
<template>
  <div class="card">
    <div v-if="title" class="card-header mb-4">
      <h3 class="text-lg font-semibold text-gray-900">{{ title }}</h3>
    </div>
    <div class="card-content">
      <slot />
    </div>
    <div v-if="$slots.footer" class="card-footer mt-4 pt-4 border-t border-gray-200">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: String
})
</script>
```

## Deployment

### 1. Build Process

```bash
# Build the frontend
cd frontend
npm run build

# This will:
# 1. Build Vue app to ../your_app/public/frontend/
# 2. Copy index.html to ../your_app/www/your_app.html
# 3. Update asset references in HTML template
```

### 2. Frappe Installation

```bash
# Install the app in Frappe
bench get-app your_app /path/to/your_app
bench install-app your_app

# Or for development
bench get-app your_app --branch develop
```

### 3. Production Considerations

- Enable gzip compression for static assets
- Set appropriate cache headers
- Use CDN for static assets if needed
- Monitor bundle sizes and optimize chunks

## Best Practices

### 1. Project Organization

- **Composables**: Use Vue composables for reusable logic
- **Components**: Create reusable UI components
- **Pages**: Separate page-level components
- **Stores**: Use Pinia for global state management
- **Types**: Add TypeScript for better development experience

### 2. Performance

- **Code Splitting**: Use dynamic imports for route-based code splitting
- **Lazy Loading**: Lazy load components and resources
- **Caching**: Leverage Frappe UI's built-in caching
- **Bundle Analysis**: Regularly analyze bundle sizes

### 3. Security

- **Authentication**: Always check user permissions on server-side
- **CSRF Protection**: Frappe UI handles CSRF tokens automatically
- **Input Validation**: Validate all user inputs
- **API Security**: Use Frappe's permission system

### 4. Development

- **Hot Reload**: Use Vite's HMR for fast development
- **Error Handling**: Implement proper error boundaries
- **Logging**: Use consistent logging patterns
- **Testing**: Write unit and integration tests

### 5. Frappe Integration

- **DocTypes**: Follow Frappe naming conventions
- **Permissions**: Use Frappe's role-based permissions
- **Hooks**: Leverage Frappe hooks for custom logic
- **API**: Use Frappe's whitelisted methods for server communication

## Common Issues & Solutions

### 1. CORS Issues in Development
- Ensure `frappeProxy: true` in Vite config
- Check Frappe site configuration

### 2. Authentication Problems
- Verify boot data is properly injected
- Check CSRF token handling
- Ensure user has proper permissions

### 3. Build Issues
- Check asset paths in production
- Verify HTML template is properly updated
- Ensure all dependencies are installed

### 4. Performance Issues
- Analyze bundle sizes
- Implement proper code splitting
- Use Frappe UI caching effectively

This guide provides a complete foundation for building modern Vue.js applications integrated with Frappe Framework. Follow these patterns and best practices to create maintainable, scalable applications.
