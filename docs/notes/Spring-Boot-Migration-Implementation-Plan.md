# Spring Boot Migration Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement inline, task by task, after user review. Use test-first behavior checks and one final independent whole-branch review.

**Goal:** Deliver one migration PR that runs the existing Java APIs as a local Spring Boot executable JAR, with verified endpoint contracts and no dependency on the Python service.

**Architecture:** Spring MVC controllers accept requests and delegate to a constructor-injected TwitchClient. Spring configuration supplies credentials, an HTTP client and Jackson ObjectMapper. Controller advice maps typed failures to stable JSON errors. Retain the existing package and domain models.

**Tech stack:** Java 21; Spring Boot 3.5.16; Maven 3.9.16 through Maven Wrapper 3.3.4 (only-script); Boot-managed Jackson 2, Lombok and JUnit dependencies. Use JDK HttpClient for Twitch requests, avoiding an additional legacy HTTP dependency.

**Spec:** [Approved migration design](Spring-Boot-Migration-Design.md).

**Status:** Proposed for implementation review. No application code or dependencies changed while preparing this plan.

## Global constraints

- One migration PR. Python integration is the next PR; model service, datasets and artifacts are unchanged.
- No authentication, database, frontend, retraining, AWS deployment or Java container is added here.
- Java 21 must be selected explicitly: the current shell defaults to Java 26, outside the chosen Boot line's documented range.
- Server defaults to 127.0.0.1:8080, configurable with SERVER_ADDRESS and SERVER_PORT.
- Keep successful Game/Item JSON names and shapes. Deliberately correct invalid-input and upstream-error behavior according to the approved design.
- TWITCH_CLIENT_ID and TWITCH_ACCESS_TOKEN come from the environment; never print their values. Missing credentials must not prevent startup or POST /game.
- All required tests use local fixtures. Live Twitch checks are optional and reported separately.
- No automatic merge. Record test counts, packaged-JAR evidence and remaining limitations in the PR.

## Files and ownership

All Java paths below are relative to `src/main/java/com/example/myProject1/`; tests mirror that package under `src/test/java/`.

| File | Responsibility |
|---|---|
| pom.xml | Boot parent, Java 21 release, executable-JAR plugin and managed dependencies |
| mvnw, mvnw.cmd, .mvn/wrapper/maven-wrapper.properties | Official wrapper scripts and pinned Maven distribution |
| .gitignore | Ignore target/ and local runtime/environment files |
| TwitchRecommenderApplication.java | Spring application entry point |
| config/TwitchConfiguration.java | Beans for HttpClient and TwitchClient; configuration values |
| externalTwitch/TwitchClient.java | Existing Twitch operations, request construction, JSON parsing and enrichment |
| externalTwitch/TwitchException.java | Typed reason enum: UNCONFIGURED, NOT_FOUND, UPSTREAM_FAILURE |
| controller/GameController.java | GET /game selection/validation and POST JSON echo |
| controller/SearchController.java | GET /search validation and grouping |
| controller/ApiExceptionHandler.java | Stable JSON errors; no upstream payload/credential disclosure |
| entity/Game.java, entity/Item.java | Only serialization compatibility changes if tests identify them |
| src/main/resources/application.properties | Local bind/port and Twitch configuration defaults |
| src/main/resources/static/index.html | Minimal backend landing page and example API links |
| src/test/java/.../TwitchRecommenderApplicationTest.java | Application startup with no credentials |
| src/test/java/.../externalTwitch/TwitchClientTest.java | Real HTTP/JSON behavior against a local stub |
| src/test/java/.../controller/ApiControllerTest.java | Route/input/status/JSON contracts with controlled client results |
| src/test/java/.../ApplicationHttpTest.java | Real random-port HTTP wiring and credential-free behavior |
| src/test/resources/twitch/*.json | Tiny hand-authored game, stream, clip and video responses |
| README.md, docs/README.md | Current Java run instructions and milestone status |

Remove the old `servlet/GameServlet.java` and `servlet/SearchServlet.java` in Task 2 when their old client constructor is retired; remove `src/main/webapp/WEB-INF/web.xml` and placeholder `src/main/webapp/index.jsp` in Task 3. Intermediate task commits are not deployed; the final migration PR restores and verifies all supported endpoints. Stop tracking existing target/ build outputs without deleting source files or relying on those binaries. Do not make unrelated entity/client refactors.

## Contract and error decisions

- GET /game: exactly one query parameter among name and limit. Trim values; blank values, both parameters, duplicate selector parameters, invalid integers and limits outside 1–100 return 400. A supplied blank parameter counts as invalid, not absent.
- GET /search: require exactly one nonblank game_id; trim before passing to client. An absent Twitch data array is malformed; an empty array is a valid empty result.
- POST /game: JSON object deserializes to Game and echoes canonical fields name, id, box_art_url. Malformed JSON, null/non-object bodies or incompatible field types return 400. Retain existing null-field omission; do not add required fields beyond the approved echo contract.
- Success is 200. Empty game-name lookup returns 404; empty top-game/content lists remain valid 200 responses.
- Error body is exactly `{"error":"code"}`. Codes: invalid_request (400), game_not_found (404), method_not_allowed (405), upstream_failure (502), twitch_unconfigured (503), internal_error (500). Unsupported request media type may return 415 with unsupported_media_type; valid unsupported HTTP methods return 405.
- Validate client input before checking credentials or making network calls. Missing either credential gives 503 on an otherwise valid Twitch-dependent request. POST echo works with neither credential.
- TwitchClient takes a configurable API base URI (default https://api.twitch.tv/helix/), HttpClient and ObjectMapper. Normalize base URI for relative-path resolution. Use URI/query encoding, never interpolate unescaped input. Configure a 1-second connect timeout and 2-second per-request timeout; no automatic application retries. These are initial safeguards, not measured service targets.
- Check upstream status before parsing. Non-2xx, timeout/I/O failures, invalid envelopes and incompatible payloads become UPSTREAM_FAILURE. Restore the interrupt flag if interrupted. For malformed item JSON, fail the request rather than silently returning an empty successful list.
- Credentials appear only in outgoing headers. Diagnostic logs do not include headers, credentials, raw response bodies or unsanitized exception messages. No token-refresh system is added.

## Review focus

1. Changed Jackson defaults or model annotations must not introduce duplicate camelCase/snake_case fields; full field-set tests own this boundary.
2. Invalid query combinations must return 400 even without credentials; they must not become network calls or a misleading 503.
3. Blank credentials and malformed/empty upstream responses must remain distinguishable through the approved 503/502/404/200 contracts.
4. The executable JAR must serve routes and static resources without an external servlet container, old WAR prefix or tracked target/ binaries.
5. Concurrent requests must not share mutable request state or headers; test separate requests and review singleton client/resource lifecycle.

## Task 1: Reproducible Spring Boot application

**Produces:** `TwitchRecommenderApplication.main(String[] args)`; a context that starts without credentials; pinned wrapper build under Java 21.

- [ ] Verify branch/base and clean status. Select Java 21 with `export JAVA_HOME="$(/usr/libexec/java_home -v 21)"`; confirm `"$JAVA_HOME/bin/java" -version`. Capture the existing 75-test Python baseline through recommendation.run.
- [ ] Obtain official Maven Wrapper 3.3.4 only-script artifacts and pin Maven 3.9.16. Verify the distribution checksum against the publisher and configure distributionSha256Sum. Keep downloaded bootstrap tools outside source control. This setup must not silently install or replace a global JDK/Maven.
- [ ] Add the Boot test/build dependencies needed to compile test scaffolding, then a failing context test `startsWithoutTwitchCredentials` that loads the future application class with blank credential properties. Run it and record the expected missing-entry-point failure; a package-download failure is not a behavior-test failure.
- [ ] Update pom.xml to Boot 3.5.16 parent, Java release 21, spring-boot-starter-web, spring-boot-starter-test, managed Lombok and spring-boot-maven-plugin. Remove explicit old Jackson/JUnit versions and WAR plugin. Keep javax.servlet-api temporarily only while old servlets still need compilation; remove it in Task 2 when the obsolete servlets are deleted.
- [ ] Add the application entry point and properties for server/address/port and twitch.client-id, twitch.access-token, twitch.api-base-url. No network call at startup. Add target/ to .gitignore and remove tracked build outputs from the index.
- [ ] Run `./mvnw -Dtest=TwitchRecommenderApplicationTest test`; expect PASS. Run `./mvnw -version`; expect Maven 3.9.16 and Java 21. Commit `build: establish Spring Boot Java 21 application`.

## Task 2: Configurable and testable Twitch client

**Consumes:** Boot configuration/ObjectMapper from Task 1; existing Game and Item models.

**Produces:** `TwitchClient(HttpClient httpClient, ObjectMapper objectMapper, URI apiBaseUri, String clientId, String accessToken)` and existing public operations `Game searchGame(String name)`, `List<Game> topGames(int limit)`, `Map<String,List<Item>> searchItems(String gameId)`, `List<Item> searchByType(String gameId, ItemType type, int limit)`. Operations throw TwitchException with `getReason(): Reason`. Configuration registers one client bean; requests keep state local.

- [ ] Write failing client tests with JDK local HttpServer on an ephemeral loopback port. Serve hand-authored Helix data envelopes. Assert name query encoding, fixture credentials in headers, game/list parsing, search grouping and stream URL/game/type enrichment. Use only obvious dummy credentials; never existing repository values.
- [ ] Add failure tests: missing/blank credential causes UNCONFIGURED without an HTTP call; empty game-name result causes NOT_FOUND; empty top/content arrays succeed; non-2xx, malformed JSON, missing/non-array data, bad item fields and I/O failure cause UPSTREAM_FAILURE. A controlled client with a short request timeout verifies timeout mapping without a long sleep.
- [ ] Run `./mvnw -Dtest=TwitchClientTest test`; observe failures against the existing constructor/behavior.
- [ ] Implement the constructor/configuration and typed exception. Reuse existing domain operations and enrichment, replace hard-coded credentials and legacy HTTP/JSON parsing with JDK HttpClient and the configured Jackson mapper. Close response resources as applicable; do not catch parsing failures and manufacture empty results. Remove the obsolete servlets now because their old no-argument client constructor is retired; Task 3 supplies the replacement routes. Remove javax.servlet-api, Apache HttpClient, org.json and commons-io once no source uses them.
- [ ] Add tests that serialize representative Game/Item objects and assert exact JSON field sets and values; if a compatibility issue appears, watch that test fail before adjusting annotations. Assert POST-relevant snake_case and STREAM/CLIP/VIDEO values explicitly.
- [ ] Run `./mvnw test`; expect all implemented Java tests pass with no real external calls. Commit `refactor: configure Twitch client and explicit upstream failures`.

## Task 3: Endpoint migration and executable acceptance

**Consumes:** Task 2 TwitchClient bean and typed failure reasons.

**Produces:** Controller routes and error/status contracts above, a portable executable JAR, documented local startup and fixture-backed acceptance evidence.

- [ ] Add ApiControllerTest using MockMvc and controlled TwitchClient responses. Test GET name returns one object; GET limit returns an array; POST echo returns exactly name/id/box_art_url; search returns STREAM/CLIP/VIDEO arrays with expected fields. Assert content type and exact property sets, not only status codes.
- [ ] Add table-driven invalid-input cases for all contract boundaries, including name+limit, blank/duplicate parameters, limits 0/101/text/overflow, missing game_id and malformed/null JSON. Verify no client operation is invoked for those inputs. Assert 404/502/503 and sanitized error bodies from typed client failures; test unsupported HTTP method.
- [ ] Run `./mvnw -Dtest=ApiControllerTest test`; expect failures because new controller routes are absent.
- [ ] Implement GameController, SearchController and ApiExceptionHandler. Use constructor injection and explicit selector validation; return typed objects/maps for Jackson. Confirm both old servlets are gone; remove web.xml, JSP and any remaining legacy-only dependencies. Add the minimal static index page linking /game?limit=10 and /game?name=Minecraft.
- [ ] Add ApplicationHttpTest using @SpringBootTest(webEnvironment=RANDOM_PORT) and actual HTTP calls: static root200, POST echo200 without credentials, valid Twitch request503, invalid Twitch request400. Add a separate fixture-configured context against the local upstream stub to verify a successful real controller→client→stub request. Set test credentials explicitly so a developer's environment cannot affect outcomes.
- [ ] Run `./mvnw verify`; expect all Java tests pass and target/myProject1-1.0-SNAPSHOT.jar is produced. Confirm no javax.servlet imports or legacy servlet registration remain and no build outputs are tracked. Run the existing full Python suite; expect 75 passing unless a documented external environment issue is found.
- [ ] Run the packaged JAR using Java 21 and blank credentials on localhost8080. Check root200, POST /game echo200, valid GET /game503, invalid GET /game400. Record actual responses, process startup and shutdown. Do not claim live Twitch verification from fixtures. If port8080 is occupied, use a documented temporary SERVER_PORT override.
- [ ] Document `./mvnw spring-boot:run`, `./mvnw verify`, `java -jar`, Java21/JAVA_HOME and IntelliJ project/Maven JDK settings, environment variables, endpoint examples and changed error/context-path behavior. Explain that wrapper's first run needs network downloads and API fixtures do not require credentials.
- [ ] Run git diff --check and a staged-secret/build-artifact scan. Commit `feat: migrate game and search routes to Spring MVC`.
- [ ] Perform one independent whole-branch review against this plan/spec. Fix material findings with regression tests, rerun impacted/full checks, then create one migration PR with actual test totals, packaged HTTP evidence and limitations. Do not merge. Keep rollback to the previous merged main revision available through Git; no external state migration exists.
- [ ] Update documentation index, milestone results and the Notion session summary. Ship this plan with the migration PR.

## Acceptance and handoff

Approve execution when the scope/contracts above are acceptable. Preserve the established inline execution approach: implement here, with one independent reviewer at the end. Completion requires verified Java startup, preserved successful endpoint contracts, explicit failure behavior, portable wrapper/JAR commands and unchanged Python tests. The subsequent recommendation integration remains a separate design/PR.

Version references: [Spring Boot 3.5 requirements](https://docs.spring.io/spring-boot/3.5/system-requirements.html), [Apache Maven releases](https://maven.apache.org/download.cgi), [Maven Wrapper](https://maven.apache.org/tools/wrapper/index.html).
