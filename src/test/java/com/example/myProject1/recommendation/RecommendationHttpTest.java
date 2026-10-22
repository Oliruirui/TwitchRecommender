package com.example.myProject1.recommendation;

import com.fasterxml.jackson.databind.*;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
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
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,
 properties={"twitch.client-id=","twitch.access-token=","recommender.request-timeout-ms=400","recommender.connect-timeout-ms=100"})
@DirtiesContext
class RecommendationHttpTest {
    static HttpServer python;
    static AtomicInteger calls=new AtomicInteger();
    static volatile String received,method,contentType;
    static volatile int status;
    static volatile String response;
    static volatile String delay;
    static final String PERSONALIZED="{\"request_id\":\"d25a2a52-9afe-4ee3-9505-89e426d78486\",\"model_version\":\"test-v1\",\"method\":\"two_tower\",\"fallback_reason\":null,\"items\":[{\"channel_id\":\"12\",\"channel_name\":\"example\",\"retrieval_score\":1.25}]}";
    @Autowired TestRestTemplate api;
    @Autowired ObjectMapper mapper;

    @DynamicPropertySource static void configure(DynamicPropertyRegistry registry) throws Exception {
        python=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        python.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
        python.createContext("/v1/recommendations",exchange->{
            calls.incrementAndGet();method=exchange.getRequestMethod();contentType=exchange.getRequestHeaders().getFirst("Content-Type");
            received=new String(exchange.getRequestBody().readAllBytes(),StandardCharsets.UTF_8);
            String waiting=delay;
            try {
                if("headers".equals(waiting))Thread.sleep(1000);
                byte[] bytes=response.getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type","application/json");
                exchange.sendResponseHeaders(status,bytes.length);
                if("body".equals(waiting)){exchange.getResponseBody().flush();Thread.sleep(1000);}
                try(var out=exchange.getResponseBody()){out.write(bytes);}
            } catch(Exception ignored){exchange.close();}
        });
        python.start();
        registry.add("recommender.base-url",()->"http://127.0.0.1:"+python.getAddress().getPort());
    }
    @AfterAll static void stop(){python.stop(0);}
    @BeforeEach void reset(){calls.set(0);status=200;response=PERSONALIZED;delay="none";}
    ResponseEntity<String> request(String body){
        var headers=new HttpHeaders();headers.setContentType(MediaType.APPLICATION_JSON);
        return api.postForEntity("/api/recommendations",new HttpEntity<>(body,headers),String.class);
    }
    @Test void forwardsNormalizedIdentityAndDefaultKPreservingResponse() throws Exception {
        var result=request("{\"user_id\":\" 1 \"}");
        assertEquals(200,result.getStatusCode().value());
        assertEquals(mapper.readTree(PERSONALIZED),mapper.readTree(result.getBody()));
        assertEquals(mapper.readTree("{\"user_id\":\"1\",\"k\":10}"),mapper.readTree(received));
        assertEquals("POST",method);assertTrue(contentType.startsWith("application/json"));assertEquals(1,calls.get());
    }
    @ParameterizedTest @ValueSource(strings={"unknown_user","retrieval_error"})
    void pythonPopularityPassesThrough(String reason) throws Exception {
        response=PERSONALIZED.replace("two_tower","popular").replace("\"fallback_reason\":null","\"fallback_reason\":\""+reason+"\"").replace("\"retrieval_score\":1.25","\"retrieval_score\":null");
        var result=request("{\"user_id\":\"new-user\",\"k\":1}");
        assertEquals(200,result.getStatusCode().value());assertEquals(mapper.readTree(response),mapper.readTree(result.getBody()));
        assertEquals(1,mapper.readTree(received).get("k").asInt());
    }
    @ParameterizedTest @ValueSource(strings={"{}","null","[]","{\"user_id\":1}","{\"user_id\":null}","{\"user_id\":\" \"}","{\"user_id\":\"1\",\"k\":0}","{\"user_id\":\"1\",\"k\":201}","{\"user_id\":\"1\",\"k\":1.0}","{\"user_id\":\"1\",\"k\":\"10\"}","{\"user_id\":\"1\",\"k\":true}","{\"user_id\":\"1\",\"k\":null}","{\"user_id\":\"1\",\"k\":999999999999}","broken"})
    void invalidInputNeverCallsPython(String body) throws Exception {
        var result=request(body);assertEquals(400,result.getStatusCode().value());
        assertEquals(mapper.readTree("{\"error\":\"invalid_request\"}"),mapper.readTree(result.getBody()));assertEquals(0,calls.get());
    }
    @Test void identityLengthUsesUnicodeCodePoints() throws Exception {
        assertEquals(200,request(mapper.writeValueAsString(java.util.Map.of("user_id","😀".repeat(128)))).getStatusCode().value());
        calls.set(0);
        assertEquals(400,request(mapper.writeValueAsString(java.util.Map.of("user_id","😀".repeat(129)))).getStatusCode().value());
        assertEquals(0,calls.get());
    }
    @ParameterizedTest @ValueSource(strings={"broken","{}","null","[]"})
    void malformedPythonResponseReturns503(String invalid) throws Exception {response=invalid;unavailable();}
    @Test void downstreamStatusDoesNotLeakBodyOrRetry() throws Exception {status=503;response="private upstream detail";unavailable();assertEquals(1,calls.get());}
    @ParameterizedTest @ValueSource(strings={"headers","body"})
    void deadlineBoundsCompleteResponse(String mode) throws Exception {
        delay=mode;long start=System.nanoTime();unavailable();
        assertTrue(TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-start)<900);assertEquals(1,calls.get());
    }
    @ParameterizedTest @ValueSource(strings={"method","request_id","model_version","fallback_reason","items"})
    void missingResponseFieldsAreRejected(String key) throws Exception {
        var tree=(com.fasterxml.jackson.databind.node.ObjectNode)mapper.readTree(response);tree.remove(key);response=tree.toString();unavailable();
    }
    @Test void duplicateIdsAndNonfiniteScoresAreRejected() throws Exception {
        var tree=(com.fasterxml.jackson.databind.node.ObjectNode)mapper.readTree(PERSONALIZED);
        var items=(com.fasterxml.jackson.databind.node.ArrayNode)tree.get("items");items.add(items.get(0).deepCopy());response=tree.toString();unavailable();
        response=PERSONALIZED.replace("1.25","1e999");unavailable();
    }
    @ParameterizedTest @ValueSource(strings={"bad_uuid","bad_version","bad_method","bad_reason","empty_items","blank_name","negative_id","string_score","missing_score","ascending_scores","too_many_items"})
    void invalidResponseContractReturns503(String change) throws Exception {
        var tree=(com.fasterxml.jackson.databind.node.ObjectNode)mapper.readTree(PERSONALIZED);
        var items=(com.fasterxml.jackson.databind.node.ArrayNode)tree.get("items");
        var item=(com.fasterxml.jackson.databind.node.ObjectNode)items.get(0);
        switch(change) {
            case "bad_uuid" -> tree.put("request_id","invalid");
            case "bad_version" -> tree.put("model_version","");
            case "bad_method" -> tree.put("method","other");
            case "bad_reason" -> tree.put("fallback_reason","unknown_user");
            case "empty_items" -> items.removeAll();
            case "blank_name" -> item.put("channel_name"," ");
            case "negative_id" -> item.put("channel_id","-1");
            case "string_score" -> item.put("retrieval_score","1.25");
            case "missing_score" -> item.remove("retrieval_score");
            case "ascending_scores" -> {var next=item.deepCopy();next.put("channel_id","13");next.put("retrieval_score",2);items.add(next);}
            case "too_many_items" -> {for(int i=0;i<10;i++){var next=item.deepCopy();next.put("channel_id",Integer.toString(20+i));items.add(next);}}
        }
        response=tree.toString();unavailable();
    }
    @ParameterizedTest @org.junit.jupiter.params.provider.ValueSource(ints={1,200})
    void forwardsBoundaryK(int k) throws Exception {
        assertEquals(200,request("{\"user_id\":\"1\",\"k\":"+k+"}").getStatusCode().value());
        assertEquals(k,mapper.readTree(received).get("k").asInt());
    }
    void unavailable() throws Exception {
        var result=request("{\"user_id\":\"1\",\"k\":10}");assertEquals(503,result.getStatusCode().value());
        assertEquals(mapper.readTree("{\"error\":\"recommendation_unavailable\"}"),mapper.readTree(result.getBody()));
    }
}
