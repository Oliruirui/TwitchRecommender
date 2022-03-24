package com.example.myProject1.servlet;

import com.example.myProject1.entity.Game;
import com.example.myProject1.entity.Item;
import com.example.myProject1.externalTwitch.TwitchClient;
import com.example.myProject1.externalTwitch.TwitchException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.commons.io.IOUtils;
import org.json.JSONObject;

import javax.servlet.*;
import javax.servlet.http.*;
import javax.servlet.annotation.*;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.Enumeration;
import java.util.List;

@WebServlet(name = "GameServlet", value = "/game")
public class GameServlet extends HttpServlet {

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException {
//        response.setContentType("application/json");
//        ObjectMapper mapper = new ObjectMapper();
//
//        Game.Builder builder = new Game.Builder();
//        builder.setName("World of Warcraft");
//        //builder.setId("1");
//        builder.setBoxArtUrl("[San Francisco](https://static-cdn.jtvnw.net/ttv-boxart/Warcraft%20III-{width}x{height}.jpg)");
//
//        Game game = builder.build();
//        //JSONObject obj = new JSONObject();
//
//        response.getWriter().println(mapper.writeValueAsString(game));
        //--------------------
        // test
        Item newItem = Item.builder().id("Stehpen").build();
        //System.out.println(newItem.getId());
        //---------------------
        //by name
        String name = request.getParameter("name");
        //by limit
        String limit = request.getParameter("limit");

        TwitchClient twitchClient = new TwitchClient();
        response.setContentType("application/json");
        ObjectMapper mapper = new ObjectMapper();
        if (name == null && limit == null){
            //throw new ServletException("url is invalid, null name and null limit");
            response.getWriter().println("url is invalid, null name and null limit");
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }else if (name == null){
            //search by limit
            try {
                List<Game> topGames = twitchClient.topGames(Integer.parseInt(limit));
                response.getWriter().println(mapper.writeValueAsString(topGames));
            } catch (TwitchException e) {
                e.printStackTrace();
            }
        }else if (limit == null){
            //search by name
            try {
                Game targetGame = twitchClient.searchGame(name);
                response.getWriter().println(mapper.writeValueAsString(targetGame));
            } catch (TwitchException e) {
                e.printStackTrace();
            }
        }else{
            //throw new ServletException("url is invalid, name and limit cannot be searched together");
            response.getWriter().println("url is invalid, name and limit cannot be searched together");
            response.setStatus(HttpServletResponse.SC_INTERNAL_SERVER_ERROR);
        }




    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException {
//        BufferedReader reader = request.getReader();
//        String tmp = IOUtils.toString(reader);
//        JSONObject obj = new JSONObject(tmp);
//        System.out.println("Name is: " + obj.getString("name"));
//        System.out.println("Developer is: " + obj.getString("developer"));
//        System.out.println("Release_time: " + obj.getString("release_time"));
//        System.out.println("Website: " + obj.getString("website"));
//        System.out.println("Price: " + obj.getString("price"));

          BufferedReader reader = request.getReader();
          String tmp = IOUtils.toString(reader);
          ObjectMapper mapper = new ObjectMapper();
          Game game = mapper.readValue(tmp, Game.class);
          response.getWriter().println(mapper.writeValueAsString(game));
          System.out.println("name: " + game.getName() + "\nid: "
                  + game.getId() + "\nboxArtURL: " + game.getBoxArtURL());

//        JSONObject res = new JSONObject();
//        res.put("status", "ok");
//        response.setContentType("application/json");
//        response.getWriter().println(res);

//        BufferedReader reader = request.getReader();
//        String tmp = IOUtils.toString(reader);
//        ObjectMapper om = new ObjectMapper();
//        Game game = om.readValue(tmp, Game.class);
//
//        ObjectMapper mapper = new ObjectMapper();
//        String gameRes = mapper.writeValueAsString(game);
//        JSONObject obj = new JSONObject(gameRes);
//        response.setContentType("application/json");
//        response.getWriter().println(obj);
    }
}
