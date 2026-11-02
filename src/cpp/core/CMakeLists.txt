find_package(SDL3 CONFIG REQUIRED)
find_package(SDL3_image CONFIG REQUIRED)
find_package(SDL3_ttf CONFIG REQUIRED)
find_package(EnTT CONFIG REQUIRED)
if(OE_USE_PYTHON)
    find_package(pybind11 CONFIG REQUIRED)
else()
    find_package(nlohmann_json CONFIG REQUIRED)
endif()
find_package(imgui CONFIG REQUIRED)

include(FetchContent)

FetchContent_Declare(
  readerwriterqueue
  GIT_REPOSITORY    https://github.com/cameron314/readerwriterqueue
  GIT_TAG           master
)
FetchContent_MakeAvailable(readerwriterqueue)

# Automatically gather .cpp files (headers are for IDEs)
file(GLOB_RECURSE SOURCES CONFIGURE_DEPENDS
    *.cpp
    *.h *.hpp
)

add_library(core STATIC ${SOURCES})

target_include_directories(core PUBLIC ${GENERATED_DIR})
target_include_directories(core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(core PUBLIC 
    readerwriterqueue
    EnTT::EnTT
    SDL3::SDL3
    $<IF:$<TARGET_EXISTS:SDL3_ttf::SDL3_ttf>,SDL3_ttf::SDL3_ttf,SDL3_ttf::SDL3_ttf-static>
    $<IF:$<TARGET_EXISTS:SDL3_image::SDL3_image-shared>,SDL3_image::SDL3_image-shared,SDL3_image::SDL3_image-static>
    sdl3_gfx
    imgui::imgui
)

# Definisi entitas: interpreter Python tertanam (desktop) atau models.json (mis. Android)
if(OE_USE_PYTHON)
    target_link_libraries(core PUBLIC pybind11::embed)
    target_compile_definitions(core PUBLIC OE_USE_PYTHON)
else()
    target_link_libraries(core PUBLIC nlohmann_json::nlohmann_json)
endif()