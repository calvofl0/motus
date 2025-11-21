# Week 3 - Core Modules Extraction Plan

## Current Status
- **Lines in index.html**: 4,433 (down from 5,394 original)
- **Reduction so far**: 961 lines (~18%)
- **Week 2 foundation modules**: ✓ Complete and refined

## Week 3 Goals
Extract self-contained, modal-based modules with clear boundaries. Leave complex file browser for later weeks.

**Target**: Reduce index.html to ~3,200 lines (~1,200 line reduction)

---

## Module Extraction Order

### 1. Remote Manager Module (~600 lines)
**File**: `frontend/js/modules/remote-manager.js`

**Scope**:
- Manage rclone remote configurations
- CRUD operations for remotes
- Template-based remote creation
- Modal UI management

**Key Functions**:
```
- openRemoteManager()
- loadRemotes()
- loadTemplates()
- selectTemplate()
- addRemote()
- editRemote()
- deleteRemote()
- renderRemoteList()
- renderTemplateForm()
```

**Dependencies**:
- apiCall (from js/lib/api.js)
- state.remoteManagement (from js/config.js)
- ModalManager (from js/lib/modal-manager.js)

**Export Strategy**:
```javascript
export class RemoteManager {
    constructor(apiCall, stateRef, modalManager) { ... }
    async loadRemotes() { ... }
    async loadTemplates() { ... }
    async addRemote(config) { ... }
    async editRemote(name, config) { ... }
    async deleteRemote(name) { ... }
    // ... etc
}
```

**Integration**:
```javascript
// In index.html:
import { RemoteManager } from '/js/modules/remote-manager.js';
const remoteManager = new RemoteManager(apiCall, state.remoteManagement, ModalManager);
```

---

### 2. OAuth Manager Module (~200 lines)
**File**: `frontend/js/modules/oauth-manager.js`

**Scope**:
- OAuth token authorization flow
- Token refresh handling
- Interactive OAuth modal

**Key Functions**:
```
- authorizeOAuth()
- refreshOAuthToken()
- pollOAuthStatus()
- handleOAuthCallback()
- showInteractiveOAuthModal()
```

**Dependencies**:
- apiCall (from js/lib/api.js)
- state.oauth (from js/config.js)
- ModalManager (from js/lib/modal-manager.js)

**Export Strategy**:
```javascript
export class OAuthManager {
    constructor(apiCall, stateRef, modalManager) { ... }
    async authorizeOAuth(remoteName) { ... }
    async refreshToken(remoteName) { ... }
    async pollStatus(remoteName) { ... }
    // ... etc
}
```

---

### 3. Upload Manager Module (~400 lines)
**File**: `frontend/js/modules/upload-manager.js`

**Scope**:
- File upload via drag-drop
- Progress tracking
- Upload cancellation
- Size limit checking
- Multi-file and folder upload

**Key Functions**:
```
- uploadFiles()
- handleExternalDrop()
- traverseFileTree()
- checkUploadSizeLimit()
- showUploadProgress()
- updateUploadProgress()
- cancelUpload()
```

**Dependencies**:
- apiCall (from js/lib/api.js)
- state.upload (from js/config.js)
- getAuthToken (from js/lib/api.js)

**Export Strategy**:
```javascript
export class UploadManager {
    constructor(apiCall, stateRef, getTokenFn) { ... }
    async uploadFiles(files, destPath, hasDirectories) { ... }
    checkSizeLimit(files) { ... }
    cancel() { ... }
    // ... etc
}
```

---

### 4. Job Manager Module (~500 lines)
**File**: `frontend/js/modules/job-manager.js`

**Scope**:
- Active jobs tracking and display
- Interrupted jobs management
- Failed jobs management
- Job progress updates
- Auto-refresh on completion

**Key Functions**:
```
- startJobUpdates()
- updateJobs()
- renderJobs()
- cancelJob()
- updateInterruptedJobs()
- renderInterruptedJobs()
- updateFailedJobs()
- renderFailedJobs()
- clearStoppedJobs()
- toggleJobPanel()
```

**Dependencies**:
- apiCall (from js/lib/api.js)
- state.jobs (from js/config.js)
- refreshPane callback (from main code)

**Export Strategy**:
```javascript
export class JobManager {
    constructor(apiCall, stateRef, refreshPaneCallback) { ... }
    startUpdates() { ... }
    stopUpdates() { ... }
    async updateActive() { ... }
    async updateInterrupted() { ... }
    async updateFailed() { ... }
    async cancel(jobId) { ... }
    async clearStopped() { ... }
    // ... etc
}
```

**Special Considerations**:
- Needs callback to refreshPane for auto-refresh on job completion
- Manages multiple update intervals
- Complex rendering logic with progress parsing

---

## What's NOT Being Extracted (Yet)

### File Browser (~1000+ lines) - Deferred to Week 4/5
**Reason**: Too complex, tightly coupled with many UI interactions

**Components**:
- File rendering (grid/list views)
- Navigation (up, into, browse path)
- Selection handling (click, shift-click, ctrl-click)
- Drag-drop between panes
- Context menu
- Column resizing
- Sorting

**Strategy for Later**:
- Extract in smaller pieces
- Create helper functions first
- Extract rendering separately from interaction
- Consider keeping some in main file for simplicity

### Expert Mode (~300 lines) - Deferred to Week 4
**Reason**: Less frequently used, can wait

---

## Implementation Steps

### For Each Module:

1. **Identify all functions** that belong to the module
2. **Map dependencies** - what external functions/state does it need?
3. **Create class-based module** with constructor for dependencies
4. **Export public methods**
5. **Update index.html**:
   - Import the new module
   - Instantiate the class
   - Replace function calls with method calls
6. **Test thoroughly**
7. **Commit and push**

### Testing Checklist:
- [ ] Modal opens/closes correctly
- [ ] API calls work (check network tab)
- [ ] State updates correctly
- [ ] UI updates correctly
- [ ] Error handling works
- [ ] No console errors

---

## Expected Results

### After Week 3:
- **4 new modules** created
- **~1,200 lines** removed from index.html
- **index.html**: ~3,200 lines
- **Total reduction**: ~40% from original

### Module Organization:
```
frontend/js/
├── lib/
│   ├── api.js              ✓ Week 2
│   ├── sse.js              ✓ Week 2
│   └── modal-manager.js    ✓ Pre-existing
├── utils/
│   ├── helpers.js          ✓ Week 2
│   └── preferences.js      ✓ Week 2
├── modules/
│   ├── remote-manager.js   → Week 3
│   ├── oauth-manager.js    → Week 3
│   ├── upload-manager.js   → Week 3
│   └── job-manager.js      → Week 3
└── config.js               ✓ Week 2
```

---

## Next Steps

1. Start with **Remote Manager** (most self-contained)
2. Then **OAuth Manager** (small, clear boundaries)
3. Then **Upload Manager** (medium complexity)
4. Finally **Job Manager** (most complex of the four)

Each module should be fully tested before moving to the next.

---

## Notes

- All modules should be class-based for consistency
- Use dependency injection (pass dependencies to constructor)
- Keep modules focused and single-purpose
- Document all public methods with JSDoc
- Maintain backward compatibility during transition
