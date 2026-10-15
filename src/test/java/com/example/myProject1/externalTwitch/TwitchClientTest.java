package com.example.myProject1.externalTwitch;

import com.example.myProject1.entity.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import java.io.*;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class TwitchClientTest {
    HttpServer server;
    URI base;
    ObjectMapper mapper = JsonMapper.builder().disable(MapperFeature.ALLOW_COERCION_OF_SCALARS).build();
    AtomicInteger calls = new AtomicInteger();
    volatile String query, authorization, clientId;
    volatile int status = 200;
    volatile String body = "{\"data\":[]}";

    @BeforeEach void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/helix/", exchange -> {
            calls.incrementAndGet();
            query = exchange.getRequestURI().getRawQuery();
            authorization = exchange.getRequestHeaders().getFirst("Authorization");
            clientId = exchange.getRequestHeaders().getFirst("Client-Id");
            String payload = switch (exchange.getRequestURI().getPath()) {
                case "/helix/streams" -> fixture("streams");
                case "/helix/clips" -> fixture("clips");
                case "/helix/videos" -> fixture("videos");
                default -> body;
            };
            byte[] bytes = payload.getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(status, bytes.length);
            try (var out = exchange.getResponseBody()) { out.write(bytes); }
        });
        server.start();
        base = URI.create("http://127.0.0.1:"+server.getAddress().getPort()+"/helix");
    }
    @AfterEach void stop() { server.stop(0); }
    String fixture(String name) throws IOException {
        try (var in = getClass().getResourceAsStream("/twitch/"+name+".json")) {
            return new String(Objects.requireNonNull(in).readAllBytes(), StandardCharsets.UTF_8);
        }
    }
    TwitchClient client() { return new TwitchClient(HttpClient.newHttpClient(), mapper, base, "fixture-id", "fixture-token"); }

    @Test void gameLookupEncodesQueryAndUsesCredentialHeaders() throws Exception {
        body = fixture("games");
        Game game = client().searchGame("A & B/世界");
        assertEquals("name=A+%26+B%2F%E4%B8%96%E7%95%8C", query);
        assertEquals("Bearer fixture-token", authorization);
        assertEquals("fixture-id", clientId);
        assertEquals(mapper.readTree("{\"name\":\"Minecraft\",\"id\":\"42\",\"box_art_url\":\"https://example.test/box.jpg\"}"), mapper.valueToTree(game));
    }
    @Test void topGamesPreservesListAndQuery() throws Exception {
        body = fixture("games");
        assertEquals("42", client().topGames(10).getFirst().getId());
        assertEquals("first=10", query);
    }
    @Test void searchGroupsAndEnrichesAllContentTypes() throws Exception {
        Map<String,List<Item>> result = client().searchItems("42");
        assertEquals(Set.of("STREAM","CLIP","VIDEO"), result.keySet());
        assertEquals("game_id=42&first=20", query);
        JsonNode stream = mapper.valueToTree(result.get("STREAM").getFirst());
        assertEquals(mapper.readTree("{\"id\":\"s1\",\"title\":\"A stream\",\"broadcaster_name\":\"alice\",\"url\":\"https://www.twitch.tv/alice\",\"thumbnail_url\":\"https://example.test/stream.jpg\",\"game_id\":\"42\",\"item_type\":\"STREAM\"}"), stream);
        assertEquals(ItemType.CLIP, result.get("CLIP").getFirst().getType());
        assertEquals("https://example.test/clip", result.get("CLIP").getFirst().getUrl());
        assertEquals(ItemType.VIDEO, result.get("VIDEO").getFirst().getType());
        assertEquals(3, calls.get());
    }
    @Test void absentOrBlankCredentialsPreventNetworkCalls() {
        for (String[] pair : List.of(new String[]{"", "token"}, new String[]{"id", " "}, new String[]{null, "token"})) {
            var client = new TwitchClient(HttpClient.newHttpClient(), mapper, base, pair[0], pair[1]);
            assertEquals(TwitchException.Reason.UNCONFIGURED, assertThrows(TwitchException.class, () -> client.topGames(10)).getReason());
        }
        assertEquals(0, calls.get());
    }
    @Test void emptyGameNameIsNotFoundButEmptyListIsValid() throws Exception {
        assertEquals(TwitchException.Reason.NOT_FOUND, assertThrows(TwitchException.class, () -> client().searchGame("missing")).getReason());
        assertTrue(client().topGames(10).isEmpty());
    }
    @ParameterizedTest @ValueSource(strings={"not json", "{}", "{\"data\":null}", "{\"data\":{}}", "{\"data\":[null]}", "{\"data\":[{\"id\":[],\"name\":\"x\"}]}"})
    void invalidEnvelopeOrGamePayloadFails(String invalid) {
        body = invalid;
        assertEquals(TwitchException.Reason.UPSTREAM_FAILURE, assertThrows(TwitchException.class, () -> client().topGames(10)).getReason());
    }
    @Test void upstreamStatusDoesNotLeakItsBody() {
        status = 401; body = "private upstream response";
        TwitchException failure = assertThrows(TwitchException.class, () -> client().topGames(10));
        assertEquals(TwitchException.Reason.UPSTREAM_FAILURE, failure.getReason());
        assertFalse(failure.getMessage().contains("private"));
    }
    @Test void timeoutAndIoFailuresMapToTypedError() throws Exception {
        HttpClient transport = mock(HttpClient.class);
        when(transport.send(any(HttpRequest.class), any(HttpResponse.BodyHandler.class)))
            .thenThrow(new HttpTimeoutException("private transport detail"), new IOException("private detail"));
        var client = new TwitchClient(transport, mapper, base, "id", "token");
        for (int i=0;i<2;i++) assertEquals(TwitchException.Reason.UPSTREAM_FAILURE, assertThrows(TwitchException.class, () -> client.topGames(10)).getReason());
    }
    @Test void emptyAndMalformedContentListsAreDistinguished() throws Exception {
        server.removeContext("/helix/");
        server.createContext("/helix/", exchange -> {
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, bytes.length);
            try(var out=exchange.getResponseBody()){out.write(bytes);}
        });
        assertTrue(client().searchByType("42", ItemType.STREAM, 20).isEmpty());
        body = "{\"data\":[{\"id\":{},\"title\":\"bad\"}]}";
        assertEquals(TwitchException.Reason.UPSTREAM_FAILURE, assertThrows(TwitchException.class, () -> client().searchByType("42", ItemType.CLIP, 20)).getReason());
    }
}
