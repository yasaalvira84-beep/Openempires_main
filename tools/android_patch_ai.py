#!/usr/bin/env python3
"""Mendaftarkan AI musuh (src/cpp/game/EnemyAI.h) ke Game.h, hanya untuk Android.

Pangkalan musuh ada di sudut peta: (lebar - 25, lebar - 25) petak, sama dengan tempat
tiga villager musuh dibuat oleh android_patch_world.py.

Dijalankan otomatis oleh .github/workflows/android.yml (tools/android_patch_*.py).
"""

MARK = 'OE_ANDROID_AI'


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


patch('src/cpp/game/Game.h', [
    ('#include "DemoWorldCreator.h"\n',
     '#include "DemoWorldCreator.h"\n'
     '#ifdef __ANDROID__ // OE_ANDROID_AI\n'
     '#include "EnemyAI.h"\n'
     '#endif\n'),
    ('        eventLoop->registerListener(std::move(projectileMan));\n',
     '        eventLoop->registerListener(std::move(projectileMan));\n'
     '#ifdef __ANDROID__ // OE_ANDROID_AI\n'
     '        {\n'
     '            const int base = static_cast<int>(settings->getWorldSizeInTiles().width) - 25;\n'
     '            eventLoop->registerListener(std::make_shared<game::EnemyAI>(2, base, base));\n'
     '        }\n'
     '#endif\n'),
])
print('Patch AI diterapkan.')
