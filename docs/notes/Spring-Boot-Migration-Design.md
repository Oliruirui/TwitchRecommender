# Spring Boot migration design — October 15, 2026

Status: design approved on October 15, 2026; implementation plan and migration code are pending.

## Goal and boundary

Run the existing Java backend locally as a Spring Boot application and preserve the useful behavior of `/game` and `/search`. This is one migration PR. Python integration is the next PR; the model service, datasets and artifacts are unchanged. No authentication, database, frontend, retraining, AWS deployment or Java container is added here.

The current application has two Java Servlets, entity classes and a Twitch API client. It targets Java 8 and packages a WAR. There is no recommendation endpoint or login flow. The JSP is a hello-world placeholder with a link to a nonexistent servlet.

## Approach

Convert the two servlets to Spring MVC REST controllers in the existing package and reuse the entity/client logic. This avoids maintaining both servlet registration and controller routing. Retaining the old servlets inside Boot would be an alternative with less initial endpoint conversion but more legacy setup; creating a separate backend would duplicate project/build maintenance.

Use Java 21 (already installed) and Spring Boot 3.5.16 with its managed Jackson 2 dependencies to limit changes to the existing Jackson 2 code. Boot 4.1.1 is the latest stable line, but upgrading to its serialization stack is additional migration scope. Recheck supported releases before implementation and pin the final dependency set in the plan. Boot 3.5 supports Java 17–25, so explicitly use Java 21 rather than the shell's current Java 26.

Build an executable JAR with an embedded server. Add a Maven Wrapper so a global Maven installation is unnecessary. Configure local default binding to 127.0.0.1:8080, with environment overrides. Document IntelliJ JDK selection, wrapper commands and `java -jar` execution. Python remains independently available on port 8000.

## Components and configuration

- Application entry point: boots Spring and discovers controllers/configuration.
- Game controller: GET game queries and existing JSON POST echo.
- Search controller: GET content grouped by STREAM, CLIP and VIDEO.
- Twitch client bean: constructor-injected into controllers. Keep Twitch-specific parsing and enrichment in the client; use deterministic upstream fixtures for tests.
- Consistent exception handling: JSON errors without credentials or upstream response bodies.
- Configuration: Twitch client ID and bearer token supplied through environment variables, replacing embedded credential literals in active code. No token acquisition or refresh system in this milestone. Missing credentials allow server startup and the POST echo but make Twitch-dependent requests return 503.

No real Twitch call is needed to build or test the application. A live smoke check is optional when valid credentials are available; report it separately from fixture-backed verification. Do not display, log or copy existing secrets into documentation.

## HTTP contracts

Routes are relative to the application root, without the previous deployment-specific WAR prefix. Preserve successful response field names and object/list shapes through explicit Jackson tests.

| Request | Successful response |
|---|---|
| GET /game?name=… | One Game object |
| GET /game?limit=N | Game list; N is an integer from 1 through 100 |
| POST /game with a Game JSON body | Echo the deserialized Game, retaining name, id and box_art_url |
| GET /search?game_id=… | Object with STREAM, CLIP and VIDEO lists, retaining existing item fields and enrichment |

Require exactly one nonblank name or limit for GET /game. Require a nonblank game_id for search. Missing, contradictory or malformed parameters and malformed JSON return 400. Unknown game name returns 404. Twitch transport/status/response-format failures return 502; missing local credentials return 503. Error JSON uses `{"error":"stable_error_code"}`. These are deliberate corrections to the old inconsistent empty-success/500 paths, not promises to preserve those bugs. Unsupported methods return 405.

Remove the obsolete servlet/web.xml setup. Replace the placeholder JSP with a small static root page that identifies the backend and lists example API URLs; no recommendation UI is added. Do not preserve the broken `hello` link. Keep the existing public endpoint behavior; no Spring Security/login requirement is introduced.

## Verification and completion

1. Controller tests with deterministic Twitch data verify routes, query handling, status codes and JSON contracts, including POST echo and item-field names.
2. A local stub HTTP server verifies the actual Twitch client request/response boundary, upstream errors and malformed payload handling without Twitch credentials.
3. An application-context test checks bean/configuration wiring; a random-port HTTP integration test checks the running server and missing-credential behavior.
4. Wrapper tests and executable JAR packaging pass under Java 21. Run the packaged JAR on localhost and verify static root, POST echo and a clear 503 for unconfigured Twitch calls.
5. Existing 75 Python tests remain passing. Verify repository changes contain no generated build output or new secret values.
6. Independent review, one PR with actual test evidence and limitations; no automatic merge. Provide local commands so Olivia can start it herself. Update the project notebook at session end.

This milestone is complete when a packaged Java server starts locally and both endpoint contracts are verified with controlled upstream data. Live Twitch access is a separate credential-dependent check, not implied by successful migration tests.

## Sources

- Spring Boot 3.5 system requirements: https://docs.spring.io/spring-boot/3.5/system-requirements.html
- Current Spring Boot system requirements: https://docs.spring.io/spring-boot/system-requirements.html
