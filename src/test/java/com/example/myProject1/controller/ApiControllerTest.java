package com.example.myProject1.controller;

import com.example.myProject1.config.TwitchConfiguration;
import com.example.myProject1.entity.*;
import com.example.myProject1.externalTwitch.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.json.JsonCompareMode;
import org.springframework.test.web.servlet.MockMvc;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(controllers={GameController.class, SearchController.class}, properties={"twitch.client-id=", "twitch.access-token="})
@Import(TwitchConfiguration.class)
class ApiControllerTest {
    @Autowired MockMvc mvc;
    @MockitoBean TwitchClient client;
    Game game() {
        Game.Builder b=new Game.Builder(); b.setId("42");b.setName("Minecraft");b.setBoxArtUrl("https://example.test/box");return b.build();
    }
    String gameJson="{\"name\":\"Minecraft\",\"id\":\"42\",\"box_art_url\":\"https://example.test/box\"}";

    @Test void nameReturnsOneGameAndLimitReturnsList() throws Exception {
        when(client.searchGame("Minecraft")).thenReturn(game());
        when(client.topGames(10)).thenReturn(List.of(game()));
        mvc.perform(get("/game").param("name"," Minecraft ")).andExpect(status().isOk())
            .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
            .andExpect(content().json(gameJson, JsonCompareMode.STRICT));
        mvc.perform(get("/game").param("limit","10")).andExpect(status().isOk())
            .andExpect(content().json("["+gameJson+"]", JsonCompareMode.STRICT));
    }
    @Test void postEchoPreservesSnakeCaseAndOmitsNulls() throws Exception {
        mvc.perform(post("/game").contentType(MediaType.APPLICATION_JSON).content(gameJson))
            .andExpect(status().isOk()).andExpect(content().json(gameJson, JsonCompareMode.STRICT));
        mvc.perform(post("/game").contentType(MediaType.APPLICATION_JSON).content("{\"name\":\"Demo\"}"))
            .andExpect(status().isOk()).andExpect(content().json("{\"name\":\"Demo\"}", JsonCompareMode.STRICT));
        verifyNoInteractions(client);
    }
    @Test void searchReturnsExactGroupedShape() throws Exception {
        when(client.searchItems("42")).thenReturn(Map.of("STREAM",List.of(),"CLIP",List.of(),"VIDEO",List.of()));
        mvc.perform(get("/search").param("game_id"," 42 ")).andExpect(status().isOk())
            .andExpect(content().json("{\"STREAM\":[],\"CLIP\":[],\"VIDEO\":[]}", JsonCompareMode.STRICT));
    }
    @ParameterizedTest @ValueSource(strings={"/game","/game?name=","/game?name=%20","/game?limit=", "/game?limit=0", "/game?limit=101", "/game?limit=text", "/game?limit=2147483648", "/game?name=x&limit=10", "/game?name=&limit=10", "/game?name=x&name=y", "/game?limit=1&limit=2", "/search", "/search?game_id=", "/search?game_id=%20", "/search?game_id=1&game_id=2"})
    void invalidQueryNeverCallsClient(String url) throws Exception {
        mvc.perform(get(java.net.URI.create(url))).andExpect(status().isBadRequest())
            .andExpect(content().json("{\"error\":\"invalid_request\"}", JsonCompareMode.STRICT));
        verifyNoInteractions(client);
    }
    @ParameterizedTest @ValueSource(strings={"broken", "null", "[]", "123", "{\"name\":{}}", "{\"name\":123}", "{} {}"})
    void malformedOrWrongTypeBodyIsRejected(String body) throws Exception {
        mvc.perform(post("/game").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isBadRequest()).andExpect(jsonPath("$.error").value("invalid_request"));
        verifyNoInteractions(client);
    }
    @Test void typedClientFailuresHaveSanitizedStatusAndBody() throws Exception {
        when(client.searchGame("missing")).thenThrow(new TwitchException(TwitchException.Reason.NOT_FOUND));
        when(client.topGames(10)).thenThrow(new TwitchException(TwitchException.Reason.UPSTREAM_FAILURE));
        when(client.searchItems("42")).thenThrow(new TwitchException(TwitchException.Reason.UNCONFIGURED));
        mvc.perform(get("/game?name=missing")).andExpect(status().isNotFound()).andExpect(content().json("{\"error\":\"game_not_found\"}",JsonCompareMode.STRICT));
        mvc.perform(get("/game?limit=10")).andExpect(status().isBadGateway()).andExpect(content().json("{\"error\":\"upstream_failure\"}",JsonCompareMode.STRICT));
        mvc.perform(get("/search?game_id=42")).andExpect(status().isServiceUnavailable()).andExpect(content().json("{\"error\":\"twitch_unconfigured\"}",JsonCompareMode.STRICT));
    }
    @Test void unexpectedFailureDoesNotExposeInternalDetails() throws Exception {
        when(client.topGames(10)).thenThrow(new IllegalStateException("sensitive detail"));
        mvc.perform(get("/game?limit=10")).andExpect(status().isInternalServerError()).andExpect(content().json("{\"error\":\"internal_error\"}",JsonCompareMode.STRICT));
    }
    @Test void unsupportedMethodAndMediaTypeHaveExplicitErrors() throws Exception {
        mvc.perform(delete("/game")).andExpect(status().isMethodNotAllowed()).andExpect(jsonPath("$.error").value("method_not_allowed"));
        mvc.perform(post("/game").contentType(MediaType.TEXT_PLAIN).content("text")).andExpect(status().isUnsupportedMediaType()).andExpect(jsonPath("$.error").value("unsupported_media_type"));
    }
}
