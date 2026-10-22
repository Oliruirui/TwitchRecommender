package com.example.myProject1.recommendation;

import com.fasterxml.jackson.databind.json.JsonMapper;
import org.junit.jupiter.api.Test;
import java.net.*;
import java.net.http.*;
import java.util.concurrent.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class PythonRecommendationClientTest {
    @Test void connectionFailureUsesUnavailableError() throws Exception {
        int port;
        try(var socket=new java.net.ServerSocket(0,0,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
        try(var transport=HttpClient.newHttpClient()) {
            var client=new PythonRecommendationClient(transport,new JsonMapper(),URI.create("http://127.0.0.1:"+port),400);
            assertThrows(RecommendationUnavailableException.class,()->client.recommend(new RecommendationRequest("1",10)));
        }
    }
    @Test void interruptionCancelsPendingRequestAndRestoresFlag() throws Exception {
        var pending=new CompletableFuture<HttpResponse<String>>();
        HttpClient transport=mock(HttpClient.class);
        when(transport.sendAsync(any(HttpRequest.class),org.mockito.ArgumentMatchers.<HttpResponse.BodyHandler<String>>any())).thenReturn(pending);
        var client=new PythonRecommendationClient(transport,new JsonMapper(),URI.create("http://127.0.0.1"),400);
        Thread.currentThread().interrupt();
        try {
            assertThrows(RecommendationUnavailableException.class,()->client.recommend(new RecommendationRequest("1",10)));
            assertTrue(Thread.currentThread().isInterrupted());
            assertTrue(pending.isCancelled());
        } finally {Thread.interrupted();}
    }
}
