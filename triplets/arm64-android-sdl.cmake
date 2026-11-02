# Triplet vcpkg untuk Android arm64. Semua library statis (masuk ke libmain.so), kecuali SDL3
# yang harus berupa libSDL3.so karena dimuat oleh SDLActivity (Java).
set(VCPKG_TARGET_ARCHITECTURE arm64)
set(VCPKG_CRT_LINKAGE dynamic)
set(VCPKG_LIBRARY_LINKAGE static)
set(VCPKG_CMAKE_SYSTEM_NAME Android)
set(VCPKG_BUILD_TYPE release)
set(VCPKG_CMAKE_CONFIGURE_OPTIONS "-DANDROID_PLATFORM=android-28" "-DANDROID_STL=c++_static")

if(PORT STREQUAL "sdl3")
    set(VCPKG_LIBRARY_LINKAGE dynamic)
endif()
