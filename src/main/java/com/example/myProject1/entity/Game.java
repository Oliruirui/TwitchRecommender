package com.example.myProject1.entity;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;

//@JsonIgnoreProperties(ignoreUnknown = true)
@JsonInclude(JsonInclude.Include.NON_NULL)
@JsonDeserialize(builder = Game.Builder.class)
public class Game {
    @JsonProperty
    private final String name;

    @JsonProperty
    private final String id;

    @JsonProperty("box_art_url")
    private final String boxArtURL;

//    @JsonCreator
//    public Game(@JsonProperty("name") String name, @JsonProperty("id") String id, @JsonProperty("box_art_url")String boxArtURL) {
//        this.name = name;
//        this.id = id;
//        this.boxArtURL = boxArtURL;
//    }


    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Builder{
        @JsonProperty
        String name;
        @JsonProperty
        String id;
        @JsonProperty("box_art_url")
        String boxArtURL;

        public void setName(String name) {
            this.name = name;
        }

        public void setId(String id) {
            this.id = id;
        }

        public void setBoxArtUrl(String boxArtURL) {
            this.boxArtURL = boxArtURL;
        }

        public Builder(){

        }

        public Game build(){
            Game game = new Game(this);
            return game;
        }
    }

    public String getName() {
        return name;
    }

    public String getId() {
        return id;
    }

    public String getBoxArtURL() {
        return boxArtURL;
    }

    public Game(Builder b){
        this.name = b.name;
        this.id = b.id;
        this.boxArtURL = b.boxArtURL;
    }
}

