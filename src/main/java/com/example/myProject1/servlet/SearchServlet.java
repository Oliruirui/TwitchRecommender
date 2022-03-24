package com.example.myProject1.servlet;

import com.example.myProject1.entity.Item;
import com.example.myProject1.externalTwitch.TwitchClient;
import com.example.myProject1.externalTwitch.TwitchException;
import com.fasterxml.jackson.databind.ObjectMapper;

import javax.servlet.*;
import javax.servlet.http.*;
import javax.servlet.annotation.*;
import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@WebServlet(name = "SearchServlet", value = "/search")
public class SearchServlet extends HttpServlet {
    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException {
        TwitchClient twitchClient = new TwitchClient();
        String gameID = request.getParameter("game_id");
        Map<String, List<Item>> searchRes = new HashMap<>();
        try {
            searchRes = twitchClient.searchItems(gameID);
        } catch (TwitchException e) {
            e.printStackTrace();
            //throw new ServletException("E");
        }
        response.setContentType("application/json");
        ObjectMapper mapper = new ObjectMapper();
        response.getWriter().println(mapper.writeValueAsString(searchRes));

    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException {

    }
}

