package org.openempires.app;

import android.content.Context;

import org.libsdl.app.SDLActivity;

import java.io.File;
import java.io.IOException;

/** Menjalankan game native (libSDL3.so + libmain.so) lewat SDL. */
public class GameActivity extends SDLActivity {
    /**
     * Penanda "game sedang berjalan". Dibuat sebelum game dimulai dan dihapus saat game keluar
     * normal. Kalau game crash (proses mati), penanda tertinggal, sehingga peluncuran berikutnya
     * menampilkan LogActivity.
     */
    static File flagFile(Context context) {
        return new File(context.getFilesDir(), "game_running.flag");
    }

    static void markRunning(Context context) {
        try {
            flagFile(context).createNewFile();
        } catch (IOException ignored) {
            // tidak fatal: hanya fitur deteksi crash yang tidak aktif
        }
    }

    @Override
    protected String[] getLibraries() {
        return new String[] { "SDL3", "main" };
    }

    @Override
    protected void onDestroy() {
        flagFile(this).delete();
        super.onDestroy();
    }
}
