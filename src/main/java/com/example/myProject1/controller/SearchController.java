package com.example.myProject1.controller;

import com.example.myProject1.entity.Item;
import com.example.myProject1.externalTwitch.TwitchClient;
import com.example.myProject1.externalTwitch.TwitchException;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/search")
public class SearchController {
    private final TwitchClient twitch;
    public SearchController(TwitchClient twitch) { this.twitch = twitch; }

    @GetMapping public Map<String, List<Item>> search(@RequestParam MultiValueMap<String, String> parameters) throws TwitchException {
        return twitch.searchItems(GameController.singleNonblank(parameters, "game_id"));
    }
}
