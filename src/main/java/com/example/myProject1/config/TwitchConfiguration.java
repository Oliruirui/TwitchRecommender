package com.example.myProject1.config;

import com.example.myProject1.externalTwitch.TwitchClient;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.jackson.Jackson2ObjectMapperBuilderCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import java.net.URI;
import java.net.http.HttpClient;
import java.time.Duration;

@Configuration
public class TwitchConfiguration {
    @Bean public Jackson2ObjectMapperBuilderCustomizer strictJson() {
        return builder -> builder.featuresToDisable(MapperFeature.ALLOW_COERCION_OF_SCALARS)
            .featuresToEnable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
    }

    @Bean(destroyMethod = "close") public HttpClient twitchHttpClient() {
        return HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(1))
            .followRedirects(HttpClient.Redirect.NEVER).build();
    }

    @Bean public TwitchClient twitchClient(HttpClient twitchHttpClient, ObjectMapper mapper,
            @Value("${twitch.api-base-url}") URI base,
            @Value("${twitch.client-id}") String clientId,
            @Value("${twitch.access-token}") String token) {
        return new TwitchClient(twitchHttpClient, mapper, base, clientId, token);
    }
}
