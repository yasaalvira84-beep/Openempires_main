# Triplet vcpkg untuk Android arm64. Semua library statis (masuk ke libmain.so), kecuali SDL3
# yang harus berupa libSDL3.so karena dimuat oleh SDLActivity (Java).
set(VCPKG_TARGET_ARCHITECTURE arm64)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_CMAKE_SYSTEM_NAME Android)
set(VCPKG_MAKE_BUILD_TRIPLET "--host=aarch64-linux-android")
set(VCPKG_BUILD_TYPE release)
# ANDROID_ABI harus eksplisit: tanpa ini paket vcpkg bisa terbangun 32-bit (armeabi-v7a),
# sehingga ditolak find_package oleh proyek utama yang 64-bit.
set(VCPKG_CMAKE_CONFIGURE_OPTIONS "-DANDROID_ABI=arm64-v8a" "-DANDROID_PLATFORM=android-28" "-DANDROID_STL=c++_static")

if(PORT STREQUAL "sdl3")
    set(VCPKG_LIBRARY_LINKAGE dynamic)
endif()
