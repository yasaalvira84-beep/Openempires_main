add_subdirectory(drs)
add_subdirectory(game)
add_subdirectory(core)
add_subdirectory(sdl3_gfx)

if(ANDROID)
    # SDLActivity memuat library bersama bernama "main" (libmain.so) dan memanggil SDL_main
    add_library(openEmpires SHARED main.cpp)
    set_target_properties(openEmpires PROPERTIES OUTPUT_NAME "main")
else()
    add_executable(openEmpires main.cpp)
endif()

# Without setting this property, the working directory will be build/src/cpp
# and the assets folder will not be found. But this has to be build/bin
set_target_properties(openEmpires PROPERTIES
    VS_DEBUGGER_WORKING_DIRECTORY "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}"
)

target_link_libraries(openEmpires
    PRIVATE
        drs
        game
        core
        sdl3_gfx
)

if(ANDROID)
    # liblog: dibutuhkan sink logcat spdlog (android_sink)
    target_link_libraries(openEmpires PRIVATE log)
endif()

target_include_directories(openEmpires
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/drs
        ${CMAKE_CURRENT_SOURCE_DIR}/game
        ${CMAKE_CURRENT_SOURCE_DIR}/core
        ${CMAKE_CURRENT_SOURCE_DIR}/sdl3_gfx
)


# Define the source asset directory
set(ASSET_DIR "${CMAKE_SOURCE_DIR}/assets")
set(OUTPUT_BIN_DIR "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}") # Use the existing bin directory

# Create the assets directory in the bin directory if it doesn't exist
file(MAKE_DIRECTORY "${OUTPUT_BIN_DIR}/assets")


# Copy the entire assets directory to the bin directory and bin\<build config; eg: debug 
# or release>
# Depending on various ways that the game can run (eg: console, IDE, IDE test explorer, 
# console test), working directory can be different. Therefore, assets should be copied
# to both build\bin and build\bin\debug or build\bin\release.
#
if(NOT ANDROID)
    # Di Android, aset dipaketkan ke dalam APK (lihat .github/workflows/android.yml)
    add_custom_command(
        TARGET openEmpires
        POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E echo "Copying assets..."
        COMMAND ${CMAKE_COMMAND} -E copy_directory "${ASSET_DIR}" "${OUTPUT_BIN_DIR}/assets"
        COMMAND ${CMAKE_COMMAND} -E copy_directory "${ASSET_DIR}" "${OUTPUT_BIN_DIR}/$<CONFIG>/assets"
        COMMENT "Copied assets to the binary directory"
        VERBATIM
    )
endif()
