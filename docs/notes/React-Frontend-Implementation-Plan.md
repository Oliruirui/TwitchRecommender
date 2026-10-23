# React Frontend Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Browse Top 10 recommendations through the existing Java endpoint.

**Architecture:** Vite serves React on localhost:5173 and proxies /api to localhost:8080. Java retains ownership of calls to Python; frontend contains no credentials.

**Tech Stack:** React, TypeScript, Vite, CSS, Vitest, Testing Library.

**Spec:** React-Frontend-Design.md (same directory).

## Global Constraints

- Local and free; no backend contract changes or paid services.
- Fixed k=10, user ID trimmed to 1–128 Unicode code points.
- Preserve server response order and distinguish null scores from zero.
- Keep existing Java homepage and user IDE edits intact.
- Native execution with one final independent review, following the established project workflow.

## Review Focus

- Rapid submissions: only one active request; submit disabled while loading.
- Previous results: clear on resubmit and failure rather than display stale recommendations.
- Unavailable or hung server: readable error, ten-second timeout, form usable afterward.
- Untrusted or malformed response: validate shape; render names as text.
- Empty results and unknown-user fallback: explicit status, no fake score or live metadata.

## Task 1: Typed API client and development setup

Files: frontend/package.json, package-lock.json, index.html, tsconfig*.json, vite.config.ts, src/api.ts, src/api.test.ts, .gitignore.

Interface: fetchRecommendations(userId: string): Promise<RecommendationResponse>; POST /api/recommendations with JSON {user_id: userId, k:10}. Response fields match the current Java/Python contract.

- [x] Add React/TypeScript/Vite setup, /api proxy and test runner; ignore node_modules, dist and local env files.
- [x] Write failing client tests for exact request, personalized/popular parsing, 400/503, malformed response, network failure and timeout.
- [x] Run npm test; confirm failures are missing implementation rather than tooling failures.
- [x] Implement API client with AbortController deadline and response validation.
- [x] Run client tests and npm run build; expect all passing.

## Task 2: Recommendation page

Files: frontend/src/main.tsx, App.tsx, App.css, App.test.tsx, test setup.

Interface: App consumes fetchRecommendations and displays response items in supplied order.

- [x] Write failing component tests for keyboard submit, trim/Unicode validation, loading/repeated submissions, ordered results, popular/null scores, empty state, errors clearing old results, retry, and HTML-like channel names rendered as text.
- [x] Run tests and confirm expected missing-page behavior.
- [x] Implement accessible form, responsive cards, status and error messages with plain CSS.
- [x] Run full frontend tests and production build; expect all passing.

## Task 3: Integration evidence and delivery

Files: frontend/README.md, docs/README.md, docs/notes/React-Frontend-Results.md.

- [x] Document npm ci, npm run dev, npm test and npm run build; explain three local processes and historical user IDs.
- [x] Verify known user, unknown-user fallback and Python outage/recovery in browser when services are available; report any untested scenario explicitly. Validate invalid input in component tests because UI fixes k=10.
- [ ] Run final tests/build and one independent review; fix material findings with focused regression checks.
- [ ] Commit only task files, push one feature branch and create one PR with actual test evidence. Attach PR to this chat; do not merge.
