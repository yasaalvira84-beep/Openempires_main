#include "Game.h"
#include "Studio.h"
#include "internal/DRSTester.h"

#ifdef __ANDROID__
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include <filesystem>
#endif

int main(int, char*[])
{
#ifdef __ANDROID__
    // Semua path aset bersifat relatif ("assets/..."). Di Android, folder data internal aplikasi
    // dijadikan direktori kerja. Isinya disiapkan oleh SetupActivity (Java): aset bawaan APK
    // disalin ke sana dan file .drs dipilih pengguna.
    if (const char* dir = SDL_GetAndroidInternalStoragePath())
        std::filesystem::current_path(dir);
#endif

    game::Game game;
    return game.run(game::Game::Params());

    // drs::DRSTester tester;
    // tester.load();
    // return 0;

    // game::Studio studio;
    // studio.init();
    // studio.run();
    // return 0;
}
