package org.openempires.app;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;

/**
 * Ditampilkan saat game sebelumnya tidak berhenti normal (kemungkinan crash). Menampilkan log
 * terakhir supaya penyebabnya bisa dilihat tanpa PC, lengkap dengan tombol salin dan bagikan.
 */
public class LogActivity extends Activity {
    private static final int MAX_CHARS = 60000;
    private static final int GAME_LOG_TAIL_BYTES = 20000;

    private TextView logView;
    private ScrollView scrollView;
    private String logText = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        int pad = (int) (12 * getResources().getDisplayMetrics().density);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setTextSize(15);
        title.setText("Game sebelumnya tidak berhenti normal (kemungkinan crash). "
                + "Log terakhir ada di bawah. Salin atau bagikan lalu kirim ke Claude.");
        root.addView(title);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        buttons.setGravity(Gravity.CENTER);
        buttons.addView(makeButton("Salin", v -> copyLog()));
        buttons.addView(makeButton("Bagikan", v -> shareLog()));
        buttons.addView(makeButton("Mulai game", v -> startGame()));
        root.addView(buttons, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        scrollView = new ScrollView(this);
        logView = new TextView(this);
        logView.setTypeface(Typeface.MONOSPACE);
        logView.setTextSize(10);
        logView.setTextIsSelectable(true);
        logView.setText("Membaca log...");
        scrollView.addView(logView);
        root.addView(scrollView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(root);

        new Thread(() -> {
            String text = collectLog();
            runOnUiThread(() -> {
                logText = text;
                logView.setText(text);
                scrollView.post(() -> scrollView.fullScroll(ScrollView.FOCUS_DOWN));
            });
        }).start();
    }

    private Button makeButton(String text, android.view.View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(text);
        b.setOnClickListener(listener);
        b.setLayoutParams(new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return b;
    }

    private void copyLog() {
        ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard != null) {
            clipboard.setPrimaryClip(ClipData.newPlainText("log OpenEmpires", logText));
            Toast.makeText(this, "Log disalin", Toast.LENGTH_SHORT).show();
        }
    }

    private void shareLog() {
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_TEXT, logText);
        startActivity(Intent.createChooser(send, "Bagikan log"));
    }

    private void startGame() {
        GameActivity.markRunning(this);
        startActivity(new Intent(this, GameActivity.class));
        finish();
    }

    private String collectLog() {
        StringBuilder sb = new StringBuilder();
        sb.append("=== logcat (hanya log aplikasi ini) ===\n");
        sb.append(readLogcat());
        sb.append("\n=== berkas log game ===\n");
        sb.append(readNewestGameLog());

        String text = sb.toString();
        if (text.length() > MAX_CHARS) {
            text = "...(dipotong)...\n" + text.substring(text.length() - MAX_CHARS);
        }
        return text;
    }

    /** Aplikasi boleh membaca logcat miliknya sendiri tanpa izin khusus. */
    private String readLogcat() {
        try {
            Process process = new ProcessBuilder("logcat", "-d", "-v", "time", "-t", "800")
                    .redirectErrorStream(true)
                    .start();
            StringBuilder out = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    out.append(line).append('\n');
                }
            } finally {
                process.destroy();
            }
            return out.length() == 0 ? "(kosong)\n" : out.toString();
        } catch (IOException e) {
            return "(gagal membaca logcat: " + e.getMessage() + ")\n";
        }
    }

    private String readNewestGameLog() {
        File newest = findNewestLog(getFilesDir(), 0);
        if (newest == null) {
            return "(tidak ada berkas .log)\n";
        }
        try (RandomAccessFile file = new RandomAccessFile(newest, "r")) {
            long length = file.length();
            long start = Math.max(0, length - GAME_LOG_TAIL_BYTES);
            file.seek(start);
            byte[] data = new byte[(int) (length - start)];
            file.readFully(data);
            return newest.getName() + (start > 0 ? " (bagian akhir)" : "") + ":\n"
                    + new String(data, StandardCharsets.UTF_8) + "\n";
        } catch (IOException e) {
            return "(gagal membaca " + newest.getName() + ": " + e.getMessage() + ")\n";
        }
    }

    private static File findNewestLog(File dir, int depth) {
        File[] children = dir.listFiles();
        if (children == null || depth > 3) {
            return null;
        }
        File newest = null;
        for (File child : children) {
            File candidate = null;
            if (child.isDirectory()) {
                candidate = findNewestLog(child, depth + 1);
            } else if (child.getName().toLowerCase().endsWith(".log")) {
                candidate = child;
            }
            if (candidate != null && (newest == null || candidate.lastModified() > newest.lastModified())) {
                newest = candidate;
            }
        }
        return newest;
    }
}
