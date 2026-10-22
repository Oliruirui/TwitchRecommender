# Java → Python integration results — October 21, 2026

Implemented POST /api/recommendations through a controller and a Python HTTP client in the existing Spring Boot application. User-approved scope excludes a separate Java recommendation service/fallback snapshot. Python serving, inference and training code are unchanged; no new dependency was added.

## Verification

- Clean Maven verify:99 Java tests pass,0 failures/errors; executable JAR produced. The prior baseline was53;46 new recommendation checks cover the controller/client boundary.
- Python regression suite:75 tests pass in8.00 seconds.
- The first31 recommendation HTTP cases failed404 before implementation, then passed after adding the endpoint.
- Loopback-stub tests cover exact normalized POST/default K, boundary K, strict input and Unicode length, exact personalized/Python-popular passthrough, invalid response contracts, nonfinite/duplicate/oversized results, non200 and malformed responses, delayed headers/body, unavailable port, and interruption/cancellation.
- Native acceptance used independent Java18090/Python18100 processes and the saved retrieval-bundle-v001. Known user1 and unknown-user Top10 payloads match direct Python calls, apart from fresh per-call UUIDs. Invalid K returns400. Stopping only the test Python process gives Java503 recommendation_unavailable. Both test processes were stopped afterward; developer processes/IDE settings were untouched.
- [Recorded native responses](Java-Python-Integration-HTTP-Results.json).

## Contract and limits

Java preserves Python's request ID, version, item order and scores. Unknown users retain Python's unknown_user popular fallback. No Java-local popularity fallback, authentication/account mapping, frontend, Twitch enrichment, online event storage, ranking or retraining is added. The API uses historical dataset IDs.

Connection timeout defaults200ms and the entire HTTP response is bounded by a2000ms deadline, with cancellation and no application retries. These are initial settings, not measured throughput/latency targets. Invalid/non200/unavailable downstream responses map to a sanitized503; invalid caller input maps to400 before network access.

Python remains responsible for exact catalog-relative Top K quality. Java checks shape/count≤K, identities, score validity and descending personalized scores, not independent model correctness. Local native execution is verified; Docker/Windows, production scale and authentication are future work.
