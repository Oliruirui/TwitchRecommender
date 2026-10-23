# React recommendation explorer

A local React + TypeScript page for the existing Java recommendation API. Requires Node 22.12+ (tested with Node 24.21.0), npm, the Java backend on 8080, and the Python retrieval server on 8000.

## Start locally

From this repository's `frontend` folder:

```bash
npm ci
npm run dev
```

Open http://127.0.0.1:5173/. Try dataset user ID `1` for personalized results or `new-user` for popularity fallback. These IDs belong to the historical training dataset, not your Twitch account. The names and IDs are historical; results do not indicate current live status. No Twitch credentials are needed for this recommendation page.

Three processes run in separate terminals:

1. Python: from the repository root with the existing Python environment activated:
   ```bash
   RECOMMENDER_BUNDLE_DIR=artifacts/retrieval-bundle-v001 python -m recommendation.run -m uvicorn recommendation.serve:app --host 127.0.0.1 --port 8000 --workers 1
   ```
2. Java: run `TwitchRecommenderApplication` in IntelliJ under JDK 21, or follow the root README's Maven startup instructions.
3. React: `npm run dev` from `frontend/`.

Vite forwards relative `/api` requests to `http://127.0.0.1:8080`. The browser never calls Python directly. The existing Spring homepage and game links remain at http://127.0.0.1:8080/.

Use Ctrl+C in each terminal to stop its process. The bundle environment variable above applies to that Python command; provide it again on the next start. Local development uses no paid hosting or API service.

## Verification

```bash
npm test
npm run build
```

Tests exercise the real page and client, replacing only browser fetch at the network boundary. The build runs strict TypeScript checks and writes static assets to `dist/`. The Vite proxy is development configuration: production hosting/routing is a future task; `dist/` is not automatically served by Spring Boot.

Manual checks: known user → personalized Top 10; unknown user → popular Top 10; blank ID → validation message; stop Python only → error with old results removed; restart Python → retry succeeds without restarting Java or React. The UI always requests k=10; invalid k remains covered by Java's tests and previous Postman testing.

The page clears earlier results on submission, disables concurrent submissions, bounds requests to ten seconds, and handles unavailable services and malformed responses. Scores are raw retrieval values, not probabilities; expand Match details to inspect them. No login, user-event collection, retraining, or live Twitch enrichment is included.
