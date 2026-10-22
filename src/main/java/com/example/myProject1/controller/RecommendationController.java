package com.example.myProject1.controller;

import com.example.myProject1.recommendation.*;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/recommendations")
public class RecommendationController {
    private final PythonRecommendationClient python;
    public RecommendationController(PythonRecommendationClient python) { this.python = python; }

    @PostMapping(consumes="application/json", produces="application/json")
    public JsonNode recommend(@RequestBody JsonNode body) throws RecommendationUnavailableException {
        return python.recommend(RecommendationRequest.from(body));
    }
}
