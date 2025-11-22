# Motus Frontend - Vue.js Migration

This is the Vue.js migration of the Motus frontend. The goal is to create a more maintainable and scalable codebase with better developer experience.

## 🎯 Migration Status

### ✅ Completed
- [x] Vite + Vue 3 setup
- [x] Vue Router configuration (Easy/Expert mode routing)
- [x] Pinia store for state management
- [x] Base components (AppHeader, FilePane, JobPanel)
- [x] Placeholder views (EasyMode, ExpertMode)
- [x] API and services layer
- [x] CSS migration

### 🚧 In Progress
- [ ] FileBrowser component (full file list, grid/list views, selection)
- [ ] Modal components (all 10 modals)
- [ ] FileOperations composable
- [ ] Job management integration
- [ ] Upload functionality

### 📋 Planned
- [ ] Remote configuration wizard (new feature!)
- [ ] OAuth flow components
- [ ] Full feature parity with vanilla version
- [ ] Testing

## 🚀 Getting Started

### Prerequisites
- Node.js 18+ (LTS recommended)
- npm or yarn

### Installation

```bash
cd frontend-vue
npm install
```

### Development

```bash
# Start dev server (with hot reload)
npm run dev
```

The app will be available at `http://localhost:3000`. The backend API calls are proxied to `http://localhost:8080` (make sure your Motus backend is running).

### Build for Production

```bash
npm run build
```

This will create an optimized build in `../frontend-dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## 📁 Project Structure

```
frontend-vue/
├── src/
│   ├── assets/          # Static assets, styles
│   ├── components/      # Vue components
│   │   ├── AppHeader.vue
│   │   ├── FilePane.vue
│   │   └── JobPanel.vue
│   ├── views/           # Page views
│   │   ├── EasyMode.vue
│   │   └── ExpertMode.vue
│   ├── stores/          # Pinia stores
│   │   └── app.js       # Main app store
│   ├── services/        # API, utilities
│   │   ├── api.js
│   │   └── preferences.js
│   ├── composables/     # Vue composables (to be added)
│   ├── router/          # Vue Router config
│   │   └── index.js
│   ├── App.vue          # Root component
│   └── main.js          # App entry point
├── public/              # Static files (CSS, images)
├── index.html           # HTML entry point
├── vite.config.js       # Vite configuration
└── package.json         # Dependencies
```

## 🔧 Architecture Decisions

### State Management (Pinia)
We use Pinia for centralized state management. The main store (`stores/app.js`) contains:
- App-level state (mode, auth, preferences)
- Left/right pane state (files, selection, path)
- Context menu state

### Routing (Vue Router)
- `/` → Easy Mode (dual-pane file browser)
- `/expert` → Expert Mode (advanced rclone operations)

### Component Strategy
- **Components**: Reusable UI elements (FilePane, JobPanel, modals)
- **Views**: Page-level components (EasyMode, ExpertMode)
- **Composables**: Shared logic (file operations, API calls)

### API Layer
The `services/api.js` provides:
- Token-based authentication
- Centralized error handling
- Type-safe API calls

## 🎨 Styling
- Existing CSS files are reused from the vanilla version
- Component-specific styles use Vue's scoped CSS
- Global styles imported in `main.js`

## 🔮 Next Steps

1. **Convert FileBrowser**: Full file grid/list rendering with selection
2. **Modal System**: Convert all 10 modals to Vue components
3. **Job Management**: Real-time job updates with SSE
4. **Upload Manager**: Drag-drop upload with progress
5. **Wizard Implementation**: New remote configuration wizard

## 📝 Migration Notes

### From Vanilla JS to Vue

**Before (Vanilla):**
```javascript
function renderFiles(pane) {
  const container = document.getElementById(`${pane}-files`);
  container.innerHTML = files.map(f => `
    <div class="file-item">${f.Name}</div>
  `).join('');
}
```

**After (Vue):**
```vue
<template>
  <div class="file-item" v-for="file in files" :key="file.Name">
    {{ file.Name }}
  </div>
</template>
```

Benefits:
- ✅ Reactive updates (no manual DOM manipulation)
- ✅ Better performance (virtual DOM diffing)
- ✅ Cleaner, more maintainable code
- ✅ TypeScript support (optional)

## 🐛 Known Issues

- File browser not yet implemented (placeholder shown)
- Job panel shows placeholder
- Modals not yet migrated
- OAuth flow needs reimplementation

## 🤝 Contributing

When adding new features:
1. Create components in `src/components/`
2. Add state to appropriate store
3. Use composables for shared logic
4. Follow Vue 3 Composition API patterns

## 📚 Resources

- [Vue 3 Documentation](https://vuejs.org/)
- [Vite Documentation](https://vitejs.dev/)
- [Pinia Documentation](https://pinia.vuejs.org/)
- [Vue Router Documentation](https://router.vuejs.org/)
