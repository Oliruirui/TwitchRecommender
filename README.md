# TwitchRecommender

A learning project for channel recommendations: offline data preparation, popularity baseline, two-tower training, FAISS retrieval and a local Python API alongside a Java backend.

- [Project documentation and learning notes](docs/README.md)
- [Python setup and run instructions](recommendation/README.md)
- [Spring Boot migration results](docs/notes/Spring-Boot-Migration-Results.md)

The Python retrieval service and Spring Boot backend are implemented. Java-to-Python integration, the recommendation frontend and application event collection are upcoming work. Generated data and model artifacts stay local.

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

Routes are now at the root context, such as `/game`, rather than a deployment-specific WAR prefix. The placeholder JSP was replaced by a static backend landing page. There is no recommendation endpoint or login requirement yet; connecting Java to the Python service is the next milestone.
