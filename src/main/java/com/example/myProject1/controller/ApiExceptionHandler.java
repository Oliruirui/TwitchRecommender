package com.example.myProject1.controller;

import com.example.myProject1.externalTwitch.TwitchException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;
import java.util.Map;

@RestControllerAdvice
public class ApiExceptionHandler extends ResponseEntityExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(TwitchException.class)
    public ResponseEntity<Object> twitchFailure(TwitchException failure) {
        return switch (failure.getReason()) {
            case UNCONFIGURED -> error(503, "twitch_unconfigured");
            case NOT_FOUND -> error(404, "game_not_found");
            case UPSTREAM_FAILURE -> error(502, "upstream_failure");
        };
    }
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Object> invalidRequest() { return error(400, "invalid_request"); }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Object> unexpected(Exception failure) {
        log.error("Unexpected API failure ({})", failure.getClass().getSimpleName());
        return error(500, "internal_error");
    }

    @Override protected ResponseEntity<Object> handleExceptionInternal(Exception ex, Object body,
            HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        String code = switch (status.value()) {
            case 400 -> "invalid_request";
            case 404 -> "not_found";
            case 405 -> "method_not_allowed";
            case 406 -> "not_acceptable";
            case 415 -> "unsupported_media_type";
            default -> "internal_error";
        };
        return super.handleExceptionInternal(ex, Map.of("error", code), headers, status, request);
    }
    private ResponseEntity<Object> error(int status, String code) {
        return ResponseEntity.status(status).body(Map.of("error", code));
    }
}
