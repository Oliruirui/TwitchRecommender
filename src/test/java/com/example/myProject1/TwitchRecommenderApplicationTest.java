package com.example.myProject1;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(properties = {"twitch.client-id=", "twitch.access-token="})
class TwitchRecommenderApplicationTest {
    @Test void startsWithoutTwitchCredentials() {}
}
