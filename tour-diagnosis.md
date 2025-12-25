# Guided Tour Issues - Diagnosis

## Issue 1: X Button Not Working (Click Does Nothing)

**Root Cause:** When the custom X button is clicked, it calls `showCancelConfirmation(noTourConfig, driverObj)` which hides the driver popover by setting `display: 'none'`. However, the driver overlay (`.driver-overlay`) remains visible with pointer-events enabled, blocking all interaction with the confirmation dialog.

**Evidence:**
- `showCancelConfirmation()` sets `.driver-popover` and `.driver-overlay` to `display: 'none'`
- But the driver overlay has high z-index and blocks pointer events
- The confirmation dialog has z-index 100000, but the overlay might still block it

**Additional Problem:** The driver.js library manages its own overlay and popover lifecycle. When we manually hide them with `display: 'none'`, we're fighting against the library's internal state management.

## Issue 2: ESC Key Shows Dialog But No Interaction Possible

**Root Cause:** Same as Issue 1 - the driver overlay blocks interaction with the confirmation dialog.

**Evidence:**
- Global ESC handler calls `showCancelConfirmation(noTourConfig, driverObj)`
- Same display hiding logic as the X button
- Driver overlay remains active and blocks interaction

## Issue 3: Step 15 Missing Finish Button

**Root Cause:** Incorrect `showButtons` configuration. Step 15 has `showButtons: ['previous', 'close']` but there is no 'close' button type in driver.js v1.3.1.

**Evidence from TypeScript definitions:**
```typescript
export type AllowedButtons = "next" | "previous" | "close";
```

However, the 'close' button is the X button in the corner (which we disabled with `allowClose: false`). The `doneBtnText` property changes the text of the **'next'** button on the last step, not a separate 'close' or 'done' button.

**Correct Configuration:** Should be `showButtons: ['previous', 'next']` and `doneBtnText: 'Finish'` will make the next button display as "Finish".

## Issue 4: Checkbox Doesn't Save Preference

**Root Cause:** The checkbox in Step 15's `onPopoverRender` creates an element with id `tour-no-show-again`, but the `onCloseClick` handler tries to read it. However, if the user uses the built-in close button (which doesn't exist due to wrong showButtons config), the checkbox value isn't being read.

**Secondary Issue:** Since the Finish button doesn't exist (see Issue 3), the `onCloseClick` handler never fires when clicking a button.

## Issue 5: Step 10 Not Highlighting Both Elements

**Root Cause:** Driver.js doesn't support multi-element highlighting with comma-separated selectors. The selector `.view-dropdown-container .view-menu-item:nth-child(3), .left-pane .toolbar-row.with-icon` will only highlight the first matching element.

**Evidence:**
- CSS selectors with commas match multiple elements
- But driver.js's `element` property expects a single element
- It will only highlight the first match in the DOM

**Current Elements in DOM:**
1. `.view-dropdown-container .view-menu-item:nth-child(3)` - the toggle in the View menu
2. `.left-pane .toolbar-row.with-icon` - matches TWO elements:
   - First: Remote dropdown toolbar row
   - Second: Path input toolbar row

**What We Need:** Highlight both the View menu toggle AND the path toolbar (second `.toolbar-row.with-icon`).

**Possible Solutions:**
1. Use `:nth-child(2)` or similar to target only the second toolbar-row
2. Wrap the elements we want to highlight in a common parent
3. Use driver.js's programmatic API to highlight multiple elements sequentially

## Issue 6: Step 12 Not Showing/Highlighting Both Dropdowns

**Root Cause 1:** Wrong class names. The code uses `.interrupted-jobs-container` and `.failed-jobs-container`, but the actual classes are:
- `.interrupted-jobs-dropdown`
- `.failed-jobs-dropdown`

**Evidence from JobPanel.vue:**
```vue
<div class="interrupted-jobs-dropdown">...</div>
<div class="failed-jobs-dropdown">...</div>
```

**Root Cause 2:** Same multi-element issue as Step 10. Even with correct class names, the selector `.interrupted-jobs-dropdown, .failed-jobs-dropdown` would only highlight the first element.

**Root Cause 3:** The `onHighlightStarted` handler tries to make elements visible, but:
1. It's using wrong class names (querySelector returns null)
2. Even if class names were correct, driver.js only highlights one element
3. The elements are hidden with `v-if` in Vue, not CSS display, so changing `style.display` won't help

**Evidence from JobPanel.vue:**
```vue
<div
  v-if="interruptedJobs.length > 0"
  class="interrupted-jobs-dropdown"
>
```
The `v-if` means the element doesn't exist in DOM when there are no interrupted jobs. Setting `style.display = 'block'` won't create the element.

## Summary of Fixes Needed

1. **X Button & ESC Dialog:** Need a different approach to show confirmation dialog. Instead of hiding driver popover, we should:
   - Increase confirmation dialog z-index to be above driver overlay
   - Disable pointer-events on driver overlay temporarily
   - Or use driver.js's built-in close mechanism

2. **Step 15 Finish Button:** Change `showButtons: ['previous', 'close']` to `showButtons: ['previous', 'next']`

3. **Checkbox Saving:** Ensure the checkbox is read when clicking the Finish button (which will now exist)

4. **Step 10 Multi-Element:** Can't use comma-separated selector. Need to either:
   - Target a common parent element
   - Use `.left-pane .toolbar-row.with-icon:nth-child(2)` to get only the path toolbar
   - Split into two sequential steps

5. **Step 12 Class Names:** Fix `.interrupted-jobs-container` → `.interrupted-jobs-dropdown` and `.failed-jobs-container` → `.failed-jobs-dropdown`

6. **Step 12 Multi-Element:** Same issue as Step 10. Also need to handle `v-if` rendering (elements might not exist in DOM).

7. **Step 12 Temporary Visibility:** Can't change CSS display when element is controlled by `v-if`. Need different approach:
   - Temporarily add fake data to make dropdowns render
   - Or accept that these dropdowns only show when there are actually interrupted/failed jobs
   - Or create fake visual representations in the tour step description (like Steps 7-8)
