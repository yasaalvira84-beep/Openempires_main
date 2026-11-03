#!/usr/bin/env python3
"""Peta lebih besar di Android untuk OpenEmpires.

Peta demo bawaan hanya 50x50 petak, terlalu kecil di layar HP. Skrip ini memakai ukuran TINY
(120x120 petak) dan menggeser posisi awal unit dan tambang ke tengah peta supaya kamera
(yang mulai di tengah peta) tetap menghadap unit-unit tersebut. Dua villager juga dijadikan
milik pemain 1 (pemain manusia) karena di Android hanya ada satu pemain yang dikendalikan.

Dijalankan otomatis oleh .github/workflows/android.yml (tools/android_patch_*.py).
"""

MARK = 'OE_ANDROID_WORLD'


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


# Ukuran dunia harus ditetapkan sebelum StateManager::init() dan Coordinates dibuat
patch('src/cpp/game/Game.h', [
    ('        auto settings = std::make_shared<core::Settings>();\n',
     '        auto settings = std::make_shared<core::Settings>();\n'
     '#ifdef __ANDROID__ // OE_ANDROID_WORLD\n'
     '        settings->setWorldSizeType(core::WorldSizeType::TINY);\n'
     '#endif\n'),
])

# Posisi awal bawaan dibuat untuk peta 50x50 (tengah = 25,25). Geser ke tengah peta sebenarnya.
patch('src/cpp/game/DemoWorldCreator.cpp', [
    ('    spdlog::info("Creating the demo world");\n',
     '    spdlog::info("Creating the demo world");\n'
     '    // OE_ANDROID_WORLD: geser posisi awal dari tengah peta 50x50 ke tengah peta sebenarnya\n'
     '    const int o = static_cast<int>(m_settings->getWorldSizeInTiles().width) / 2 - 25;\n'),
    ('getResourceType("stone"), 30, 30, 4)', 'getResourceType("stone"), 30 + o, 30 + o, 4)'),
    ('getResourceType("gold"), 20, 30, 4)', 'getResourceType("gold"), 20 + o, 30 + o, 4)'),
    ('createVillager(players[1], Tile(24, 22));', 'createVillager(players[0], Tile(24 + o, 22 + o));'),
    ('createVillager(players[1], Tile(25, 21));', 'createVillager(players[0], Tile(25 + o, 21 + o));'),
    ('createMilitaryUnit("militia", players[0], Tile(20, 25));',
     'createMilitaryUnit("militia", players[0], Tile(20 + o, 25 + o));'),
    ('createMilitaryUnit("militia", players[0], Tile(21, 21));',
     'createMilitaryUnit("militia", players[0], Tile(21 + o, 21 + o));'),
    ('createMilitaryUnit("archer", players[0], Tile(21, 25));',
     'createMilitaryUnit("archer", players[0], Tile(21 + o, 25 + o));'),
    ('createMilitaryUnit("archer", players[0], Tile(21, 17));',
     'createMilitaryUnit("archer", players[0], Tile(21 + o, 17 + o));'),
])
print('Patch peta diterapkan.')
