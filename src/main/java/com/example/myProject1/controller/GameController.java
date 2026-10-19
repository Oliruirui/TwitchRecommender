package com.example.myProject1.controller;

import com.example.myProject1.entity.Game;
import com.example.myProject1.externalTwitch.TwitchClient;
import com.example.myProject1.externalTwitch.TwitchException;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/game")
public class GameController {
    private final TwitchClient twitch;
    public GameController(TwitchClient twitch) { this.twitch = twitch; }

    @GetMapping public Object getGame(@RequestParam MultiValueMap<String, String> parameters) throws TwitchException {
        boolean name = parameters.containsKey("name"), limit = parameters.containsKey("limit");
        if (name == limit) throw new IllegalArgumentException();
        String value = singleNonblank(parameters, name ? "name" : "limit");
        if (name) return twitch.searchGame(value);
        int count;
        try { count = Integer.parseInt(value); }
        catch (NumberFormatException e) { throw new IllegalArgumentException(); }
        if (count < 1 || count > 100) throw new IllegalArgumentException();
        return twitch.topGames(count);
    }

    static String singleNonblank(MultiValueMap<String, String> parameters, String key) {
        var values = parameters.get(key);
        if (values == null || values.size() != 1 || values.getFirst() == null || values.getFirst().isBlank()) {
            throw new IllegalArgumentException();
        }
        return values.getFirst().strip();
    }

    @PostMapping(consumes="application/json") public Game echo(@RequestBody Game game) { return game; }
}
