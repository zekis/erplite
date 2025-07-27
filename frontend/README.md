# ERPLite Vue.js Frontend

This is a modern Vue.js frontend for ERPLite built with Vite, Frappe UI, and Tailwind CSS. It demonstrates the proper way to build Vue.js applications within the Frappe framework.

## 🚀 Features

- **Vue.js 3** with Composition API
- **Frappe UI** components for consistent design
- **Tailwind CSS** for utility-first styling
- **Vite** for fast development and building
- **Pinia** for state management
- **Vue Router** for client-side routing

## 📁 Project Structure

```
frontend/
├── src/
│   ├── pages/           # Page components
│   │   ├── Home.vue     # Landing page with demos
│   │   └── Scheduler.vue # Task scheduler example
│   ├── App.vue          # Root component
│   ├── main.js          # Application entry point
│   ├── router.js        # Vue Router configuration
│   └── index.css        # Global styles with Tailwind
├── index.html           # HTML template
├── package.json         # Dependencies and scripts
├── vite.config.js       # Vite configuration
├── tailwind.config.js   # Tailwind CSS configuration
└── postcss.config.js    # PostCSS configuration
```

## 🛠️ Development Setup

### Prerequisites

- Node.js (v16 or higher)
- Yarn or npm
- Frappe development environment

### Installation

1. **Install dependencies:**
   ```bash
   cd frontend
   yarn install
   # or
   npm install
   ```

2. **Start development server:**
   ```bash
   yarn dev
   # or
   npm run dev
   ```

3. **Build for production:**
   ```bash
   yarn build
   # or
   npm run build
   ```

## 🔧 How It Works

### Integration with Frappe

This Vue.js app integrates with Frappe using the `frappe-ui/vite` plugin which provides:

- **Frappe Proxy**: Automatic proxying to Frappe backend during development
- **Jinja Boot Data**: Access to server-side data in Vue components
- **Lucide Icons**: Icon library integration
- **Build Configuration**: Automatic building and deployment to Frappe

### Build Process

1. **Development**: `yarn dev` starts Vite dev server with hot reload
2. **Build**: `yarn build` creates optimized production build
3. **Deploy**: Built files are automatically copied to Frappe's public folder
4. **Access**: App is accessible at `/app` route in Frappe

### API Integration

The Vue app communicates with Frappe backend through:

- **REST API**: Standard Frappe API endpoints
- **Authentication**: Automatic session handling
- **Error Handling**: Consistent error responses

Example API call:
```javascript
const response = await fetch('/api/method/erplite.vue_test.api.get_tasks')
const data = await response.json()
```

## 📱 Pages

### Home Page (`/`)
- Welcome screen with feature overview
- Interactive demos showing Vue.js capabilities
- API integration examples
- Comparison with pure JavaScript approach

### Scheduler Page (`/scheduler`)
- Task management interface
- Reactive state management demo
- CRUD operations with backend
- Statistics dashboard

## 🎨 Styling

### Tailwind CSS
- Utility-first CSS framework
- Responsive design out of the box
- Custom color palette for Frappe integration
- Component-based styling

### Frappe UI Components
- Consistent design language
- Pre-built components (Button, Input, etc.)
- Automatic theming
- Accessibility features

## 🔄 Comparison with Pure JavaScript

### Vue.js Advantages:
- **Reactive State**: Automatic UI updates when data changes
- **Component Architecture**: Reusable, modular components
- **Declarative Templates**: Describe what you want, not how to build it
- **Built-in Routing**: Client-side navigation
- **State Management**: Predictable data flow with Pinia
- **Developer Tools**: Vue DevTools for debugging
- **Hot Reload**: Instant feedback during development
- **TypeScript Support**: Optional type safety

### Pure JavaScript Challenges:
- **Manual DOM Manipulation**: Verbose and error-prone
- **State Synchronization**: Complex to keep UI and data in sync
- **Event Management**: Manual listener setup and cleanup
- **No Component Reusability**: Code duplication
- **Difficult Debugging**: Limited tooling
- **Hard to Maintain**: Complex codebases become unwieldy

## 🚀 Production Deployment

### Build Process
```bash
# Build the Vue app
yarn build

# This automatically:
# 1. Creates optimized production build
# 2. Copies files to ../erplite/public/frontend/
# 3. Creates ../erplite/www/app.html entry point
```

### Access Points
- **Development**: `http://localhost:3000` (Vite dev server)
- **Production**: `https://your-site.com/app` (Frappe integration)

## 🔧 Configuration

### Vite Configuration (`vite.config.js`)
- Frappe UI plugin setup
- Build output configuration
- Development proxy settings
- Asset optimization

### Router Configuration (`router.js`)
- Client-side routing setup
- Base path configuration for Frappe integration
- Route definitions

### Tailwind Configuration (`tailwind.config.js`)
- Content paths for purging unused CSS
- Custom color palette
- Responsive breakpoints

## 📚 Resources

- [Vue.js Documentation](https://vuejs.org/)
- [Frappe UI Documentation](https://github.com/frappe/frappe-ui)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [Frappe Framework Documentation](https://frappeframework.com/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
