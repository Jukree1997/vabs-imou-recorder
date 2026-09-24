package com.vabs.imourecorder;

import org.json.JSONException;
import org.json.JSONObject;

final class DownloadJob {
    final String apiHost;
    final String accessToken;
    final String playToken;
    final String deviceId;
    final int channelId;
    final String recordId;
    final String deviceCode;
    final long beginTimeMillis;
    final int recordType;
    final int speed;
    final String productId;
    final boolean tlsEnable;
    final long expectedBytes;
    final String outputName;

    private DownloadJob(JSONObject json) throws JSONException {
        if (json.getInt("schemaVersion") != 1) {
            throw new JSONException("Unsupported job schema");
        }
        apiHost = required(json, "apiHost");
        accessToken = required(json, "accessToken");
        playToken = required(json, "playToken");
        deviceId = required(json, "deviceId");
        channelId = json.getInt("channelId");
        recordId = required(json, "recordId");
        deviceCode = required(json, "deviceCode");
        beginTimeMillis = json.getLong("beginTimeMillis");
        recordType = json.optInt("recordType", 1);
        speed = json.optInt("speed", 2);
        productId = json.optString("productId", "");
        tlsEnable = json.optBoolean("tlsEnable", false);
        expectedBytes = Math.max(0, json.optLong("expectedBytes", 0));
        outputName = required(json, "outputName");
        if (!outputName.matches("(?:[0-9]{4}-[0-9]{4}|[0-9]{6}-[0-9]{6}-[0-9]{4})\\.mp4")) {
            throw new JSONException("Unsafe output filename");
        }
    }

    static DownloadJob fromJson(String text) throws JSONException {
        return new DownloadJob(new JSONObject(text));
    }

    private static String required(JSONObject json, String name) throws JSONException {
        String value = json.getString(name).trim();
        if (value.isEmpty()) {
            throw new JSONException(name + " is empty");
        }
        return value;
    }
}
