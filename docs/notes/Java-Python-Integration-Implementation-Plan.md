# Java → Python Integration Implementation Plan

> Use superpowers:executing-plans inline, test-first, with a final independent review. The user's narrowed scope and API contract are approved in conversation.

Goal: add Java POST /api/recommendations around the existing Python API.
Spec: [approved narrowed design](Java-Python-Integration-Design.md).

## Tasks

1. Write loopback-backed HTTP integration tests for exact forwarding/personalized and Python-popular responses; defaults/strict validation; downstream malformed/non200/unavailable/timeout responses. Watch failures before implementation.
2. Add recommendation/RecommendationRequest.java (strict input normalization), RecommendationUnavailableException.java, PythonRecommendationClient.java (JSON request, complete-response deadline, response validation), RecommendationConfiguration.java (qualified HTTP client) and controller/RecommendationController.java. Extend ApiExceptionHandler only for503 recommendation_unavailable. Add recommendation configuration properties; no dependencies or Python changes.
3. Run targeted and complete Java tests, Python regression suite and real Java→Python checks on test ports. Update README/design/results, perform independent review, fix material issues with reproducing tests, and publish one PR. Preserve developer IDE changes; do not merge automatically.

Review focus: strict numeric/string/null input handling; valid Python-popular passthrough; malformed/partial/nonfinite/duplicate results; deadline covering response body and cancellation; separate Twitch/recommendation client wiring. Tests must exercise each boundary. No Java snapshot/fallback, authentication, frontend or training.
