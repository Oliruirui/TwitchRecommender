# TwitchRecommender

A learning project for channel recommendations: offline data preparation, popularity baseline, two-tower training, FAISS retrieval and a local Python API alongside a Java backend.

- [Project documentation and learning notes](docs/README.md)
- [Python setup and run instructions](recommendation/README.md)
- [Spring Boot migration results](docs/notes/Spring-Boot-Migration-Results.md)

The Python retrieval service and Spring Boot backend are implemented. Java-to-Python retrieval integration is implemented; the recommendation frontend and application event collection are upcoming work. Generated data and model artifacts stay local.

## Java backend (Spring Boot)

Use JDK 21. On macOS, select the installed JDK for the current terminal:

```bash
export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
./mvnw -version
./mvnw verify
./mvnw spring-boot:run
```

The checked-in Maven Wrapper pins Maven 3.9.16 and verifies its distribution SHA256. The first run downloads Maven and dependencies; a global Maven install is unnecessary. Windows users can use `mvnw.cmd` with JDK 21 configured.

The backend starts at `http://127.0.0.1:8080`. Stop it with Ctrl+C. Alternatively, build and run the executable JAR:

```bash
./mvnw clean verify
"$JAVA_HOME/bin/java" -jar target/myProject1-1.0-SNAPSHOT.jar
```

In IntelliJ, import `pom.xml`, set **Project SDK** and the **Maven runner/importer JDK** to 21, then run `TwitchRecommenderApplication.main`. Changing only the terminal JDK does not necessarily change the IDE's Maven JDK. No external Tomcat or WAR deployment is needed.

### Configuration

| Environment variable | Default / purpose |
|---|---|
| SERVER_ADDRESS | 127.0.0.1; override intentionally for non-local access |
| SERVER_PORT | 8080 |
| TWITCH_CLIENT_ID | Empty; Twitch client ID for upstream requests |
| TWITCH_ACCESS_TOKEN | Empty; raw access token, without a `Bearer ` prefix |
| TWITCH_API_BASE_URL | https://api.twitch.tv/helix/; override for controlled local tests |

Set credentials in your shell or IDE environment, never in tracked source files. The application does not automatically load `.env` files or acquire/refresh tokens. With missing or blank credentials, startup and the POST echo work, while otherwise valid Twitch-dependent requests return 503. Tests use dummy values and a local HTTP stub; they do not need Twitch credentials.

### API examples

```bash
curl -s http://127.0.0.1:8080/
curl -s http://127.0.0.1:8080/game \
  -H 'Content-Type: application/json' \
  -d '{"name":"Minecraft","id":"42","box_art_url":"https://example.test/box"}'
curl -s 'http://127.0.0.1:8080/game?name=Minecraft'
curl -s 'http://127.0.0.1:8080/game?limit=10'
curl -s 'http://127.0.0.1:8080/search?game_id=27471'
```

`GET /game` takes exactly one nonblank `name` or integer `limit` (1–100). Duplicate selectors, contradictory parameters or malformed values return 400. `GET /search` requires one nonblank `game_id`. `POST /game` echoes a valid Game JSON object using `name`, `id`, `box_art_url`, omitting null fields; malformed JSON and incompatible field types return 400. Search returns STREAM, CLIP and VIDEO lists and preserves existing item field names/enrichment.

Errors use `{"error":"code"}`: `invalid_request` (400), `game_not_found` (404), `method_not_allowed` (405), `unsupported_media_type` (415), `upstream_failure` (502), `twitch_unconfigured` (503), `internal_error` (500). Upstream failures no longer masquerade as empty successful responses. Empty upstream lists remain valid; an empty name lookup returns 404. A 1-second connection timeout and 2-second per-request timeout are initial safeguards, not measured performance targets.

Routes are now at the root context, such as `/game`, rather than a deployment-specific WAR prefix. The placeholder JSP was replaced by a static backend landing page. The separate /api/recommendations endpoint is described below; no login requirement is introduced.

## Java → Python recommendations

Start the existing Python service on port8000 (see its README), then run Java under JDK21. This endpoint uses dataset demo users and requires no Twitch credentials:

```bash
curl -s http://127.0.0.1:8080/api/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"1","k":10}'
```

Java validates a strict string user_id (trimmed, 1–128 Unicode code points) and strict integer k (1–200, default10), then POSTs to Python `/v1/recommendations`. Invalid input returns400 invalid_request before any Python call. The response preserves Python's request_id, model_version, method, fallback_reason and ordered items. Learned scores are not probabilities. Historical dataset identities are not mapped to real application accounts yet.

Unknown users and recoverable inference failures continue to use Python's existing popularity fallback. There is no Java-local popularity snapshot in this milestone. If Python is unavailable, returns a non200 or invalid response, or exceeds the complete-response deadline, Java returns503 `{"error":"recommendation_unavailable"}`. Interrupted requests cancel pending work and preserve thread interruption. No raw upstream error body is returned.

| Environment variable | Default |
|---|---|
| RECOMMENDER_BASE_URL | http://127.0.0.1:8000 |
| RECOMMENDER_CONNECT_TIMEOUT_MS | 200 |
| RECOMMENDER_REQUEST_TIMEOUT_MS | 2000 |

Both timeouts must be positive, and connect timeout cannot exceed request timeout. Use a server-configured HTTP(S) URL; caller input cannot select the downstream host. Requests do not follow redirects or perform application retries. A separately qualified HTTP client leaves Twitch's existing timeouts unchanged. No Python code/model/training changes or new Java dependencies were required.

To test in Postman, select POST, enter `http://127.0.0.1:8080/api/recommendations`, select Body → raw → JSON, and use the body above. To observe an outage response, stop your Python process and repeat; restarting Python restores normal forwarding without restarting Java. Do not stop a shared process you do not own.

## React frontend

See [frontend/README.md](frontend/README.md) for the React + TypeScript recommendation explorer, local startup and testing. Development UI: http://127.0.0.1:5173/. Java and Python must also be running.
