package org.openempires.app;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
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
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Menyiapkan folder data game sebelum GameActivity dibuka:
 *  1. Menyalin aset bawaan APK (font, gambar, models.json) ke filesDir/assets.
 *  2. Jika graphics.drs, terrain.drs, atau interfac.drs belum ada, pengguna cukup memilih SATU
 *     folder (mis. folder Data milik AoE2); ketiga file dicari otomatis sampai beberapa tingkat
 *     subfolder. Pemilihan file satu per satu tetap tersedia sebagai cadangan.
 * Tidak butuh izin penyimpanan khusus (memakai pemilih dokumen Android).
 */
public class SetupActivity extends Activity {
    private static final int REQUEST_PICK_FOLDER = 1;
    private static final int REQUEST_PICK_FILES = 2;
    private static final String[] REQUIRED_DRS = { "graphics.drs", "terrain.drs", "interfac.drs" };

    // Batas pencarian supaya tidak memindai pohon folder yang sangat besar
    private static final int MAX_DEPTH = 6;
    private static final int MAX_DIRS = 500;

    private TextView statusView;
    private Button pickFolderButton;
    private Button pickFilesButton;
    private File gameAssetsDir;

    // Hanya dipakai di thread pemindai
    private int visitedDirs;
    private List<String> wanted = new ArrayList<>();

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

        pickFolderButton = new Button(this);
        pickFolderButton.setText("Pilih folder game (otomatis)");
        pickFolderButton.setVisibility(View.GONE);
        pickFolderButton.setOnClickListener(v -> openFolderPicker());
        root.addView(pickFolderButton);

        pickFilesButton = new Button(this);
        pickFilesButton.setText("Pilih file satu per satu");
        pickFilesButton.setVisibility(View.GONE);
        pickFilesButton.setOnClickListener(v -> openFilePicker());
        root.addView(pickFilesButton);

        setContentView(root);
        setStatus("Menyiapkan aset...");

        new Thread(() -> {
            try {
                copyAssetDir("assets", gameAssetsDir);
            } catch (IOException e) {
                runOnUiThread(() -> setStatus("Gagal menyalin aset: " + e.getMessage()));
                return;
            }
            runOnUiThread(() -> checkDrsAndContinue(null));
        }).start();
    }

    private void setStatus(String text) {
        statusView.setText(text);
    }

    private void setPickButtonsVisible(boolean visible) {
        int v = visible ? View.VISIBLE : View.GONE;
        pickFolderButton.setVisibility(v);
        pickFilesButton.setVisibility(v);
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

    private void checkDrsAndContinue(String note) {
        List<String> missing = missingDrs();
        if (missing.isEmpty()) {
            startActivity(new Intent(this, GameActivity.class));
            finish();
            return;
        }
        String text = "File game Age of Empires II belum lengkap.\n\n"
                + "Pilih folder yang berisi file game (mis. folder \"Data\" milik AoE2). "
                + "File berikut dicari otomatis:\n" + String.join(", ", missing);
        if (note != null) {
            text = note + "\n\n" + text;
        }
        setStatus(text);
        setPickButtonsVisible(true);
    }

    private void openFolderPicker() {
        startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), REQUEST_PICK_FOLDER);
    }

    private void openFilePicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        startActivityForResult(intent, REQUEST_PICK_FILES);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null) {
            return;
        }

        if (requestCode == REQUEST_PICK_FOLDER) {
            Uri treeUri = data.getData();
            if (treeUri == null) {
                return;
            }
            setPickButtonsVisible(false);
            new Thread(() -> importFromFolder(treeUri)).start();
        } else if (requestCode == REQUEST_PICK_FILES) {
            List<Uri> uris = new ArrayList<>();
            ClipData clip = data.getClipData();
            if (clip != null) {
                for (int i = 0; i < clip.getItemCount(); i++) {
                    uris.add(clip.getItemAt(i).getUri());
                }
            } else if (data.getData() != null) {
                uris.add(data.getData());
            }
            setPickButtonsVisible(false);
            new Thread(() -> importFromFiles(uris)).start();
        }
    }

    /** Mencari file .drs yang dibutuhkan di dalam folder pilihan (dan subfolder-nya), lalu menyalinnya. */
    private void importFromFolder(Uri treeUri) {
        runOnUiThread(() -> setStatus("Mencari file di folder yang dipilih..."));

        wanted = missingDrs();
        visitedDirs = 0;
        Map<String, Uri> found = new HashMap<>();
        Map<String, Boolean> exact = new HashMap<>();
        scanFolder(treeUri, DocumentsContract.getTreeDocumentId(treeUri), 0, found, exact);

        if (found.isEmpty()) {
            runOnUiThread(() -> {
                setStatus("File " + String.join(", ", wanted) + " tidak ditemukan di folder itu "
                        + "(dicari sampai " + MAX_DEPTH + " tingkat subfolder).\n\n"
                        + "Coba pilih folder lain, mis. folder \"Data\" milik AoE2. Catatan: pada Android 11+, "
                        + "folder \"Download\" itu sendiri tidak bisa dipilih, tetapi subfoldernya bisa.");
                setPickButtonsVisible(true);
            });
            return;
        }
        importTargets(found);
    }

    private void importFromFiles(List<Uri> uris) {
        Map<String, Uri> targets = new HashMap<>();
        List<String> ignored = new ArrayList<>();
        for (Uri uri : uris) {
            String name = displayName(uri);
            String target = requiredNameFor(name);
            if (target == null) {
                ignored.add(name);
            } else if (!targets.containsKey(target)) {
                targets.put(target, uri);
            }
        }
        if (targets.isEmpty()) {
            String note = "Tidak ada file yang dibutuhkan di pilihan itu"
                    + (ignored.isEmpty() ? "." : " (dilewati: " + String.join(", ", ignored) + ").");
            runOnUiThread(() -> checkDrsAndContinue(note));
            return;
        }
        importTargets(targets);
    }

    /** Menyalin file-file hasil pencarian atau pilihan ke folder data game, lalu memeriksa ulang. */
    private void importTargets(Map<String, Uri> targets) {
        List<String> copied = new ArrayList<>();
        int index = 0;
        for (String name : REQUIRED_DRS) {
            Uri uri = targets.get(name);
            if (uri == null) {
                continue;
            }
            index++;
            String label = "Menyalin " + name + " (" + index + "/" + targets.size() + ") ...";
            runOnUiThread(() -> setStatus(label));
            try {
                copyUriToFile(uri, new File(gameAssetsDir, name));
                copied.add(name);
            } catch (IOException e) {
                runOnUiThread(() -> {
                    setStatus("Gagal menyalin " + name + ": " + e.getMessage());
                    setPickButtonsVisible(true);
                });
                return;
            }
        }
        String note = copied.isEmpty() ? null : "Disalin: " + String.join(", ", copied) + ".";
        runOnUiThread(() -> checkDrsAndContinue(note));
    }

    private boolean allWantedFoundExactly(Map<String, Boolean> exact) {
        for (String name : wanted) {
            Boolean e = exact.get(name);
            if (e == null || !e) {
                return false;
            }
        }
        return true;
    }

    /**
     * Menelusuri folder lewat DocumentsContract. Nama yang sama persis menang atas nama yang hanya
     * berawalan sama (mis. "graphics (1).drs").
     */
    private void scanFolder(Uri treeUri, String docId, int depth, Map<String, Uri> found,
            Map<String, Boolean> exact) {
        if (depth > MAX_DEPTH || visitedDirs >= MAX_DIRS) {
            return;
        }
        visitedDirs++;

        Uri childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, docId);
        List<String> subDirs = new ArrayList<>();
        try (Cursor c = getContentResolver().query(childrenUri, new String[] {
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE }, null, null, null)) {
            if (c == null) {
                return;
            }
            while (c.moveToNext()) {
                String childId = c.getString(0);
                String name = c.getString(1);
                String mime = c.getString(2);
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                    subDirs.add(childId);
                    continue;
                }
                String target = requiredNameFor(name);
                if (target == null || !wanted.contains(target)) {
                    continue;
                }
                boolean isExact = name.equalsIgnoreCase(target);
                Boolean previous = exact.get(target);
                if (previous == null || (!previous && isExact)) {
                    found.put(target, DocumentsContract.buildDocumentUriUsingTree(treeUri, childId));
                    exact.put(target, isExact);
                }
            }
        } catch (RuntimeException e) {
            // folder ini tidak bisa dibaca, lewati
        }

        for (String subDir : subDirs) {
            if (allWantedFoundExactly(exact)) {
                return;
            }
            scanFolder(treeUri, subDir, depth + 1, found, exact);
        }
    }

    /** Memetakan nama file (mis. "graphics (1).drs") ke nama yang dibutuhkan game. */
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
