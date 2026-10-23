# React frontend verification — 2026-10-22

React + TypeScript + Vite frontend in `frontend/`; Java and Python contracts unchanged. All npm dependency versions and the lockfile are pinned. No remote font, image or paid service dependency.

## Automated evidence

- API tests: 17 initially failed against the unimplemented client, then passed.
- Page tests: 10 initially failed against the empty component, then passed.
- Total frontend: 27 passing tests. Strict TypeScript checks and Vite production build pass.
- Java Maven verify: 99 passing tests, zero failures/errors/skips, JDK 21.
- Python: use the existing macOS launcher to select the compatible native OpenMP runtime. A direct pytest invocation bypassing it aborted; launcher-based verification passed: 75 tests in 6.75 seconds.

Frontend tests cover request payload, order and score preservation, both popularity reasons, null scores, malformed response handling, 400/503/500, network error, ten-second abort, Unicode user ID limits, keyboard submit, concurrent submission prevention, stale-result removal, failure/retry, empty results and HTML-like names rendered as text.

## Browser integration evidence

In-app browser → Vite 5173 → Java 8080 → Python 8000, real local `retrieval-bundle-v001`:

- User `1`: personalized Top 10, beginning ninja, tfue, esl_csgo; all ten names and order match the earlier Postman result. Expanded first match details shows 21.490 (display rounding).
- User `new-user`: popular Top 10, unknown-user explanation, no score details. Begins ninja, tfue, shroud, riotgames.
- Stop only the agent-started Python process: Java 503 becomes a readable unavailable message; previous cards removed.
- Restart Python and retry without restarting Java/React: personalized Top 10 returns.
- Browser layout inspected at the available desktop/tablet-width viewport. Narrow mobile devices and other browser engines are not separately verified.

No production deployment, online-quality measurement, or throughput claim. Build output requires production routing configuration before deployment. Existing developer IDE files are excluded.

## Independent review

One fresh reviewer examined 767bc2f..c453e72 and independently reran all 27 frontend tests and the production build. No Critical/Important findings.

Deferred minor: frontend response validation coerces fallback_reason using String(), so an array such as ["unknown_user"] could pass that check and omit the UI explanation. The current Java client rejects that malformed response before it reaches the frontend; tighten this defensive check in a follow-up.

Scope decisions confirmed: empty-result handling is intentionally defensive although Java currently rejects empty lists; production routing remains future work; native browser fetch honors AbortSignal during request/body consumption. An artificial mock ignoring AbortSignal does not establish a production timeout defect. Screen-reader and narrow-mobile testing remain unverified.
