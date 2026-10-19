package com.example.myProject1.externalTwitch;

import com.example.myProject1.entity.Game;
import com.example.myProject1.entity.Item;
import com.example.myProject1.entity.ItemType;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

import static com.example.myProject1.externalTwitch.TwitchException.Reason.*;

/** Stateless operations on Twitch's Helix API; all request data stays local. */
public class TwitchClient {
    private static final int DEFAULT_SEARCH_LIMIT = 20;
    private final HttpClient httpClient;
    private final ObjectMapper mapper;
    private final URI base;
    private final String clientId;
    private final String accessToken;

    public TwitchClient(HttpClient httpClient, ObjectMapper objectMapper, URI apiBaseUri,
                        String clientId, String accessToken) {
        this.httpClient = httpClient;
        this.mapper = objectMapper;
        this.base = URI.create(apiBaseUri.toString().replaceAll("/+$", "") + "/");
        this.clientId = clientId == null ? "" : clientId.strip();
        this.accessToken = accessToken == null ? "" : accessToken.strip();
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private JsonNode data(String path) throws TwitchException {
        if (clientId.isBlank() || accessToken.isBlank()) throw new TwitchException(UNCONFIGURED);
        CompletableFuture<HttpResponse<String>> responseFuture = null;
        try {
            HttpRequest request = HttpRequest.newBuilder(base.resolve(path))
                .header("Client-Id", clientId).header("Authorization", "Bearer " + accessToken)
                .timeout(Duration.ofSeconds(2)).GET().build();
            // Bound the entire response, including a body that stalls after headers.
            responseFuture = httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            HttpResponse<String> response = responseFuture.get(2, TimeUnit.SECONDS);
            if (response.statusCode() < 200 || response.statusCode() >= 300) throw new TwitchException(UPSTREAM_FAILURE);
            JsonNode envelope = mapper.readTree(response.body());
            if (envelope == null || !envelope.isObject() || !envelope.path("data").isArray()) throw new TwitchException(UPSTREAM_FAILURE);
            return envelope.get("data");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new TwitchException(UPSTREAM_FAILURE);
        } catch (IOException | IllegalArgumentException | ExecutionException | TimeoutException e) {
            throw new TwitchException(UPSTREAM_FAILURE);
        } finally {
            if (responseFuture != null && !responseFuture.isDone()) responseFuture.cancel(true);
        }
    }

    private <T> List<T> parse(JsonNode data, Class<T> type) throws TwitchException {
        List<T> result = new ArrayList<>();
        for (JsonNode row : data) {
            if (!row.isObject() || !row.path("id").isTextual() || row.path("id").asText().isBlank()
                || (type == Game.class && !row.path("name").isTextual())) throw new TwitchException(UPSTREAM_FAILURE);
            try {
                result.add(mapper.treeToValue(row, type));
            } catch (IOException | IllegalArgumentException e) {
                throw new TwitchException(UPSTREAM_FAILURE);
            }
        }
        return result;
    }

    public List<Game> topGames(int limit) throws TwitchException {
        return parse(data("games/top?first=" + limit), Game.class);
    }

    public Game searchGame(String gameName) throws TwitchException {
        List<Game> games = parse(data("games?name=" + encode(gameName)), Game.class);
        if (games.isEmpty()) throw new TwitchException(NOT_FOUND);
        return games.getFirst();
    }

    public List<Item> searchByType(String gameId, ItemType type, int limit) throws TwitchException {
        String resource = switch (type) {
            case STREAM -> "streams";
            case CLIP -> "clips";
            case VIDEO -> "videos";
        };
        List<Item> items = parse(data(resource + "?game_id=" + encode(gameId) + "&first=" + limit), Item.class);
        for (Item item : items) {
            item.setGameID(gameId);
            item.setType(type);
            if (type == ItemType.STREAM) {
                if (item.getBroadcasterName() == null || item.getBroadcasterName().isBlank()) {
                    throw new TwitchException(UPSTREAM_FAILURE);
                }
                item.setUrl("https://www.twitch.tv/" + item.getBroadcasterName());
            }
        }
        return items;
    }

    public Map<String, List<Item>> searchItems(String gameId) throws TwitchException {
        Map<String, List<Item>> result = new LinkedHashMap<>();
        for (ItemType type : ItemType.values()) result.put(type.name(), searchByType(gameId, type, DEFAULT_SEARCH_LIMIT));
        return result;
    }
}
