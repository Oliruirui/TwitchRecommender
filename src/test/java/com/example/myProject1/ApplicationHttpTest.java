package com.example.myProject1;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.*;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties={"twitch.client-id=", "twitch.access-token="})
@DirtiesContext
class ApplicationHttpTest {
    @Autowired TestRestTemplate http;
    @Autowired ObjectMapper mapper;

    @Test void packagedRoutesWorkWithoutCredentials() throws Exception {
        var root=http.getForEntity("/",String.class);
        assertEquals(200,root.getStatusCode().value());
        assertTrue(root.getBody().contains("TwitchRecommender backend"));
        HttpHeaders headers=new HttpHeaders();headers.setContentType(MediaType.APPLICATION_JSON);
        String body="{\"name\":\"Minecraft\",\"id\":\"42\",\"box_art_url\":\"https://example.test/box\"}";
        var echo=http.postForEntity("/game",new HttpEntity<>(body,headers),String.class);
        assertEquals(200,echo.getStatusCode().value());
        assertEquals(mapper.readTree(body),mapper.readTree(echo.getBody()));
    }
    @Test void validationPrecedesCredentialCheckOverRealHttp() throws Exception {
        var valid=http.getForEntity("/game?limit=10",String.class);
        assertEquals(503,valid.getStatusCode().value());
        assertEquals(mapper.readTree("{\"error\":\"twitch_unconfigured\"}"),mapper.readTree(valid.getBody()));
        var invalid=http.getForEntity("/game?limit=0",String.class);
        assertEquals(400,invalid.getStatusCode().value());
        assertEquals(mapper.readTree("{\"error\":\"invalid_request\"}"),mapper.readTree(invalid.getBody()));
        assertEquals(503,http.getForEntity("/search?game_id=42",String.class).getStatusCode().value());
    }
}

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties={"twitch.client-id=fixture-id", "twitch.access-token=fixture-token"})
@DirtiesContext
class ApplicationFixtureHttpTest {
    static HttpServer upstream;
    static volatile String streamsPayload = "{\"data\":[]}";
    @Autowired TestRestTemplate http;
    @Autowired ObjectMapper mapper;

    @DynamicPropertySource static void configure(DynamicPropertyRegistry properties) throws Exception {
        upstream=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        upstream.createContext("/helix/games", exchange -> {
            if (!"fixture-id".equals(exchange.getRequestHeaders().getFirst("Client-Id"))
                || !"Bearer fixture-token".equals(exchange.getRequestHeaders().getFirst("Authorization"))) {
                exchange.sendResponseHeaders(401,-1);exchange.close();return;
            }
            String name=URLDecoder.decode(exchange.getRequestURI().getRawQuery().split("=",2)[1],StandardCharsets.UTF_8);
            byte[] body=("{\"data\":[{\"id\":\"42\",\"name\":\""+name+"\",\"box_art_url\":\"https://example.test/box\"}]}").getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200,body.length);
            try(var out=exchange.getResponseBody()){out.write(body);}
        });
        for (String resource : new String[]{"streams", "clips", "videos"}) {
            upstream.createContext("/helix/"+resource, exchange -> {
                String json=resource.equals("streams") ? streamsPayload : "{\"data\":[]}";
                byte[] bytes=json.getBytes(StandardCharsets.UTF_8);
                exchange.sendResponseHeaders(200,bytes.length);
                try(var out=exchange.getResponseBody()){out.write(bytes);}
            });
        }
        upstream.start();
        properties.add("twitch.api-base-url",()->"http://127.0.0.1:"+upstream.getAddress().getPort()+"/helix/");
    }
    @AfterAll static void stop(){upstream.stop(0);}
    @Test void realControllerClientAndUpstreamAreWired() throws Exception {
        var response=http.getForEntity("/game?name=Minecraft",String.class);
        assertEquals(200,response.getStatusCode().value());
        assertEquals(mapper.readTree("{\"id\":\"42\",\"name\":\"Minecraft\",\"box_art_url\":\"https://example.test/box\"}"),mapper.readTree(response.getBody()));
    }
    @org.junit.jupiter.params.ParameterizedTest
    @org.junit.jupiter.params.provider.ValueSource(strings={
        "{\"data\":[{\"id\":\"s1\"}]}",
        "{\"data\":[{\"id\":\"s1\",\"user_name\":null}]}",
        "{\"data\":[{\"id\":\"s1\",\"user_name\":\"\"}]}",
        "{\"data\":[{\"id\":\"s1\",\"user_name\":\"   \"}]}"})
    void malformedStreamBroadcasterReturns502(String payload) throws Exception {
        streamsPayload=payload;
        var response=http.getForEntity("/search?game_id=42",String.class);
        assertEquals(502,response.getStatusCode().value());
        assertEquals(mapper.readTree("{\"error\":\"upstream_failure\"}"),mapper.readTree(response.getBody()));
    }
    @Test void concurrentRequestsKeepSeparateNames() throws Exception {
        try(var executor=Executors.newVirtualThreadPerTaskExecutor()) {
            var first=executor.submit(()->http.getForEntity("/game?name=alpha",String.class));
            var second=executor.submit(()->http.getForEntity("/game?name=beta",String.class));
            var a=first.get(5,TimeUnit.SECONDS);var b=second.get(5,TimeUnit.SECONDS);
            assertEquals(200,a.getStatusCode().value());assertEquals(200,b.getStatusCode().value());
            assertEquals("alpha",mapper.readTree(a.getBody()).get("name").asText());
            assertEquals("beta",mapper.readTree(b.getBody()).get("name").asText());
        }
    }
}
