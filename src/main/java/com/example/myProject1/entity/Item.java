package com.example.myProject1.entity;


import com.fasterxml.jackson.annotation.*;
import lombok.Builder;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import lombok.extern.jackson.Jacksonized;

@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
//@JsonDeserialize
//@JsonDeserialize(builder = Item.Builder.class)
public class Item {
    @Override
    public String toString() {
        return "Item{" +
                "id='" + id + '\'' +
                ", title='" + title + '\'' +
                ", broadcasterName='" + broadcasterName + '\'' +
                ", url='" + url + '\'' +
                ", thumbnailURL='" + thumbnailURL + '\'' +
                ", gameID='" + gameID + '\'' +
                ", type=" + type +
                '}' + '\n';
    }

    @JsonProperty("id")
    private final String id;

    @JsonProperty("title")
    private final String title;

//    @JsonProperty("viewer_count")
//    private String viewerCount;

    @JsonProperty("broadcaster_name")
    @JsonAlias({"user_name"})
    private String broadcasterName;

    @JsonProperty("url")
    private String url;

    @JsonProperty("thumbnail_url")
    private final String thumbnailURL;

    @JsonProperty("game_id")
    private String gameID;

    @JsonProperty("item_type")
    private ItemType type;

    public String getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    public String getBroadcasterName() {
        return broadcasterName;
    }

    public String getUrl() {
        return url;
    }

    public String getThumbnailURL() {
        return thumbnailURL;
    }

    public String getGameID() {
        return gameID;
    }

    public ItemType getType() {
        return type;
    }

    public void setBroadcasterName(String broadcasterName) {
        this.broadcasterName = broadcasterName;
    }

    public void setUrl(String url) {
        this.url = url;
    }

    public void setGameID(String gameID) {
        this.gameID = gameID;
    }

    public void setType(ItemType type) {
        this.type = type;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    @Builder @Jacksonized
    public Item(String id, String title, @JsonProperty("broadcaster_name") @JsonAlias({"user_name"}) String broadcasterName,
                String url,  @JsonProperty("thumbnail_url")String thumbnailURL) {
        this.id = id;
        this.title = title;
        this.broadcasterName = broadcasterName;
        this.url = url;
        this.thumbnailURL = thumbnailURL;

    }
}
