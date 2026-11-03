#!/usr/bin/env python3
"""Layar penuh di Android untuk OpenEmpires.

Masalah: game menggambar di area tetap 1366x768 piksel, sedangkan layar HP jauh lebih besar,
jadi peta hanya tampil di sebagian layar (pojok kiri atas).
Perbaikan: ukuran dunia tampilan game dibuat 1536x768 (rasio mendekati layar HP, ~2:1) dan
renderer memetakannya ke seluruh layar (letterbox, tanpa distorsi). HUD, kamera, dan culling
semua memakai ukuran dari Settings, jadi ikut menyesuaikan.

Dijalankan otomatis oleh .github/workflows/android.yml (tools/android_patch_*.py).
"""

GAME = 'src/cpp/'
W, H = 1536, 768


def load(path):
    raw = open(path, 'rb').read()
    return raw.decode('utf-8-sig').replace('\r\n', '\n'), b'\r\n' in raw, raw.startswith(b'\xef\xbb\xbf')


def save(path, text, crlf, bom):
    if crlf:
        text = text.replace('\n', '\r\n')
    open(path, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8'))


def patch(path, marker, edits):
    s, crlf, bom = load(path)
    if marker in s:
        print(path, 'sudah dipatch, dilewati')
        return
    for old, new in edits:
        assert s.count(old) == 1, (path, old[:70], s.count(old))
        s = s.replace(old, new)
    save(path, s, crlf, bom)
    print(path, 'dipatch')


patch(GAME + 'game/Game.h', 'OE_ANDROID_VIEW', [
    ('        settings->setWindowDimensions(1366, 768);\n',
     '#ifdef __ANDROID__ // OE_ANDROID_VIEW\n'
     '        settings->setWindowDimensions(%d, %d);\n'
     '#else\n'
     '        settings->setWindowDimensions(1366, 768);\n'
     '#endif\n' % (W, H)),
])

patch(GAME + 'core/Renderer.cpp', 'OE_ANDROID_VIEW', [
    ('    {\n        std::lock_guard<std::mutex> lock(m_sdlInitMutex);\n        m_sdlInitialized = true;\n    }\n',
     '#ifdef __ANDROID__ // OE_ANDROID_VIEW\n'
     '    // Petakan area game (ukuran dari Settings) ke seluruh layar HP\n'
     '    SDL_SetRenderLogicalPresentation(m_renderer, m_settings->getWindowDimensions().width,\n'
     '                                     m_settings->getWindowDimensions().height,\n'
     '                                     SDL_LOGICAL_PRESENTATION_LETTERBOX);\n'
     '#endif\n'
     '    {\n        std::lock_guard<std::mutex> lock(m_sdlInitMutex);\n        m_sdlInitialized = true;\n    }\n'),
])
print('Patch layar diterapkan.')
