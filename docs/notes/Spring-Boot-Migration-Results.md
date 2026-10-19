# Spring Boot migration results — October 15–18, 2026

Replaced the two legacy servlets with Spring MVC controllers and packaged the Java backend as an executable JAR. `/game` and `/search` retain their successful JSON shapes; invalid input and upstream errors now return explicit JSON status/error contracts. No recommendation endpoint or Python call is added in this milestone.

## Recorded verification

- Maven Wrapper 3.3.4 runs Maven 3.9.16 under Java 21.0.12.1. The Maven archive was checked against the publisher SHA512; the wrapper pins distribution SHA256. Wrapper scripts were checked against Maven Central's available artifact checksum.
- `./mvnw clean verify`: 53 Java tests pass and the executable JAR is built.
- Python regression suite: 75 tests pass in 8.40 seconds.
- Java tests include context startup, exact Game/Item JSON, MockMvc endpoint validation/error behavior, real HTTP client calls against local Helix fixtures, and random-port application HTTP tests, including concurrent lookups.
- MockMvc exposed numeric-to-string JSON coercion; explicit textual coercion configuration now rejects incompatible scalar values. Encoded whitespace cases use real URI parsing.
- Packaged JAR started on loopback (port8080 initially; final verification uses18080 to avoid the developer’s IntelliJ process) without Twitch credentials. Root and POST echo return200; invalid limit returns400; otherwise valid game/search requests return503 with twitch_unconfigured. [Recorded responses](Spring-Boot-HTTP-Results.json).
- Credential literals were removed from active source; configuration uses environment variables. Forty-one previously tracked generated build files were removed from version control; target/ is now ignored.

## Compatibility and limits

Successful field names remain name/id/box_art_url for Game and the existing snake_case item fields. Domain entity source files did not need changes. Routes now use the root context instead of a deployment-specific WAR prefix. The hello-world JSP and old servlet configuration are removed; the root serves a static backend page.

Invalid/missing/duplicate selectors return400; name lookup with no result returns404; Twitch errors or invalid response data return502; missing credentials return503. Empty upstream lists are valid. Errors do not expose upstream bodies or credentials. Client requests have a 1-second connect timeout and a 2-second request timeout, with no application retry loop.

Required automated tests use a local HTTP stub and dummy credentials. On October18, Olivia separately confirmed successful Postman→Twitch and browser→Java→Twitch `/game?limit=10` calls. This is a user-reported live smoke check, not an automated assertion about every Twitch endpoint. Token refresh, Windows execution, Docker, throughput and latency targets remain unverified. No Python behavior, training, data, authentication or application account mapping changed. Token acquisition/refresh and Java-to-Python integration remain future work.

## Run it

From the repository root on macOS:

```bash
export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
./mvnw verify
./mvnw spring-boot:run
```

Or run `"$JAVA_HOME/bin/java" -jar target/myProject1-1.0-SNAPSHOT.jar`. See the [repository README](../../README.md) for environment configuration and API examples. First use of the wrapper requires network downloads.

## Review fixes

Independent review reproduced missing stream broadcaster data producing a fabricated /null URL. Four real HTTP regressions for missing/null/empty/blank broadcaster values failed before the fix and now return502 upstream_failure.

A follow-up test also proved that the JDK request timeout alone did not bound a delayed response body. The client now waits at most two seconds for the complete async response, cancels an unfinished request, and maps failures to the existing sanitized error. The delayed-body regression failed before the fix and passes afterward. Full STREAM/CLIP/VIDEO serialization assertions pass.

Review boundaries retained: validation covers fields used in current parsing/enrichment, not a complete independent implementation of Twitch’s schemas; other malformed metadata may need future checks. Live credential validity/revocation and renewal are managed separately; this milestone does not verify credential administration. Windows and production capacity require separate validation. No deferred Minor findings.
