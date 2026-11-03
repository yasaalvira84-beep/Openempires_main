#!/usr/bin/env python3
"""Kontrol sentuh Android untuk OpenEmpires.

Dijalankan otomatis oleh .github/workflows/android.yml (tools/android_patch_*.py).
Menyambungkan src/cpp/core/TouchControls.h ke Renderer.cpp dan InputProcessor.h.
Setiap penggantian di-assert tepat satu kali: kalau kode asli berubah, skrip gagal jelas.
"""

CORE = 'src/cpp/core/'


def load(path):
    raw = open(path, 'rb').read()
    crlf = b'\r\n' in raw
    bom = raw.startswith(b'\xef\xbb\xbf')
    return raw.decode('utf-8-sig').replace('\r\n', '\n'), crlf, bom


def save(path, text, crlf, bom):
    if crlf:
        text = text.replace('\n', '\r\n')
    open(path, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8'))


def patch(path, edits):
    s, crlf, bom = load(path)
    if 'TouchControls' in s:
        print(path, 'sudah dipatch, dilewati')
        return
    for old, new in edits:
        assert s.count(old) == 1, (path, old[:70], s.count(old))
        s = s.replace(old, new)
    save(path, s, crlf, bom)
    print(path, 'dipatch')


patch(CORE + 'InputProcessor.h', [
    ('#include "Event.h"\n',
     '#include "Event.h"\n#include "TouchControls.h"\n'),
    ('            m_previousMouseState = currentMouseState;\n        }\n    }\n',
     '            m_previousMouseState = currentMouseState;\n        }\n\n'
     '        // Event sentuh (Android) yang sudah diubah jadi event mouse / keyboard\n'
     '        TouchControls::instance().drain(callback);\n    }\n'),
])

patch(CORE + 'Renderer.cpp', [
    ('#include "StatsCounter.h"\n',
     '#include "StatsCounter.h"\n#include "TouchControls.h"\n'),

    # Sentuhan tidak lagi dibuat jadi klik mouse otomatis oleh SDL; ditangani TouchControls.
    ('    if (!SDL_Init(SDL_INIT_VIDEO))\n',
     '#ifdef __ANDROID__\n'
     '    SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "0");\n'
     '#endif\n'
     '    if (!SDL_Init(SDL_INIT_VIDEO))\n'),

    ('        // handle mouse click events\n',
     '#ifdef __ANDROID__\n'
     '        TouchControls::instance().onSdlEvent(event, m_window, m_renderer);\n'
     '#endif\n'
     '        // handle mouse click events\n'),

    ('    }\n    return true;\n}\n\n/**\n * @brief Updates the graphic components',
     '    }\n'
     '#ifdef __ANDROID__\n'
     '    TouchControls::instance().update();\n'
     '    {\n'
     '        const Vec2 pan = TouchControls::instance().takePan();\n'
     '        if (pan.x != 0 || pan.y != 0)\n'
     '        {\n'
     '            m_coordinates.setViewportPositionInPixelsWithBounryChecking(\n'
     '                m_coordinates.getViewportPositionInPixels() - pan);\n'
     '        }\n'
     '    }\n'
     '#endif\n'
     '    return true;\n}\n\n/**\n * @brief Updates the graphic components'),

    ('        renderSelectionBox();\n',
     '        renderSelectionBox();\n'
     '#ifdef __ANDROID__\n'
     '        TouchControls::instance().draw(m_renderer);\n'
     '#endif\n'),
])
print('Patch sentuh diterapkan.')
