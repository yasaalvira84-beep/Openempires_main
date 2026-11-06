#!/usr/bin/env python3
"""Label nomor SLP di tengah setiap petak uji medan. SEMENTARA, bersama android_patch_terrain.py.

DemoWorldCreator::terrainTypeAt mendaftarkan (petak tengah, nomor SLP) ke core/ProbeLabels.h, dan
RendererImpl::renderDebugInfo menggambar nomor itu dengan SDL_RenderDebugText di posisi layar
petak tersebut. Dari screenshot, nomor tiap jenis medan terbaca langsung.

Harus berjalan SETELAH android_patch_terrain.py (urutan abjad: "terrain.py" < "terrain_labels.py").
Hapus file ini (dan android_patch_terrain.py) untuk mematikan peta uji.
"""

MARK = 'OE_ANDROID_TERRAIN_LABELS'

RENDERER = 'src/cpp/core/Renderer.cpp'
SOURCE = 'src/cpp/game/DemoWorldCreator.cpp'


def load(path):
    raw = open(path, 'rb').read()
    return raw.decode('utf-8-sig').replace('\r\n', '\n'), b'\r\n' in raw, raw.startswith(b'\xef\xbb\xbf')


def save(path, text, crlf, bom):
    if crlf:
        text = text.replace('\n', '\r\n')
    open(path, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8'))


def patch(path, edits):
    s, crlf, bom = load(path)
    if MARK in s:
        print(path, 'sudah dipatch, dilewati')
        return
    for old, new in edits:
        assert s.count(old) == 1, (path, old[:70], s.count(old))
        s = s.replace(old, new)
    save(path, s, crlf, bom)
    print(path, 'dipatch')


patch(SOURCE, [
    ('#include "DRSFile.h"\n',
     '#include "DRSFile.h"\n#include "ProbeLabels.h" // OE_ANDROID_TERRAIN_LABELS\n'),
    ('                probeTypes[slot] = getResourceType("terrain_probe_" + std::to_string(id));\n'
     '                present += label;\n',
     '                probeTypes[slot] = getResourceType("terrain_probe_" + std::to_string(id));\n'
     '                present += label;\n'
     '                {\n'
     '                    // OE_ANDROID_TERRAIN_LABELS: nomor SLP di tengah petak 3x3 ini\n'
     '                    const auto worldSize = m_settings->getWorldSizeInTiles();\n'
     '                    const int gridX = static_cast<int>(worldSize.width) / 2 - 10;\n'
     '                    const int gridY = static_cast<int>(worldSize.height) / 2 - 10;\n'
     '                    std::lock_guard<std::mutex> lock(probeLabelsMutex());\n'
     '                    probeLabels().push_back({gridX + static_cast<int>(slot % 7) * 3 + 1,\n'
     '                                             gridY + static_cast<int>(slot / 7) * 3 + 1,\n'
     '                                             std::to_string(id)});\n'
     '                }\n'),
])

patch(RENDERER, [
    ('#include "Version.h"\n',
     '#include "Version.h"\n#include "ProbeLabels.h" // OE_ANDROID_TERRAIN_LABELS\n'),
    ('    SDL_RenderDebugText(m_renderer, 10, m_settings->getWindowDimensions().height - 20,\n'
     '                        OPENEMPIRES_VERSION_STRING);\n',
     '    SDL_RenderDebugText(m_renderer, 10, m_settings->getWindowDimensions().height - 20,\n'
     '                        OPENEMPIRES_VERSION_STRING);\n'
     '\n'
     '    // OE_ANDROID_TERRAIN_LABELS: nomor SLP di atas tiap petak uji medan\n'
     '    {\n'
     '        Uint8 r = 0, g = 0, b = 0, a = 255;\n'
     '        SDL_GetRenderDrawColor(m_renderer, &r, &g, &b, &a);\n'
     '        SDL_SetRenderDrawColor(m_renderer, 255, 255, 0, 255);\n'
     '        {\n'
     '            std::lock_guard<std::mutex> lock(probeLabelsMutex());\n'
     '            for (const auto& label : probeLabels())\n'
     '            {\n'
     '                const auto pos = m_coordinates.feetToScreenUnits(Tile(label.tileX, label.tileY).centerInFeet());\n'
     '                SDL_RenderDebugText(m_renderer, static_cast<float>(pos.x), static_cast<float>(pos.y),\n'
     '                                    label.text.c_str());\n'
     '            }\n'
     '        }\n'
     '        SDL_SetRenderDrawColor(m_renderer, r, g, b, a);\n'
     '    }\n'),
])
print('Patch label medan diterapkan.')
