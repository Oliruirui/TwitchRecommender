# Local Python retrieval service — October 14, 2026

Implemented FastAPI/Uvicorn serving around the previously exported epoch-30 bundle. Model and FAISS index load once at startup; no retraining or historical-data reads during requests. Java and frontend integration remain future work.

## Verification

- 75 Python tests pass, including the previous 36 and 39 new retrieval/HTTP cases.
- Dependency consistency: `pip check` reports no broken requirements.
- Native Uvicorn startup with `retrieval-bundle-v001` succeeds; readiness reports this version.
- Actual HTTP: live/ready, known user, unknown user and API documentation return 200; invalid K returns 422.
- Known user `1` Top 10 matches independent full-catalog dot-product scoring. First three: ninja, tfue, esl_csgo.
- Unknown user results match the bundle's training-only popularity order and use null scores.
- Synthetic tests verify missing/corrupt bundle and failed warmup return unready/503, fallback on retrieval errors, load-once behavior after deleting files, strict input validation, ties, short catalogs and unchanged model state.
- Docker Compose configuration is included. Docker/Linux execution is unverified: Docker is not installed on this laptop.
- No throughput/latency target has been measured.

## Try it

From the repository checkout, keep this command running:

```bash
RECOMMENDER_BUNDLE_DIR=artifacts/retrieval-bundle-v001 \
.venv/bin/python -m recommendation.run -m uvicorn \
  recommendation.serve:app --host 127.0.0.1 --port 8000 --workers 1
```

Open http://127.0.0.1:8000/docs and expand `POST /v1/recommendations`. Choose **Try it out**, enter `{"user_id":"1","k":10}`, and click **Execute**. A user ID absent from training uses popularity fallback. Stop the server with Ctrl+C before starting a second copy on the same port.

## Dependency choice

FastAPI 0.143.1, Uvicorn 0.54.0 and HTTPX 0.28.1 are pinned. Starlette 0.52.1 and AnyIO 4.12.1 keep the planned HTTPX TestClient integration free of deprecation warnings. Future dependency updates require re-running the serving tests.

Recorded HTTP evidence is in [Python-Retrieval-Service-HTTP-Results.json](Python-Retrieval-Service-HTTP-Results.json). For current run and test commands, see [the package README](../../recommendation/README.md).

## Delivery and review

[PR #4](https://github.com/Oliruirui/TwitchRecommender/pull/4) was merged. Commits: 15ca64f (service) and 1afc3b3 (review fix). Independent review found one Important startup metadata issue; six regression cases first failed, then the fix passed with the full 75-test suite. No Critical or deferred Minor findings.

Decisions retained after review: Docker/Linux verification remains pending (platform fixes may still be needed); FAISS owns tied-boundary membership (equal-scoring channels can vary across runtimes); throughput and continuous readiness monitoring remain later work (capacity and post-startup failures are not yet measured/monitored); Java account integration and hostile-bundle protection remain later work (use dataset IDs and locally trusted artifacts).

The October 14 Notion session summary was added, and the earlier export PR status was corrected to merged.
