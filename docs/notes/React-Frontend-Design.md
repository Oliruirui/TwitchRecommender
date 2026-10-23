# React recommendation frontend

Approved in chat on 2026-10-22: React + TypeScript, Vite, separate frontend/ folder, local development on port 5173 with /api proxied to Java on 8080; Java calls Python on 8000.

Goal: inspect recommendations in a browser instead of Postman, using historical dataset user IDs. No paid services or changes to backend contracts.

The page accepts a trimmed user ID (1–128 Unicode code points), requests a fixed k=10 via POST /api/recommendations, and displays the returned channel order and names. Show personalized or popularity-fallback status, including a readable fallback reason. Scores are optional technical details; null scores are never shown as zero. Dataset channel IDs are not assumed to be current Twitch IDs. Do not fabricate thumbnails or live status.

Use accessible labels, keyboard form submission, visible loading/error/status messages, and responsive result cards. Disable repeated submissions during a request; clear stale results on a new submission and on errors. Bound requests to ten seconds, with a readable retry message. Handle 400, 503, network failures, malformed responses and empty results. Render response text through React; no raw HTML injection.

Keep the existing Spring homepage and game links available on port 8080. No login, event collection, ranking, retraining, deployment, or Twitch enrichment. Use plain CSS and no component framework.

Verify with component/API tests, TypeScript compilation and production build, then browser checks against Java/Python when available. Document the three local processes and the historical-user-ID limitation.
