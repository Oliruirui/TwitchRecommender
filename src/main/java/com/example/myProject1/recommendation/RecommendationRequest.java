package com.example.myProject1.recommendation;

import com.fasterxml.jackson.databind.JsonNode;

public record RecommendationRequest(String user_id, int k) {
    public static RecommendationRequest from(JsonNode body) {
        if (body == null || !body.isObject() || !body.path("user_id").isTextual()) throw new IllegalArgumentException();
        String user = body.get("user_id").textValue().strip().replaceAll("(?U)^\\s+|\\s+$", "").strip();
        if (user.isEmpty() || user.codePointCount(0,user.length()) > 128) throw new IllegalArgumentException();
        int k = 10;
        if (body.has("k")) {
            JsonNode value = body.get("k");
            if (!value.isIntegralNumber() || !value.canConvertToInt()) throw new IllegalArgumentException();
            k = value.intValue();
        }
        if (k < 1 || k > 200) throw new IllegalArgumentException();
        return new RecommendationRequest(user, k);
    }
}
