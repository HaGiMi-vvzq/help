# Hackathon Frontend Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the demo-facing frontend so the product looks cohesive, modern, and route-demo ready without destabilizing the existing agent and matching flows.

**Architecture:** Keep the current Vue 3 + Element Plus structure, but tighten the visual system from the top down: global tokens first, then layout shell, then the three core presentation surfaces (`AgentView`, `NeedPlazaView`, `MatchResultView`). Preserve existing stores and backend contracts. Use route-level lazy loading and component-level code splitting to reduce bundle pressure without altering behavior.

**Tech Stack:** Vue 3, Vue Router, Pinia, Element Plus, Vite, TypeScript, scoped CSS, existing backend API contracts

---

## File Structure

- Modify: `frontend/src/styles/global.css`
  - Own the design tokens, shell-level utility classes, and shared visual language.
- Modify: `frontend/src/components/layout/AppLayout.vue`
  - Own the navigation shell, page chrome, topbar, status affordances, and overall SaaS feel.
- Modify: `frontend/src/views/AgentView.vue`
  - Own the AI workbench presentation: session rail, message workspace, suggestions, knowledge, memory, and task status presentation.
- Modify: `frontend/src/views/NeedPlazaView.vue`
  - Own the marketplace landing experience, page overview, filters, and card density.
- Modify: `frontend/src/views/MatchResultView.vue`
  - Own result credibility, comparison readability, candidate prioritization, and contact affordances.
- Modify: `frontend/src/router/index.ts`
  - Own route-level code splitting and lazy-load structure.
- Verify: `backend/tests/test_project_contracts.py`
  - Ensure promised frontend capabilities remain represented in contracts.

## Task 1: Rebuild the global visual system and shell

**Files:**
- Modify: `frontend/src/styles/global.css`
- Modify: `frontend/src/components/layout/AppLayout.vue`
- Test: `frontend/src/router/index.ts`

- [ ] **Step 1: Write the failing expectation by recording the intended shell changes in the contract surface**

Expected shell changes to preserve while implementing:

```text
- Global tokens include a clearer surface hierarchy and a dark-accent shell language
- AppLayout exposes stronger brand area, topbar status area, and page context
- Router continues to lazy-load all views
```

- [ ] **Step 2: Inspect the current shell and route boundaries**

Run:

```powershell
Get-Content frontend/src/components/layout/AppLayout.vue
Get-Content frontend/src/styles/global.css
Get-Content frontend/src/router/index.ts
```

Expected: current shell is functional but visually thin; router already lazy-loads views and can be preserved.

- [ ] **Step 3: Implement the new token layer and shell structure**

Key implementation points:

```vue
<!-- AppLayout.vue -->
<div class="app-shell">
  <aside class="shell-sidebar">...</aside>
  <main class="shell-main">
    <header class="shell-topbar">...</header>
    <section class="shell-content">...</section>
  </main>
</div>
```

```css
/* global.css */
:root {
  --bg-app: #eef3f8;
  --bg-panel: #ffffff;
  --bg-panel-alt: #f7f9fc;
  --bg-accent-strong: #0f172a;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --border-soft: #dbe4ee;
}
```

- [ ] **Step 4: Keep route loading stable**

Implementation rule:

```ts
// router/index.ts
component: () => import('@/views/AgentView.vue')
```

Expected: no route should be converted to eager import.

- [ ] **Step 5: Run the frontend build**

Run:

```powershell
cmd /c npm run build
```

Expected: PASS

## Task 2: Turn AgentView into a real AI workbench

**Files:**
- Modify: `frontend/src/views/AgentView.vue`
- Test: `backend/tests/test_project_contracts.py`

- [ ] **Step 1: Preserve the existing behavior checkpoints before changing layout**

Behavior that must remain intact:

```text
- session switching
- send message
- upload file
- publish drafts
- refresh tasks
- knowledge search
- memory reset
```

- [ ] **Step 2: Inspect the current agent surface**

Run:

```powershell
Get-Content frontend/src/views/AgentView.vue
```

Expected: three-column structure exists, but the workbench hierarchy is weak.

- [ ] **Step 3: Implement the upgraded workbench layout**

Key implementation points:

```vue
<section class="agent-hero">...</section>
<section class="agent-stream">...</section>
<aside class="agent-insights">...</aside>
```

```css
.agent-hero {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
}

.message-result-card,
.task-summary-card,
.workspace-panel {
  border: 1px solid var(--border-soft);
  background: var(--bg-panel);
}
```

- [ ] **Step 4: Preserve contract markers and interaction affordances**

Required markers that must remain visible in source:

```text
主动建议
知识搜索
文件库
记忆摘要
task-error-block
task-type-tag
```

- [ ] **Step 5: Run focused regression checks**

Run:

```powershell
conda run -n ark python -m unittest tests.test_project_contracts
cmd /c npm run build
```

Expected: PASS

## Task 3: Rebuild NeedPlazaView as a convincing product homepage

**Files:**
- Modify: `frontend/src/views/NeedPlazaView.vue`
- Modify: `frontend/src/styles/global.css`

- [ ] **Step 1: Preserve the marketplace requirements**

Required behavior:

```text
- filter by type
- list cards from store.needs
- navigate to match results
- keep publish action prominent
```

- [ ] **Step 2: Inspect the current plaza layout**

Run:

```powershell
Get-Content frontend/src/views/NeedPlazaView.vue
```

Expected: current page has cards and filters but lacks a strong overview band and product-level framing.

- [ ] **Step 3: Implement overview band, denser filter bar, and stronger card hierarchy**

Key implementation points:

```vue
<section class="plaza-hero">...</section>
<section class="plaza-toolbar">...</section>
<section class="plaza-grid">...</section>
```

```css
.plaza-hero {
  display: grid;
  grid-template-columns: 1.3fr 0.7fr;
}

.need-card-meta,
.need-card-tags,
.need-card-cta {
  display: flex;
}
```

- [ ] **Step 4: Use existing list data for lightweight stats only**

Allowed lightweight computation:

```ts
const openCount = computed(() => store.needs.filter((item) => item.status === '开放').length)
```

Expected: no new API needed.

- [ ] **Step 5: Run the frontend build**

Run:

```powershell
cmd /c npm run build
```

Expected: PASS

## Task 4: Tighten MatchResultView into a decision surface

**Files:**
- Modify: `frontend/src/views/MatchResultView.vue`
- Test: `backend/tests/test_project_contracts.py`

- [ ] **Step 1: Preserve existing matching behaviors**

Required behavior:

```text
- comparison-table marker remains
- draft message remains keyed by user_id
- select / deselect still works
- contact and draft-message actions still work
```

- [ ] **Step 2: Inspect the current result page**

Run:

```powershell
Get-Content frontend/src/views/MatchResultView.vue
```

Expected: the logic is already rich; visual grouping and summary can be improved.

- [ ] **Step 3: Implement a stronger overview and card hierarchy**

Key implementation points:

```vue
<section class="result-hero">...</section>
<section class="comparison-table">...</section>
<section class="candidate-grid">...</section>
```

```css
.result-hero,
.comparison-section,
.candidate-card {
  border: 1px solid var(--border-soft);
  background: var(--bg-panel);
}
```

- [ ] **Step 4: Keep the message drafting logic stable**

Required source shape:

```ts
draftMessages.value[match.user_id] = data.message
```

Expected: no regression to username-based keys.

- [ ] **Step 5: Run combined verification**

Run:

```powershell
conda run -n ark python -m unittest tests.test_project_contracts tests.test_agent_smoke
cmd /c npm run build
```

Expected: PASS

## Task 5: Final regression and polish pass

**Files:**
- Modify: `frontend/src/components/layout/AppLayout.vue`
- Modify: `frontend/src/views/AgentView.vue`
- Modify: `frontend/src/views/NeedPlazaView.vue`
- Modify: `frontend/src/views/MatchResultView.vue`
- Modify: `frontend/src/styles/global.css`

- [ ] **Step 1: Inspect for layout regressions**

Checklist:

```text
- no text overlap
- no unstable button widths
- no nested decorative cards
- no broken mobile drawer behavior
- no lost route navigation
```

- [ ] **Step 2: Apply only minimal polish fixes**

Allowed fixes:

```text
- spacing
- font hierarchy
- border contrast
- card padding
- button grouping
```

- [ ] **Step 3: Run final verification**

Run:

```powershell
conda run -n ark python -m unittest tests.test_project_contracts tests.test_agent_smoke
conda run -n ark python -m compileall app tests
cmd /c npm run build
```

Expected: all PASS; build warnings may remain non-blocking if unchanged from baseline.
