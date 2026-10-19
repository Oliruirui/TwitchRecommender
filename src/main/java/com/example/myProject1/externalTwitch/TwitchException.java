package com.example.myProject1.externalTwitch;

/** Public failure categories; never carries credentials or an upstream response body. */
public class TwitchException extends Exception {
    public enum Reason { UNCONFIGURED, NOT_FOUND, UPSTREAM_FAILURE }
    private final Reason reason;

    public TwitchException(Reason reason) {
        super(reason.name());
        this.reason = reason;
    }
    public Reason getReason() { return reason; }
}
