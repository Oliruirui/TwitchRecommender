package com.example.myProject1.recommendation;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.MediaType;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;

/** Calls the existing Python runtime; never trains or adds a second popularity fallback. */
public class PythonRecommendationClient {
    private final HttpClient http;
    private final ObjectMapper mapper;
    private final URI endpoint;
    private final long deadlineMs;

    public PythonRecommendationClient(HttpClient http, ObjectMapper mapper, URI base, long deadlineMs) {
        this.http = http; this.mapper = mapper; this.deadlineMs = deadlineMs;
        if (!("http".equals(base.getScheme()) || "https".equals(base.getScheme())) || base.getHost() == null
                || base.getUserInfo() != null || base.getQuery() != null || base.getFragment() != null || deadlineMs <= 0) {
            throw new IllegalArgumentException("Invalid recommendation endpoint configuration");
        }
        endpoint = URI.create(base.toString().replaceAll("/+$", "") + "/v1/recommendations");
    }

    public JsonNode recommend(RecommendationRequest input) throws RecommendationUnavailableException {
        CompletableFuture<HttpResponse<String>> pending = null;
        try {
            var request = HttpRequest.newBuilder(endpoint).header("Content-Type", "application/json")
                .timeout(Duration.ofMillis(deadlineMs))
                .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(input))).build();
            pending = http.sendAsync(request, HttpResponse.BodyHandlers.ofString());
            var response = pending.get(deadlineMs, TimeUnit.MILLISECONDS);
            if (response.statusCode() != 200 || !MediaType.APPLICATION_JSON.isCompatibleWith(
                    MediaType.parseMediaType(response.headers().firstValue("Content-Type").orElse("")))) {
                throw new RecommendationUnavailableException();
            }
            return validate(mapper.readTree(response.body()), input.k());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RecommendationUnavailableException();
        } catch (RecommendationUnavailableException e) {
            throw e;
        } catch (Exception e) {
            // Do not disclose downstream bodies, request data or transport exception messages.
            throw new RecommendationUnavailableException();
        } finally {
            if (pending != null && !pending.isDone()) pending.cancel(true);
        }
    }

    private JsonNode validate(JsonNode result, int k) throws RecommendationUnavailableException {
        if (result == null || !result.isObject()) throw new RecommendationUnavailableException();
        for (String key : List.of("request_id", "model_version", "method", "fallback_reason", "items")) {
            if (!result.has(key)) throw new RecommendationUnavailableException();
        }
        if (!result.get("request_id").isTextual() || !result.get("model_version").isTextual()
                || !result.get("method").isTextual()) throw new RecommendationUnavailableException();
        String id = result.get("request_id").textValue();
        if (!UUID.fromString(id).toString().equalsIgnoreCase(id)
                || !result.get("model_version").textValue().matches("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")) {
            throw new RecommendationUnavailableException();
        }
        String method = result.get("method").textValue();
        JsonNode reason = result.get("fallback_reason");
        boolean personalized = "two_tower".equals(method);
        if (personalized ? !reason.isNull() : !("popular".equals(method) && reason.isTextual()
                && Set.of("unknown_user", "retrieval_error").contains(reason.textValue()))) {
            throw new RecommendationUnavailableException();
        }
        var items = result.get("items");
        if (!items.isArray() || items.isEmpty() || items.size() > k) throw new RecommendationUnavailableException();
        Set<String> ids = new HashSet<>();
        double previous = Double.POSITIVE_INFINITY;
        for (JsonNode item : items) {
            if (!item.isObject() || !item.path("channel_id").isTextual() || !item.path("channel_name").isTextual()
                    || !item.has("retrieval_score") || item.get("channel_name").textValue().isBlank()
                    || !item.get("channel_id").textValue().matches("0|[1-9][0-9]*")
                    || !ids.add(item.get("channel_id").textValue())) throw new RecommendationUnavailableException();
            JsonNode score = item.get("retrieval_score");
            if (personalized) {
                if (!score.isNumber() || !Double.isFinite(score.doubleValue()) || score.doubleValue() > previous) {
                    throw new RecommendationUnavailableException();
                }
                previous = score.doubleValue();
            } else if (!score.isNull()) throw new RecommendationUnavailableException();
        }
        return result;
    }
}
