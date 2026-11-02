package org.openempires.app;

import org.libsdl.app.SDLActivity;

/** Menjalankan game native (libSDL3.so + libmain.so) lewat SDL. */
public class GameActivity extends SDLActivity {
    @Override
    protected String[] getLibraries() {
        return new String[] { "SDL3", "main" };
    }
}
