# Spring Boot migration results — October 15, 2026

Replaced the two legacy servlets with Spring MVC controllers and packaged the Java backend as an executable JAR. `/game` and `/search` retain their successful JSON shapes; invalid input and upstream errors now return explicit JSON status/error contracts. No recommendation endpoint or Python call is added in this milestone.

## Recorded verification

- Maven Wrapper 3.3.4 runs Maven 3.9.16 under Java 21.0.12.1. The Maven archive was checked against the publisher SHA512; the wrapper pins distribution SHA256. Wrapper scripts were checked against Maven Central's available artifact checksum.
- `./mvnw clean verify`: 48 Java tests pass and the executable JAR is built.
- Python regression suite: 75 tests pass in 6.40 seconds.
- Java tests include context startup, exact Game/Item JSON, MockMvc endpoint validation/error behavior, real HTTP client calls against local Helix fixtures, and random-port application HTTP tests, including concurrent lookups.
- MockMvc exposed numeric-to-string JSON coercion; explicit textual coercion configuration now rejects incompatible scalar values. Encoded whitespace cases use real URI parsing.
- Packaged JAR started on 127.0.0.1:8080 without Twitch credentials. Root and POST echo return200; invalid limit returns400; otherwise valid game/search requests return503 with twitch_unconfigured. [Recorded responses](Spring-Boot-HTTP-Results.json).
- Credential literals were removed from active source; configuration uses environment variables. Forty-one previously tracked generated build files were removed from version control; target/ is now ignored.

## Compatibility and limits

Successful field names remain name/id/box_art_url for Game and the existing snake_case item fields. Domain entity source files did not need changes. Routes now use the root context instead of a deployment-specific WAR prefix. The hello-world JSP and old servlet configuration are removed; the root serves a static backend page.

Invalid/missing/duplicate selectors return400; name lookup with no result returns404; Twitch errors or invalid response data return502; missing credentials return503. Empty upstream lists are valid. Errors do not expose upstream bodies or credentials. Client requests have a 1-second connect timeout and a 2-second request timeout, with no application retry loop.

Tests use a local HTTP stub and dummy credentials. Live Twitch access, real token validity/refresh, Docker, throughput and latency targets were not verified. No Python behavior, training, data, authentication or application account mapping changed. Token acquisition/refresh and Java-to-Python integration remain future work.

## Run it

From the repository root on macOS:

```bash
export JAVA_HOME="$(/usr/libexec/java_home -v 21)"
./mvnw verify
./mvnw spring-boot:run
```

Or run `"$JAVA_HOME/bin/java" -jar target/myProject1-1.0-SNAPSHOT.jar`. See the [repository README](../../README.md) for environment configuration and API examples. First use of the wrapper requires network downloads.
