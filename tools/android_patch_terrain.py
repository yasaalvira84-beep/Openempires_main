#!/usr/bin/env python3
"""Peta uji (probe) jenis medan untuk OpenEmpires di Android. SEMENTARA.

Nomor SLP tiap jenis medan di terrain.drs tidak diketahui (file biner pengguna tidak bisa dibaca
dari sini). Skrip ini menaruh satu petak 3x3 untuk setiap SLP 15000..15031 (kecuali 15001 = rumput
bawaan) berdampingan di area awal: 7 kolom (arah +x) x 5 baris (arah +y), diurutkan menurut nomor
SLP (baris demi baris). Area itu dibuka dari kabut perang. Dari screenshot, jenis medan tiap nomor
bisa dipetakan lalu dipakai untuk peta sungguhan.

Nomor SLP yang ternyata tidak ada di terrain.drs dilewati (slotnya tetap rumput biasa) dan daftar
nomor yang ada/tidak ada dicatat ke log. Pemuat grafis dan getBoundingBox dibuat tahan terhadap SLP
yang tidak ada (sebelumnya "Resource not found" membuat game crash saat memulai).

Dijalankan otomatis oleh .github/workflows/android.yml (tools/android_patch_*.py).
Hapus file ini untuk mematikan peta uji.
"""

MARK = 'OE_ANDROID_TERRAIN_PROBE'

MODELS = 'assets/scripts/models.py'
LOADER = 'src/cpp/game/DRSGraphicsLoader.cpp'
DRSIFACE = 'src/cpp/game/DRSInterface.cpp'
HEADER = 'src/cpp/game/DemoWorldCreator.h'
SOURCE = 'src/cpp/game/DemoWorldCreator.cpp'

MODELS_BLOCK = '''# OE_ANDROID_TERRAIN_PROBE: jenis medan uji (slp_id 15000..15031 dari terrain.drs)
for _slp_id in range(15000, 15032):
    if _slp_id == 15001:  # rumput bawaan (default_tileset)
        continue
    all_entity_names.append(f"terrain_probe_{_slp_id}")
    all_tilesets.append(
        TileSet(
            name=f"terrain_probe_{_slp_id}",
            graphics=Graphic(
                layer=GraphicLayer.GROUND,
                variants=[
                    GraphicVariant(
                        graphic=SingleGraphic(drs_file="terrain.drs", slp_id=_slp_id),
                        variation_filter={GraphicVariantType.THEME: "default"})])))

'''

NEW_FUNCTIONS = r'''
// OE_ANDROID_TERRAIN_PROBE: petak uji jenis medan (lihat tools/android_patch_terrain.py)
EntityTypes DemoWorldCreator::terrainTypeAt(uint32_t x, uint32_t y)
{
    // Slot tetap per nomor SLP: slot 0 = 15000, slot 1 = 15002, ..., slot 30 = 15031.
    // Nilai 0 berarti SLP itu tidak ada di terrain.drs (slot dibiarkan rumput biasa).
    static std::vector<uint32_t> probeTypes;
    static bool initialized = false;
    if (!initialized)
    {
        initialized = true;
        probeTypes.assign(31, 0);

        drs::DRSFile terrainDrs;
        const bool loaded = terrainDrs.load("assets/terrain.drs");
        std::string present;
        std::string missing;
        for (int id = 15000; id <= 15031; ++id)
        {
            if (id == 15001)
                continue;

            bool exists = false;
            if (loaded)
            {
                try
                {
                    terrainDrs.getSLPFile(id);
                    exists = true;
                }
                catch (const std::exception&)
                {
                }
            }

            if (exists)
            {
                const size_t slot = static_cast<size_t>(id < 15001 ? id - 15000 : id - 15001);
                probeTypes[slot] = getResourceType("terrain_probe_" + std::to_string(id));
                present += std::to_string(id) + " ";
            }
            else
            {
                missing += std::to_string(id) + " ";
            }
        }
        spdlog::info("Peta uji medan: terrain.drs dimuat={}. SLP ada: {}| SLP tidak ada: {}", loaded,
                     present, missing);
    }

    const auto size = m_settings->getWorldSizeInTiles();
    const int cx = static_cast<int>(size.width) / 2;
    const int cy = static_cast<int>(size.height) / 2;
    const int dx = static_cast<int>(x) - (cx - 10);
    const int dy = static_cast<int>(y) - (cy - 10);

    // 7 kolom x 5 baris petak 3x3, mulai dari (cx-10, cy-10)
    if (dx >= 0 && dx < 21 && dy >= 0 && dy < 15)
    {
        const size_t index = static_cast<size_t>(dy / 3) * 7 + static_cast<size_t>(dx / 3);
        if (index < probeTypes.size() && probeTypes[index] != 0)
            return static_cast<EntityTypes>(probeTypes[index]);
    }
    return EntityTypes::ET_TILE;
}

void DemoWorldCreator::revealTerrainProbe(const std::vector<Ref<Player>>& players)
{
    if (players.empty())
        return;

    const auto size = m_settings->getWorldSizeInTiles();
    const Tile center(static_cast<int>(size.width) / 2, static_cast<int>(size.height) / 2);
    players[0]->getFogOfWar()->markAsExplored(center.centerInFeet(), 256 * 16);
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
    if append:
        s = s.rstrip('\n') + '\n' + append
    save(path, s, crlf, bom)
    print(path, 'dipatch')


LISTS_LINE = 'lists = [all_units, all_natural_resources, all_buildings, all_tilesets, all_ui_elements, all_misc]\n'

patch(MODELS, [(LISTS_LINE, MODELS_BLOCK + LISTS_LINE)])

patch(LOADER, [
    ('        auto slp = drs->getSLPFile(slpId);\n\n        std::vector<SDL_Surface*> surfaces;\n',
     '        // OE_ANDROID_TERRAIN_PROBE: SLP yang tidak ada di DRS tidak boleh membuat game crash\n'
     '        std::optional<decltype(drs->getSLPFile(slpId))> slpOpt;\n'
     '        try\n'
     '        {\n'
     '            slpOpt.emplace(drs->getSLPFile(slpId));\n'
     '        }\n'
     '        catch (const std::exception& e)\n'
     '        {\n'
     '            spdlog::error("SLP {} tidak bisa dimuat: {}", slpId, e.what());\n'
     '            return;\n'
     '        }\n'
     '        auto& slp = *slpOpt;\n\n'
     '        std::vector<SDL_Surface*> surfaces;\n'),
])

patch(DRSIFACE, [
    ('#include "DRSInterface.h"\n',
     '#include "DRSInterface.h"\n#include <spdlog/spdlog.h>\n'),
    ('    auto frameInfos = drsFile->getSLPFile(slpId).getFrameInfos();\n'
     '    auto& frame = frameInfos[frameIndex];\n'
     '    core::Rect<int> box(frame.hotspot_x, frame.hotspot_y, frame.width, frame.height);\n'
     '    return box;\n',
     '    // OE_ANDROID_TERRAIN_PROBE: SLP yang tidak ada di DRS tidak boleh membuat game crash\n'
     '    try\n'
     '    {\n'
     '        auto frameInfos = drsFile->getSLPFile(slpId).getFrameInfos();\n'
     '        auto& frame = frameInfos[frameIndex];\n'
     '        core::Rect<int> box(frame.hotspot_x, frame.hotspot_y, frame.width, frame.height);\n'
     '        return box;\n'
     '    }\n'
     '    catch (const std::exception& e)\n'
     '    {\n'
     '        spdlog::error("SLP {} tidak bisa dimuat dari {}: {}", slpId, drsFile->getFilename(), e.what());\n'
     '        return core::Rect<int>(0, 0, 0, 0);\n'
     '    }\n'),
])

patch(HEADER, [
    ('    void createTerrain();\n',
     '    void createTerrain();\n'
     '    EntityTypes terrainTypeAt(uint32_t x, uint32_t y); // OE_ANDROID_TERRAIN_PROBE\n'
     '    void revealTerrainProbe(const std::vector<core::Ref<core::Player>>& players);\n'),
])

patch(SOURCE, [
    ('#include "Coordinates.h"\n',
     '#include "Coordinates.h"\n#include "DRSFile.h"\n'),
    ('            createTile(i, j, EntityTypes::ET_TILE);\n',
     '            createTile(i, j, terrainTypeAt(i, j)); // OE_ANDROID_TERRAIN_PROBE\n'),
    ('    auto players = createPlayers();\n',
     '    auto players = createPlayers();\n'
     '    revealTerrainProbe(players); // OE_ANDROID_TERRAIN_PROBE\n'),
], append=NEW_FUNCTIONS)
print('Patch peta uji medan diterapkan.')
