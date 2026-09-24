package com.vabs.imourecorder;

import android.app.Activity;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.lc.opensdk.api.InitParams;
import com.lc.opensdk.api.LCOpenSDK_Api;
import com.lc.opensdk.listener.LCOpenSDK_DownloadListener;
import com.lc.opensdk.media.LCOpenSDK_Download;
import com.lc.opensdk.media.LCOpenSDK_StatusCode;

import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/** Minimal one-job OpenSDK runner controlled by the Linux coordinator. */
public final class MainActivity extends Activity {
    private static final int DOWNLOAD_INDEX = 0;

    private TextView statusView;
    private ProgressBar progressBar;
    private long bytesReceived;
    private long expectedBytes;
    private File resultFile;
    private File jobFile;
    private File outputFile;
    private boolean terminal;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        createStatusScreen();
        startPreparedJob();
    }

    private void createStatusScreen() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(48, 96, 48, 48);
        layout.setGravity(Gravity.CENTER_HORIZONTAL);

        TextView title = new TextView(this);
        title.setText("VABS IMOU Downloader");
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        layout.addView(title);

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setMax(100);
        LinearLayout.LayoutParams progressParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        progressParams.setMargins(0, 56, 0, 28);
        layout.addView(progressBar, progressParams);

        statusView = new TextView(this);
        statusView.setTextSize(18);
        statusView.setGravity(Gravity.CENTER);
        layout.addView(statusView);
        setContentView(layout);
    }

    private void startPreparedJob() {
        File internal = getFilesDir();
        jobFile = new File(internal, "job.json");
        resultFile = new File(internal, "result.json");
        if (!jobFile.isFile()) {
            setStatus("Waiting for Linux to push job.json");
            return;
        }

        try {
            if (resultFile.exists() && !resultFile.delete()) {
                throw new IllegalStateException("Could not clear old result");
            }
            DownloadJob job = DownloadJob.fromJson(readUtf8(jobFile));
            expectedBytes = job.expectedBytes;
            File movies = new File(internal, "Movies");
            if (!movies.isDirectory() && !movies.mkdirs()) {
                throw new IllegalStateException("Could not create Android movie storage");
            }
            outputFile = new File(movies, job.outputName);
            if (outputFile.exists() && !outputFile.delete()) {
                throw new IllegalStateException("Could not clear old output");
            }

            setStatus("Connecting to the authorized camera recording…");
            LCOpenSDK_Api.initOpenApi(
                    new InitParams(getApplication(), job.apiHost, job.accessToken)
            );
            LCOpenSDK_Download.setListener(new DownloadListener());
            LCOpenSDK_Download.startDeviceDownload(
                    DOWNLOAD_INDEX,
                    job.accessToken,
                    job.playToken,
                    job.deviceId,
                    outputFile.getAbsolutePath(),
                    job.recordId,
                    job.deviceCode,
                    job.beginTimeMillis,
                    job.recordType,
                    job.speed,
                    job.productId,
                    job.tlsEnable,
                    job.channelId
            );
        } catch (Throwable error) {
            fail("Could not start: " + safeMessage(error), "startup", -1);
        }
    }

    private final class DownloadListener extends LCOpenSDK_DownloadListener {
        @Override
        public void onDownloadReceiveData(int index, int dataLength) {
            if (index != DOWNLOAD_INDEX || terminal) {
                return;
            }
            bytesReceived += Math.max(dataLength, 0);
            runOnUiThread(() -> {
                if (expectedBytes > 0) {
                    int percent = (int) Math.min(99, bytesReceived * 100 / expectedBytes);
                    progressBar.setProgress(percent);
                    setStatus("Downloading… " + percent + "%");
                } else {
                    setStatus("Downloading…");
                }
            });
        }

        @Override
        public void onDownloadState(int index, String code, int type, String path) {
            if (index != DOWNLOAD_INDEX || terminal) {
                return;
            }
            boolean rtspComplete =
                    type == LCOpenSDK_StatusCode.Protocol.RESULT_PROTO_TYPE_RTSP
                            && LCOpenSDK_StatusCode.RTSPCode.STATE_RTSP_FILE_PLAY_OVER.equals(code);
            boolean httpComplete =
                    type == LCOpenSDK_StatusCode.Protocol.RESULT_PROTO_TYPE_LCHTTP
                            && LCOpenSDK_StatusCode.LCHTTPCode.STATE_LCHTTP_PLAY_FILE_OVER.equals(code);
            if (rtspComplete || httpComplete) {
                terminal = true;
                LCOpenSDK_Download.stopDownload(index);
                if (jobFile != null) {
                    // Remove temporary token and camera code after a successful transfer.
                    jobFile.delete();
                }
                writeResult("complete", code, type, null);
                runOnUiThread(() -> {
                    progressBar.setProgress(100);
                    setStatus("Download complete; waiting for Linux validation");
                });
                return;
            }

            // A REST state is a terminal setup/authentication failure in the vendor demo.
            if (type == LCOpenSDK_StatusCode.Protocol.RESULT_PROTO_TYPE_REST) {
                terminal = true;
                LCOpenSDK_Download.stopDownload(index);
                fail("OpenSDK rejected the download", code, type);
            }
        }
    }

    private void fail(String message, String code, int type) {
        if (!terminal) {
            terminal = true;
        }
        writeResult("failed", code, type, message);
        runOnUiThread(() -> setStatus(message));
    }

    private void writeResult(String status, String code, int type, String message) {
        if (resultFile == null) {
            return;
        }
        try {
            JSONObject json = new JSONObject();
            json.put("status", status);
            json.put("code", code == null ? "" : code);
            json.put("protocolType", type);
            json.put("bytesReceived", bytesReceived);
            json.put("outputName", outputFile == null ? "" : outputFile.getName());
            if (message != null) {
                json.put("message", message);
            }
            try (FileOutputStream stream = new FileOutputStream(resultFile, false)) {
                stream.write((json.toString() + "\n").getBytes(StandardCharsets.UTF_8));
                stream.getFD().sync();
            }
        } catch (Throwable ignored) {
            // The UI still reports the failure when result persistence itself fails.
        }
    }

    private static String readUtf8(File file) throws Exception {
        try (FileInputStream stream = new FileInputStream(file)) {
            byte[] bytes = new byte[(int) file.length()];
            int offset = 0;
            while (offset < bytes.length) {
                int read = stream.read(bytes, offset, bytes.length - offset);
                if (read < 0) {
                    break;
                }
                offset += read;
            }
            if (offset != bytes.length) {
                throw new IllegalStateException("Could not read complete job file");
            }
            return new String(bytes, StandardCharsets.UTF_8);
        }
    }

    private static String safeMessage(Throwable error) {
        String name = error.getClass().getSimpleName();
        String message = error.getMessage();
        return message == null || message.trim().isEmpty() ? name : name + ": " + message;
    }

    private void setStatus(String text) {
        statusView.setText(text);
    }
}
