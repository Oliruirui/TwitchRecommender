# Python Retrieval Service Implementation Plan

> Historical planning/usage note. Check [project status](../README.md) and [current run instructions](../../recommendation/README.md) before following commands. Unchecked boxes preserve the original plan; they are not a live task tracker.

> **For agentic workers:** Use superpowers:executing-plans after user review. Implement inline, task by task, with test-first behavior checks and one final independent review.

**Goal:** Start a local HTTP service that loads the existing bundle once and returns personalized or popular Top K channels.

**Architecture:** FastAPI owns request validation, lifecycle, health and JSON responses. A separate in-memory retrieval engine uses the existing `load_bundle()` and FAISS index. Uvicorn runs one worker; the existing macOS launcher handles native-library compatibility.

**Tech stack:** Existing Python/PyTorch/FAISS; add and pin compatible FastAPI, Uvicorn and HTTPX versions during implementation. Docker Compose provides an optional local container entry point.

**Spec:** [LLD](TwitchRecommender-LLD-v0.1.md), first Python serving version, startup/health, fallback and local deployment. The concrete contracts below resolve this milestone's remaining details.

## Scope and constraints

- Use `artifacts/retrieval-bundle-v001`, built from the selected thirty-epoch model. Do not retrain, rebuild the index, or read historical datasets during requests.
- Run locally with no paid services. Keep Java, frontend, ranking, exposure/click storage and experiment assignment for later milestones.
- Reuse `recommendation/export.py::load_bundle`; do not duplicate its checksum and compatibility validation.
- Load once per process at startup; no hot reload. One worker initially. CPU Torch uses one thread; set FAISS's thread count to one in the thread performing search.
- Keep previously watched channels eligible. Treat scores as learned dot products, not probabilities.
- Make one implementation PR after review. Do not merge it automatically.

## Files to change

| File | Change |
|---|---|
| `recommendation/retrieval.py` | New: in-memory engine, personalized retrieval, popular fallback |
| `recommendation/serve.py` | New: FastAPI schemas, startup lifecycle, endpoints, request IDs |
| `recommendation/tests/conftest.py` | New: small synthetic bundle fixture shared by new serving tests |
| `recommendation/tests/test_retrieval.py` | New: engine behavior and fallback checks |
| `recommendation/tests/test_serve.py` | New: HTTP contracts, startup and health checks |
| `recommendation/requirements.txt` | Add pinned FastAPI, Uvicorn and HTTPX dependencies |
| `recommendation/README.md` | Add startup, curl, API-docs and container instructions |
| `compose.yaml` | New: Python service only, local port and read-only bundle mount |

Reuse the existing `model.py`, `export.py`, `run.py`, and training Dockerfile. No model/training changes are planned.

## API contract

### POST /v1/recommendations

Request: `{"user_id":"1","k":10}`. `user_id` is a strict string, trimmed, 1–128 characters after trimming. `k` is a strict integer from 1 to 200, default 10; reject booleans, numeric strings, floats, null and out-of-range values with HTTP 422. Reject whitespace-only identities.

Successful HTTP 200 response:

```json
{
  "request_id": "a-new-UUID-for-this-request",
  "model_version": "retrieval-bundle-v001",
  "method": "two_tower",
  "fallback_reason": null,
  "items": [
    {"channel_id": "12", "channel_name": "example_channel", "retrieval_score": 1.25}
  ]
}
```

The single item above illustrates the schema, not a complete Top 10. Return exactly `min(k, catalog_size)` distinct items. Channel IDs are bundle-local indices. Personalized items are ordered by score descending, then integer channel index for equal returned scores; membership at a tied K boundary follows FAISS. Keep popularity's existing order for fallback.

Unknown user: HTTP 200, `method="popular"`, `fallback_reason="unknown_user"`, and null retrieval scores. Recoverable retrieval exceptions or invalid native search results use the same fallback with reason `retrieval_error`; log the failure server-side without returning internal details. Validate returned IDs, uniqueness, count and finite scores before sending a personalized response.

If no validated bundle is loaded, return HTTP 503 with `{"detail":"recommendation service unavailable"}`. Never use a popularity file from an invalid bundle. Java's independent outage snapshot belongs to the later Java milestone.

### Health endpoints

- `GET /health/live`: HTTP 200, `{"status":"alive"}` when the process can respond.
- `GET /health/ready`: HTTP 200, `{"status":"ready","model_version":"..."}` after complete bundle load and one known-user smoke query; otherwise HTTP 503, `{"status":"not_ready"}`.

The startup smoke query must return `method=two_tower` with valid results; a popularity fallback does not count as a successful warmup. Startup load failures are logged once and leave the app running but unready, so health and request behavior are observable. Restart after correcting configuration; no automatic reload. Readiness reports loaded bundle usability, not continuous deep inspection of inference quality.

## Review focus

- Malformed IDs and K values must fail before model computation.
- Unknown users and retrieval failures must have traceable, distinct fallback reasons.
- Missing/corrupt bundles must fail readiness and recommendations without exposing partial state.
- Short catalogs and tied scores must not produce padding IDs, duplicates or invented results.
- Multiple requests must reuse the same loaded objects and preserve bundle version and model state.

## Task 1: Retrieval engine

**Interfaces:** `RetrievalEngine(bundle: dict)` consumes the existing loader result. `recommend(user_id: str, k: int) -> dict` returns `model_version`, `method`, `fallback_reason`, and `items`; the HTTP layer adds the request UUID. Construction prepares channel names in mapping-index order. It does not reopen artifact files per request.

- [ ] Create a synthetic, trusted twenty-channel bundle fixture with known vectors and a deterministic popular order; no downloaded data or real model is required for unit tests.
- [ ] Write failing tests: known-user scores/Top K against hand-computed dots; unknown user returns popularity; K larger than catalog returns every channel once; previously watched channels remain eligible.
- [ ] Add failing tests for a real search exception and invalid results (nonfinite scores, duplicate IDs or FAISS padding). Assert returned fallback contents/reason, not merely that a mocked method was called.
- [ ] Run `python -m recommendation.run -m pytest recommendation/tests/test_retrieval.py -q`; observe failures from missing behavior.
- [ ] Implement encoding under `torch.inference_mode()`, FAISS search with K clamped to catalog size, output validation, mapping, ordering and fallback. Keep the shared index/model read-only.
- [ ] Rerun tests; require all passing and unchanged weights before/after repeated queries.

## Task 2: FastAPI lifecycle and endpoints

**Interfaces:** `create_app(bundle_dir: Path | None = None) -> FastAPI`; module-level `app = create_app()`. Resolve the explicit path first, otherwise `RECOMMENDER_BUNDLE_DIR`. Missing configuration leaves the service unready. Load in FastAPI lifespan and publish one engine to application state only after the known-user smoke query succeeds. Clear it at shutdown.

- [ ] Add pinned dependencies. Use a real FastAPI TestClient with the synthetic bundle; no network server is needed for unit tests.
- [ ] Write failing tests for the three endpoints and declared JSON/status contracts, including default K, strict validation, fresh UUIDs, and a known personalized response.
- [ ] Add startup tests for missing/corrupt artifacts and successful ready/version output. Confirm a valid request returns 503 while unready and health/live still returns 200.
- [ ] Verify load-once behavior by removing the fixture's on-disk bundle after startup and issuing two successful requests. Verify unknown/retrieval-error fallback through the HTTP path.
- [ ] Run `python -m recommendation.run -m pytest recommendation/tests/test_serve.py -q` and observe intended failures.
- [ ] Implement lifecycle and endpoints. Use synchronous recommendation handlers so CPU inference runs outside the event loop. Generate UUID4 per handled recommendation request. Add typed response schemas and finite-score constraints.
- [ ] Rerun targeted tests, then the full existing suite through the launcher; all earlier 36 checks must remain passing.

## Task 3: Local run, container configuration and acceptance

**Files:** README, requirements, and new `compose.yaml`. Retain the existing Dockerfile's Python entry point.

- [ ] Start the real local server with the existing bundle and one Uvicorn worker. Bind native development access to `127.0.0.1:8000`.
- [ ] Call both health endpoints and POST known/unknown/invalid-user requests with curl. Verify known Top K matches direct querying of the loaded bundle, unknown users receive popular fallback, and invalid K returns 422. Record actual response evidence.
- [ ] Confirm the generated API documentation is available at `http://127.0.0.1:8000/docs`.
- [ ] Add Compose service `recommender`, build using `recommendation/Dockerfile`, publish `127.0.0.1:8000:8000`, mount `./artifacts/retrieval-bundle-v001:/app/artifacts/retrieval-bundle-v001:ro`, and set `RECOMMENDER_BUNDLE_DIR=/app/artifacts/retrieval-bundle-v001`.
- [ ] Compose command: `["-m", "uvicorn", "recommendation.serve:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]`. No Java container, event volume or online logging database in this milestone.
- [ ] If Docker is installed/running, verify container startup and the same HTTP smoke cases. Otherwise explicitly record container execution as pending; native success must not be reported as Docker verification.
- [ ] Finish documentation, full tests, dependency checks and independent review. Create one PR with actual verification results and limitations. Update the Notion session summary after completion.

## Intended local command after implementation

From the existing repository checkout:

```bash
RECOMMENDER_BUNDLE_DIR=artifacts/retrieval-bundle-v001 \
.venv/bin/python -m recommendation.run -m uvicorn \
  recommendation.serve:app --host 127.0.0.1 --port 8000 --workers 1
```

In another terminal:

```bash
curl -s http://127.0.0.1:8000/health/ready
curl -s http://127.0.0.1:8000/v1/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"1","k":10}'
```

Historical plan: the service was subsequently implemented and merged in [PR #4](https://github.com/Oliruirui/TwitchRecommender/pull/4). Success means a working local retrieval-only HTTP service with demonstrated fallback and health behavior. Serving capacity and latency optimization remain later measured work; no 100-RPS guarantee is made.
