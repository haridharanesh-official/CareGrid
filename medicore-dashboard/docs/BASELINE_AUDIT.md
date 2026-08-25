# Pre-refactor Baseline Audit

Recorded before the CareGrid refactor on 24 August 2026.

## Existing structure

- React 19 + Vite 6 single-page prototype.
- `src/App.jsx` contains the complete application, all page markup, demo data, hash navigation, global action handling, Inventory local state, and modals.
- `src/styles.css` contains the complete visual system in a mostly monolithic stylesheet.
- No router, role/auth provider, API services, sensor adapter, polling hooks, or feature modules.
- No project-level frontend tests; only the bundled Sites worker/package test exists.

## Working features before refactor

- Polished MediCore blue/white desktop dashboard visual system with responsive sidebar/card behavior.
- Hash navigation for Dashboard, Patient Management, Appointments, Billing, Inventory, and generic fallback destinations.
- Inventory search, status filter, alphabetical sort, pagination, selection, local medicine creation, row details, automation toggle, and CSV preparation.
- Dashboard quick-link navigation and top-bar search redirect.
- Generic confirmation modal/toast behavior for otherwise inert controls.
- Static Patient, Appointments, Billing, Dashboard, and Inventory views.
- Vite development preview, Sites-ready production build, and Sites worker fallback.

## Baseline verification

- `npm run build`: passed.
- `npm run test:sites`: 4 passed, 0 failed.
- Git: no repository is initialized in `D:\CareGrid\medicore-dashboard`, so logical commits cannot be created until Git is available.

## Known issues accepted for refactor

- MediCore branding and irrelevant ERP content.
- Monolithic React and CSS architecture.
- Manual hash routing and no route guards.
- Generic placeholder pages and global fake action modal.
- Hardcoded data and duplicated portrait asset.
- No live CareGrid gateway integration, sensor validity model, RFID, ambulance, medication, bed, alert, or clinical workflow architecture.
