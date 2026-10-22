package com.example.myProject1.recommendation;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.*;
import java.net.URI;
import java.net.http.HttpClient;
import java.time.Duration;

@Configuration
public class RecommendationConfiguration {
    @Bean(destroyMethod="close") public HttpClient recommendationHttpClient(
            @Value("${recommender.connect-timeout-ms}") long connect,
            @Value("${recommender.request-timeout-ms}") long deadline) {
        if (connect <= 0 || deadline <= 0 || connect > deadline) throw new IllegalArgumentException("Invalid recommendation timeouts");
        return HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connect))
            .followRedirects(HttpClient.Redirect.NEVER).build();
    }
    @Bean public PythonRecommendationClient pythonRecommendationClient(
            @Qualifier("recommendationHttpClient") HttpClient http, ObjectMapper mapper,
            @Value("${recommender.base-url}") URI base,
            @Value("${recommender.request-timeout-ms}") long deadline) {
        return new PythonRecommendationClient(http,mapper,base,deadline);
    }
}
