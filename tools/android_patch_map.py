#!/usr/bin/env python3
"""Peta demo lebih kaya untuk OpenEmpires di Android.

Peta bawaan sengaja mengosongkan area +-10 petak di sekitar titik awal dan hanya punya satu gugus
emas dan satu gugus batu (4 petak), dan pemain mulai dengan sumber daya 0. Skrip ini menambah
DemoWorldCreator::createStartingResources():
  - beberapa hutan kecil, tambang emas, dan tambang batu di sekeliling area awal (di luar zona
    tempat unit awal diletakkan oleh android_patch_world.py)
  - modal awal untuk pemain manusia (kayu, batu, emas)

Dijalankan otomatis oleh .github/workflows/android.yml (tools/android_patch_*.py).
Tidak menyentuh baris yang dipatch oleh android_patch_world.py.
"""

MARK = 'OE_ANDROID_MAP'

HEADER = 'src/cpp/game/DemoWorldCreator.h'
SOURCE = 'src/cpp/game/DemoWorldCreator.cpp'

NEW_FUNCTION = r'''
// OE_ANDROID_MAP: sumber daya di sekitar titik awal (peta bawaan hanya rumput kosong)
void DemoWorldCreator::createStartingResources(const std::vector<Ref<Player>>& players)
{
    auto& gameMap = m_stateMan->gameMap();
    const int w = static_cast<int>(gameMap.width);
    const int h = static_cast<int>(gameMap.height);
    const int cx = w / 2;
    const int cy = h / 2;
    std::mt19937 rng(std::random_device{}());

    // Zona unit awal (lihat android_patch_world.py): jangan taruh pohon di sini
    auto inSafeZone = [&](int x, int y)
    {
        const int dx = x - cx;
        const int dy = y - cy;
        return dx >= -11 && dx <= 5 && dy >= -13 && dy <= 5;
    };

    auto freeTile = [&](int x, int y)
    {
        return x >= 1 && y >= 1 && x < w - 1 && y < h - 1 && !inSafeZone(x, y) &&
               !gameMap.isOccupied(MapLayerType::STATIC, Tile(x, y));
    };

    // Hutan kecil: pohon disebar acak dalam kotak 7x7 di sekitar titik pusat hutan
    auto grove = [&](int gx, int gy, int count)
    {
        int placed = 0;
        for (int attempt = 0; attempt < count * 6 && placed < count; ++attempt)
        {
            const int x = gx + static_cast<int>(rng() % 7) - 3;
            const int y = gy + static_cast<int>(rng() % 7) - 3;
            if (freeTile(x, y))
            {
                createTree(x, y);
                ++placed;
            }
        }
    };

    // Hutan di berbagai arah dari titik awal (selisih terhadap pusat peta)
    grove(cx + 9, cy - 8, 18);
    grove(cx - 14, cy + 5, 16);
    grove(cx + 12, cy + 10, 20);
    grove(cx - 6, cy - 17, 18);
    grove(cx + 4, cy + 16, 16);
    grove(cx - 16, cy - 8, 22);

    // Tambang tambahan (jumlah petak per gugus)
    createMiningCluster(getResourceType("gold"), cx + 9, cy + 3, 7);
    createMiningCluster(getResourceType("gold"), cx - 8, cy + 12, 6);
    createMiningCluster(getResourceType("stone"), cx - 14, cy - 3, 6);
    createMiningCluster(getResourceType("stone"), cx + 3, cy - 16, 6);

    // Modal awal pemain manusia
    if (!players.empty())
    {
        players[0]->grantResource(static_cast<uint8_t>(ResourceType::WOOD), 500);
        players[0]->grantResource(static_cast<uint8_t>(ResourceType::STONE), 300);
        players[0]->grantResource(static_cast<uint8_t>(ResourceType::GOLD), 300);
    }
}
'''


def load(path):
    raw = open(path, 'rb').read()
    return raw.decode('utf-8-sig').replace('\r\n', '\n'), b'\r\n' in raw, raw.startswith(b'\xef\xbb\xbf')


def save(path, text, crlf, bom):
    if crlf:
        text = text.replace('\n', '\r\n')
    open(path, 'wb').write((b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8'))


def patch(path, edits, append=''):
    s, crlf, bom = load(path)
    if MARK in s:
        print(path, 'sudah dipatch, dilewati')
        return
    for old, new in edits:
        assert s.count(old) == 1, (path, old[:70], s.count(old))
        s = s.replace(old, new)
    s = s.rstrip('\n') + '\n' + append
    save(path, s, crlf, bom)
    print(path, 'dipatch')


patch(HEADER, [
    ('    void generateRandomForest();\n',
     '    void generateRandomForest();\n'
     '    void createStartingResources(const std::vector<core::Ref<core::Player>>& players); // OE_ANDROID_MAP\n'),
])

patch(SOURCE, [
    ('    auto players = createPlayers();\n',
     '    auto players = createPlayers();\n'
     '    createStartingResources(players); // OE_ANDROID_MAP\n'),
], append=NEW_FUNCTION)
print('Patch peta kaya diterapkan.')
