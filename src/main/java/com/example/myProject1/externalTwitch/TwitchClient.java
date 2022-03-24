package com.example.myProject1.externalTwitch;

import com.example.myProject1.entity.Game;
import com.example.myProject1.entity.Item;
import com.example.myProject1.entity.ItemType;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;
import org.json.JSONObject;

import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class TwitchClient {

    private static final String TOKEN = "Bearer lp9kvwywjebez1oh7e9qr7gtwzittk";
    private static final String CLIENT_ID = "ozcay8ib2cl859l2nmt7rgsa6uqdv7";
    private static final String TOP_GAME_URL = "https://api.twitch.tv/helix/games/top?first=%s";
    private static final String GAME_SEARCH_URL_TEMPLATE = "https://api.twitch.tv/helix/games?name=%s";
    private static final String STREAM_SEARCH_URL_TEMPLATE = "https://api.twitch.tv/helix/streams?game_id=%s&first=%s";
    private static final String VIDEO_SEARCH_URL_TEMPLATE = "https://api.twitch.tv/helix/videos?game_id=%s&first=%s";
    private static final String CLIP_SEARCH_URL_TEMPLATE = "https://api.twitch.tv/helix/clips?game_id=%s&first=%s";
    private static final String TWITCH_BASE_URL = "https://www.twitch.tv/";
    private static final int DEFAULT_SEARCH_LIMIT = 20;

    // Build the request URL which will be used when calling Twitch APIs,
    // e.g. https://api.twitch.tv/helix/games/top when trying to get top games.
    //https://api.twitch.tv/helix/games?name=LOL
    private String buildGameURLName(String gameName) {
        try {
            gameName = URLEncoder.encode(gameName, "UTF-8");
        } catch (UnsupportedEncodingException e) {
            e.printStackTrace();
        }
        String result = String.format(GAME_SEARCH_URL_TEMPLATE, gameName);
        return result;
    }

    // Similar to buildGameURL,
    // build Search URL that will be used when calling Twitch API.
    // e.g. https://api.twitch.tv/helix/clips?game_id=12924.
    private String buildSearchURL(String url, String gameId, int limit) {
        try {
            gameId = URLEncoder.encode(gameId, "UTF-8");
        } catch (UnsupportedEncodingException e) {
            e.printStackTrace();
        }
        if (limit > 100 || limit < 0) {
            limit = DEFAULT_SEARCH_LIMIT;
        }
        String builtURL = String.format(url, gameId, limit);
        return builtURL;
    }

//    private String buildGameURL(String url, String gameName, int limit){
//        return String.format(url, gameName == null ? limit : gameName);
//    }

    private String buildGameURLTop(int limit) {
        return String.format(TOP_GAME_URL, limit);
    }

    // Send HTTP request to Twitch Backend based on the given URL, and returns the body of the HTTP response
    // returned from Twitch backend.
    private String searchTwitch(String url) throws TwitchException {
        CloseableHttpClient httpClient = HttpClients.createDefault();
        HttpGet httpGet = new HttpGet(url);
        httpGet.setHeader("Authorization", TOKEN);
        httpGet.setHeader("Client-ID", CLIENT_ID);
        //System.out.println("URL: " + url);
        try {
            CloseableHttpResponse httpResponse = httpClient.execute(httpGet);
            String jsonString = EntityUtils.toString(httpResponse.getEntity());
            JSONObject obj = new JSONObject(jsonString);
            //System.out.println(jsonString);
            Object dataString = obj.get("data");
            //System.out.println("-------------------");
            //System.out.println("dataString: " + dataString);
            String objString = dataString.toString();
            return objString;
        } catch (Exception e) {
            e.printStackTrace();
            throw new TwitchException("Something went wrong when sending request to Twitch");
        }
    }

    // Convert JSON format data returned from Twitch to an Arraylist of Game objects
    private List<Game> getGameList(String data) throws TwitchException {
        List<Game> objectList;
        ObjectMapper mapper = new ObjectMapper();
        try {
            objectList = mapper.readValue(data, new TypeReference<List<Game>>() {
            });

        } catch (JsonProcessingException e) {
            throw new TwitchException("JsonProcessingException occured when mapping json data to object list");
        }
        return objectList;
    }

    // Similar to getGameList, convert the json data returned from Twitch to a list of Item objects.
    private List<Item> getItemList(String data) throws TwitchException {
        List<Item> result = new ArrayList<>();
        ObjectMapper mapper = new ObjectMapper();
        try{
            //System.out.println("data" + data);
            result = mapper.readValue(data, new TypeReference<List<Item>>() {
            });
        }catch (JsonProcessingException e){
            //throw new TwitchException("JsonProcessingException occured when mapping json data to Item list");
            e.printStackTrace();
        }
        return result;
    }

    // Returns the top x streams based on game ID.
    private List<Item> searchStreams(String gameId, int limit) throws TwitchException {
        String searchStreamsURL = buildSearchURL(STREAM_SEARCH_URL_TEMPLATE, gameId, limit);
        //System.out.println("url" + searchStreamsURL);
        String data = searchTwitch(searchStreamsURL);
        List<Item> streamList = getItemList(data);
        for (Item streamItem : streamList){
            streamItem.setUrl(TWITCH_BASE_URL + streamItem.getBroadcasterName());
            streamItem.setGameID(gameId);
            streamItem.setType(ItemType.STREAM);
            System.out.println("StreamItem: " + streamItem);
        }
        return streamList;
    }


    // Returns the top x clips based on game ID.
    private List<Item> searchClips(String gameId, int limit) throws TwitchException {
        String searchClipsURL = buildSearchURL(CLIP_SEARCH_URL_TEMPLATE, gameId, limit);
        String searchClipsURLData = searchTwitch(searchClipsURL);
        List<Item> clipsList = getItemList(searchClipsURLData);
        for (Item clipItem : clipsList){
            clipItem.setGameID(gameId);
            clipItem.setType(ItemType.CLIP);
        }
        return clipsList;
    }

    // Returns the top x videos based on game ID.
    private List<Item> searchVideos(String gameId, int limit) throws TwitchException {
        String searchVideosURL = buildSearchURL(VIDEO_SEARCH_URL_TEMPLATE, gameId, limit);
        String searchVideosURLData = searchTwitch(searchVideosURL);
        List<Item> videoList = getItemList(searchVideosURLData);
        for (Item videoItem : videoList){
            videoItem.setGameID(gameId);
            videoItem.setType(ItemType.VIDEO);
        }
        return videoList;
    }

    public List<Item> searchByType(String gameId, ItemType type, int limit) throws TwitchException {
        if (type == ItemType.STREAM){
            return searchStreams(gameId, limit);
        }else if (type == ItemType.VIDEO){
            return searchVideos(gameId, limit);
        }else if (type == ItemType.CLIP){
            return searchClips(gameId, limit);
        }

        throw new TwitchException("type of content is not stream, video or clip, please put a valid type");
    }

    public Map<String, List<Item>> searchItems(String gameId) throws TwitchException {
        Map<String, List<Item>> searchResult = new HashMap<>();
        for (ItemType type : ItemType.values()){
            List<Item> searchResultList = searchByType(gameId, type, DEFAULT_SEARCH_LIMIT);
            searchResult.put(type.toString(), searchResultList);
            //System.out.println(searchResult.get(ItemType.STREAM.toString()));
        }
        return searchResult;
    }


        // Integrate search() and getGameList() together, returns the top x popular games from Twitch.
    public List<Game> topGames(int limit) throws TwitchException {
        //System.out.println(searchTwitch(buildGameURLTop(TOP_GAME_URL, limit)));
        String urlToSearch = buildGameURLTop(limit);
        String jsonObjects = searchTwitch(urlToSearch);
        List<Game> listOfGames = getGameList(jsonObjects);
        return listOfGames;
    }

    // Integrate search() and getGameList() together, returns the dedicated game based on the game name.
    public Game searchGame(String gameName) throws TwitchException {
        String urlSearchGame = buildGameURLName(gameName);
        String jsonObjects = searchTwitch(urlSearchGame);
        List<Game> listOfGames = getGameList(jsonObjects);
        try {
            return listOfGames.get(0);
        } catch (IndexOutOfBoundsException e) {
            throw new TwitchException("Game search result is null");
        }
    }


}