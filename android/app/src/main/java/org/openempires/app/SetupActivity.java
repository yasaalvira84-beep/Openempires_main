package org.openempires.app;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Menyiapkan folder data game sebelum GameActivity dibuka:
 *  1. Menyalin aset bawaan APK (font, gambar, models.json) ke filesDir/assets.
 *  2. Jika graphics.drs, terrain.drs, atau interfac.drs belum ada, meminta pengguna memilihnya
 *     lewat pemilih file Android (tanpa izin penyimpanan khusus).
 */
public class SetupActivity extends Activity {
    private static final int REQUEST_PICK_DRS = 1;
    private static final String[] REQUIRED_DRS = { "graphics.drs", "terrain.drs", "interfac.drs" };

    private TextView statusView;
    private Button pickButton;
    private File gameAssetsDir;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        gameAssetsDir = new File(getFilesDir(), "assets");

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        int pad = (int) (24 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);

        statusView = new TextView(this);
        statusView.setTextSize(16);
        statusView.setGravity(Gravity.CENTER);
        root.addView(statusView);

        pickButton = new Button(this);
        pickButton.setText("Pilih file .drs");
        pickButton.setVisibility(View.GONE);
        pickButton.setOnClickListener(v -> openPicker());
        root.addView(pickButton);

        setContentView(root);
        setStatus("Menyiapkan aset...");

        new Thread(() -> {
            try {
                copyAssetDir("assets", gameAssetsDir);
            } catch (IOException e) {
                runOnUiThread(() -> setStatus("Gagal menyalin aset: " + e.getMessage()));
                return;
            }
            runOnUiThread(this::checkDrsAndContinue);
        }).start();
    }

    private void setStatus(String text) {
        statusView.setText(text);
    }

    private List<String> missingDrs() {
        List<String> missing = new ArrayList<>();
        for (String name : REQUIRED_DRS) {
            File f = new File(gameAssetsDir, name);
            if (!f.isFile() || f.length() == 0) {
                missing.add(name);
            }
        }
        return missing;
    }

    private void checkDrsAndContinue() {
        List<String> missing = missingDrs();
        if (missing.isEmpty()) {
            startActivity(new Intent(this, GameActivity.class));
            finish();
            return;
        }
        setStatus("File game Age of Empires II belum ada.\n\nPilih ketiga file ini dari folder Data "
                + "AoE2 (bisa sekaligus):\n" + String.join(", ", missing));
        pickButton.setVisibility(View.VISIBLE);
    }

    private void openPicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        startActivityForResult(intent, REQUEST_PICK_DRS);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_PICK_DRS || resultCode != RESULT_OK || data == null) {
            return;
        }

        List<Uri> uris = new ArrayList<>();
        ClipData clip = data.getClipData();
        if (clip != null) {
            for (int i = 0; i < clip.getItemCount(); i++) {
                uris.add(clip.getItemAt(i).getUri());
            }
        } else if (data.getData() != null) {
            uris.add(data.getData());
        }

        pickButton.setVisibility(View.GONE);
        new Thread(() -> importDrsFiles(uris)).start();
    }

    private void importDrsFiles(List<Uri> uris) {
        List<String> ignored = new ArrayList<>();
        for (Uri uri : uris) {
            String target = requiredNameFor(displayName(uri));
            if (target == null) {
                ignored.add(displayName(uri));
                continue;
            }
            runOnUiThread(() -> setStatus("Menyalin " + target + " ..."));
            try {
                copyUriToFile(uri, new File(gameAssetsDir, target));
            } catch (IOException e) {
                runOnUiThread(() -> {
                    setStatus("Gagal menyalin " + target + ": " + e.getMessage());
                    pickButton.setVisibility(View.VISIBLE);
                });
                return;
            }
        }
        runOnUiThread(() -> {
            if (!ignored.isEmpty() && !missingDrs().isEmpty()) {
                setStatus("Dilewati (bukan file yang dibutuhkan): " + String.join(", ", ignored));
            }
            checkDrsAndContinue();
        });
    }

    /** Memetakan nama file pilihan pengguna (mis. "graphics (1).drs") ke nama yang dibutuhkan game. */
    private static String requiredNameFor(String displayName) {
        if (displayName == null) {
            return null;
        }
        String lower = displayName.toLowerCase(Locale.ROOT);
        if (!lower.endsWith(".drs")) {
            return null;
        }
        for (String required : REQUIRED_DRS) {
            String base = required.substring(0, required.length() - ".drs".length());
            if (lower.startsWith(base)) {
                return required;
            }
        }
        return null;
    }

    private String displayName(Uri uri) {
        try (Cursor c = getContentResolver().query(uri, new String[] { OpenableColumns.DISPLAY_NAME },
                null, null, null)) {
            if (c != null && c.moveToFirst()) {
                return c.getString(0);
            }
        } catch (RuntimeException ignored) {
            // jatuh ke segmen terakhir path di bawah
        }
        String last = uri.getLastPathSegment();
        return last == null ? null : last.substring(last.lastIndexOf('/') + 1);
    }

    private void copyUriToFile(Uri uri, File dest) throws IOException {
        File tmp = new File(dest.getPath() + ".part");
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) {
                throw new IOException("tidak bisa membuka file");
            }
            copyStream(in, tmp);
        }
        if (dest.exists() && !dest.delete()) {
            throw new IOException("tidak bisa menimpa " + dest.getName());
        }
        if (!tmp.renameTo(dest)) {
            throw new IOException("tidak bisa menyimpan " + dest.getName());
        }
    }

    /** Menyalin isi folder aset APK secara rekursif ke penyimpanan internal aplikasi. */
    private void copyAssetDir(String assetPath, File dest) throws IOException {
        String[] children = getAssets().list(assetPath);
        if (children == null || children.length == 0) {
            try (InputStream in = getAssets().open(assetPath)) {
                copyStream(in, dest);
            } catch (IOException e) {
                // folder kosong, abaikan
            }
            return;
        }
        if (!dest.isDirectory() && !dest.mkdirs()) {
            throw new IOException("tidak bisa membuat folder " + dest);
        }
        for (String child : children) {
            copyAssetDir(assetPath + "/" + child, new File(dest, child));
        }
    }

    private static void copyStream(InputStream in, File dest) throws IOException {
        File parent = dest.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
            throw new IOException("tidak bisa membuat folder " + parent);
        }
        try (OutputStream out = new FileOutputStream(dest)) {
            byte[] buffer = new byte[64 * 1024];
            int n;
            while ((n = in.read(buffer)) > 0) {
                out.write(buffer, 0, n);
            }
        }
    }
}
