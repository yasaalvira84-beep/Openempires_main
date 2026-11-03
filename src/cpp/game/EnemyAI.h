#ifndef GAME_ENEMYAI_H
#define GAME_ENEMYAI_H

// AI musuh sederhana (tingkat ringan) untuk build Android, tanpa Python.
//
// AI memakai jalur yang sama dengan pemain manusia: event BUILDING_REQUESTED,
// UNIT_QUEUE_REQUEST dan COMMAND_REQUEST. Keputusan diambil tiap 2 detik:
//   1. Bangun town center, lalu rumah (bila kapasitas populasi menipis), lalu barak.
//   2. Latih villager (sampai 5) di town center dan militia (sampai 10) di barak.
//   3. Villager yang menganggur membantu menyelesaikan bangunan.
//   4. Gelombang serangan: pertama setelah 4 menit, lalu tiap 3 menit, bila pasukan >= 3.
// Catatan: kode asli tidak punya biaya sumber daya, jadi AI tidak mengumpulkan sumber daya.

#include "EntityTypeRegistry.h"
#include "EventHandler.h"
#include "EventPublisher.h"
#include "Player.h"
#include "PlayerFactory.h"
#include "ServiceRegistry.h"
#include "StateManager.h"
#include "commands/CmdAttack.h"
#include "commands/CmdBuild.h"
#include "components/CompBuilder.h"
#include "components/CompBuilding.h"
#include "components/CompEntityInfo.h"
#include "components/CompHealth.h"
#include "components/CompMeleeAttack.h"
#include "components/CompPlayer.h"
#include "components/CompRangeAttack.h"
#include "components/CompTransform.h"
#include "components/CompUnit.h"
#include "components/CompUnitFactory.h"
#include "logging/Logger.h"
#include "utils/Constants.h"
#include "utils/ObjectPool.h"

#include <cstdint>
#include <limits>
#include <vector>

namespace game
{
class EnemyAI : public core::EventHandler
{
  public:
    EnemyAI(uint8_t playerId, int baseTileX, int baseTileY)
        : m_playerId(playerId), m_baseX(baseTileX), m_baseY(baseTileY)
    {
        registerCallback(core::Event::Type::TICK, this, &EnemyAI::onTick);
        registerCallback(core::Event::Type::BUILDING_CREATED, this, &EnemyAI::onBuildingCreated);
    }

  private:
    static constexpr int STEP_MS = 2000;
    static constexpr int FIRST_WAVE_MS = 240000;
    static constexpr int WAVE_GAP_MS = 180000;
    static constexpr int WAVE_DURATION_MS = 120000;
    static constexpr int RETARGET_MS = 6000;
    static constexpr size_t MIN_WAVE_SIZE = 3;
    static constexpr size_t TARGET_VILLAGERS = 5;
    static constexpr size_t TARGET_ARMY = 10;
    static constexpr int MAX_HOUSES = 6;

    struct Census
    {
        std::vector<uint32_t> villagers;
        std::vector<uint32_t> army;
        uint32_t tc = entt::null;
        uint32_t barracks = entt::null;
        int tcDone = 0, tcSite = 0;
        int houseDone = 0, houseSite = 0;
        int barracksDone = 0, barracksSite = 0;
        std::vector<uint32_t> sites; // Semua bangunan milik AI yang belum selesai
    };

    // Event handlers

    bool onTick(const core::Event& e)
    {
        const int delta = e.getData<core::TickData>().deltaTimeMs;
        m_elapsedMs += delta;
        m_sinceStepMs += delta;
        if (m_sinceStepMs < STEP_MS)
            return false;
        m_sinceStepMs = 0;

        if (!resolveServices())
            return false;
        step();
        return false;
    }

    // Bangunan milik AI disetujui: kerahkan semua villager untuk membangunnya
    bool onBuildingCreated(const core::Event& e)
    {
        const auto& data = e.getData<core::BuildingPlacementData>();
        if (!m_player || !data.player || !data.player->isSame(m_player))
            return false;

        const Census c = takeCensus();
        for (auto villager : c.villagers)
            orderBuild(villager, data.entity);
        return false;
    }

    // Decision making

    bool resolveServices()
    {
        if (m_ready)
            return true;

        try
        {
            auto factory = core::ServiceRegistry::getInstance().getService<core::PlayerFactory>();
            m_player = factory->getPlayer(m_playerId);
            m_stateMan = core::ServiceRegistry::getInstance().getService<core::StateManager>();
            m_types = core::ServiceRegistry::getInstance().getService<core::EntityTypeRegistry>();

            m_villagerType = m_types->getEntityType("villager");
            m_militiaType = m_types->getEntityType("militia");
            m_tcType = m_types->getEntityType("town_center");
            m_houseType = m_types->getEntityType("house");
            m_barracksType = m_types->getEntityType("barracks");
        }
        catch (...)
        {
            // Dunia belum selesai dibuat; coba lagi pada langkah berikutnya
            return false;
        }

        m_nextWaveMs = FIRST_WAVE_MS;
        m_ready = true;
        spdlog::info("[AI] Musuh (pemain {}) aktif, pangkalan di tile ({}, {})", m_playerId,
                     m_baseX, m_baseY);
        return true;
    }

    void step()
    {
        const Census c = takeCensus();

        // 1. Bangun pangkalan
        if (c.tcDone + c.tcSite == 0)
        {
            if (!c.villagers.empty())
                requestBuilding(m_tcType);
        }
        else if (m_player->getVacantHousingCapacity() < 3 && c.houseSite == 0 &&
                 c.houseDone + c.houseSite < MAX_HOUSES)
        {
            requestBuilding(m_houseType);
        }
        else if (c.tcDone > 0 && c.houseDone >= 1 && c.barracksDone + c.barracksSite == 0)
        {
            requestBuilding(m_barracksType);
        }

        // 2. Latih unit
        if (c.tc != entt::null)
            produce(c.tc, m_villagerType, c.villagers.size(), TARGET_VILLAGERS);
        if (c.barracks != entt::null)
            produce(c.barracks, m_militiaType, c.army.size(), TARGET_ARMY);

        // 3. Villager menganggur membantu membangun
        if (!c.sites.empty())
        {
            for (auto villager : c.villagers)
            {
                auto& unit = m_stateMan->getComponent<core::CompUnit>(villager);
                if (unit.commandQueue.size() <= 1)
                    orderBuild(villager, c.sites.front());
            }
        }

        // 4. Gelombang serangan
        updateWave(c);
    }

    void requestBuilding(uint32_t type)
    {
        // Petak calon lokasi di sekitar pangkalan (jarak 7 petak agar tidak bertabrakan).
        // Tiap permintaan memakai petak baru; bila ditolak (mis. terhalang pohon), langkah
        // berikutnya otomatis mencoba petak lain.
        static const int offsets[][2] = {
            {0, 0},   {7, 0},   {0, 7},   {-7, 0}, {0, -7},   {7, 7},    {-7, 7},
            {7, -7},  {-7, -7}, {14, 0},  {0, 14}, {-14, 0},  {0, -14},  {14, 7},
            {7, 14},  {-14, 7}, {7, -14}, {14, 14}, {-14, -14}, {14, -14}, {-14, 14}};
        constexpr int count = static_cast<int>(sizeof(offsets) / sizeof(offsets[0]));

        if (m_slot >= count)
            return; // Semua petak sudah dicoba

        const int slot = m_slot++;
        const core::Tile tile(m_baseX + offsets[slot][0], m_baseY + offsets[slot][1]);

        core::BuildingPlacementData data;
        data.player = m_player;
        data.entityType = type;
        data.pos = tile.centerInFeet();

        spdlog::info("[AI] Meminta bangunan tipe {} di tile {}", type, tile.toString());
        core::publishEvent(core::Event::Type::BUILDING_REQUESTED, data);
    }

    void produce(uint32_t building, uint32_t unitType, size_t have, size_t target)
    {
        auto& factory = m_stateMan->getComponent<core::CompUnitFactory>(building);
        const size_t queued = factory.productionQueue.size();
        if (queued >= 2 || have + queued >= target)
            return;

        core::UnitQueueData data;
        data.player = m_player;
        data.entityType = unitType;
        data.building = building;
        core::publishEvent(core::Event::Type::UNIT_QUEUE_REQUEST, data);
    }

    void orderBuild(uint32_t villager, uint32_t site)
    {
        if (!m_stateMan->hasComponent<core::CompBuilder>(villager))
            return;

        auto cmd = core::ObjectPool<core::CmdBuild>::acquire();
        cmd->target = site;
        core::publishEvent(core::Event::Type::COMMAND_REQUEST,
                           core::CommandRequestData{cmd, villager});
    }

    void updateWave(const Census& c)
    {
        if (!m_waveActive)
        {
            if (m_elapsedMs >= m_nextWaveMs && c.army.size() >= MIN_WAVE_SIZE)
            {
                m_waveActive = true;
                m_waveEndMs = m_elapsedMs + WAVE_DURATION_MS;
                m_lastRetargetMs = m_elapsedMs - RETARGET_MS; // Langsung pilih sasaran
                spdlog::info("[AI] Gelombang serangan dimulai dengan {} unit", c.army.size());
            }
            return;
        }

        if (m_elapsedMs >= m_waveEndMs || c.army.empty())
        {
            m_waveActive = false;
            m_nextWaveMs = m_elapsedMs + WAVE_GAP_MS;
            spdlog::info("[AI] Gelombang serangan berakhir");
            return;
        }

        if (m_elapsedMs - m_lastRetargetMs < RETARGET_MS)
            return;
        m_lastRetargetMs = m_elapsedMs;

        // Titik tengah pasukan
        float cx = 0, cy = 0;
        for (auto unit : c.army)
        {
            const auto& tr = m_stateMan->getComponent<core::CompTransform>(unit);
            cx += tr.position.x;
            cy += tr.position.y;
        }
        const core::Feet centroid(cx / c.army.size(), cy / c.army.size());

        const uint32_t target = findNearestEnemyTarget(centroid);
        if (target == entt::null)
        {
            // Tidak ada sasaran tersisa; akhiri gelombang
            m_waveActive = false;
            m_nextWaveMs = m_elapsedMs + WAVE_GAP_MS;
            return;
        }

        for (auto unit : c.army)
        {
            auto cmd = core::ObjectPool<core::CmdAttack>::acquire();
            cmd->target = target;
            core::publishEvent(core::Event::Type::COMMAND_REQUEST,
                               core::CommandRequestData{cmd, unit});
        }
    }

    // Sasaran: unit atau bangunan milik pemain lain (bukan alam) yang punya darah
    uint32_t findNearestEnemyTarget(const core::Feet& from)
    {
        uint32_t best = entt::null;
        float bestDist = std::numeric_limits<float>::max();

        m_stateMan->getEntities<core::CompPlayer, core::CompEntityInfo, core::CompTransform,
                                core::CompHealth>()
            .each(
                [&](uint32_t entity, core::CompPlayer& pc, core::CompEntityInfo& info,
                    core::CompTransform& tr, core::CompHealth&)
                {
                    if (!pc.player || isMine(pc) || info.isDestroyed ||
                        pc.player->getId() == core::Constants::NATURE_PLAYER_ID)
                        return;

                    if (auto unit = m_stateMan->tryGetComponent<core::CompUnit>(entity))
                    {
                        if (unit->isGarrisoned)
                            return;
                    }

                    const float d = tr.position.distanceSquared(from);
                    if (d < bestDist)
                    {
                        bestDist = d;
                        best = entity;
                    }
                });
        return best;
    }

    // Census

    bool isMine(const core::CompPlayer& pc) const
    {
        return pc.player && pc.player->isSame(m_player);
    }

    Census takeCensus()
    {
        Census c;

        m_stateMan->getEntities<core::CompUnit, core::CompPlayer, core::CompEntityInfo>().each(
            [&](uint32_t entity, core::CompUnit& unit, core::CompPlayer& pc,
                core::CompEntityInfo& info)
            {
                if (!isMine(pc) || info.isDestroyed || unit.isGarrisoned)
                    return;

                if (info.entityType.value() == m_villagerType)
                {
                    c.villagers.push_back(entity);
                }
                else if (m_stateMan->hasComponent<core::CompMeleeAttack>(entity) ||
                         m_stateMan->hasComponent<core::CompRangeAttack>(entity))
                {
                    c.army.push_back(entity);
                }
            });

        m_stateMan->getEntities<core::CompBuilding, core::CompPlayer, core::CompEntityInfo>().each(
            [&](uint32_t entity, core::CompBuilding& building, core::CompPlayer& pc,
                core::CompEntityInfo& info)
            {
                if (!isMine(pc) || info.isDestroyed)
                    return;

                const uint32_t type = info.entityType.value();
                const bool done = building.isConstructed();
                if (!done)
                    c.sites.push_back(entity);

                if (type == m_tcType)
                {
                    if (done)
                    {
                        ++c.tcDone;
                        c.tc = entity;
                    }
                    else
                        ++c.tcSite;
                }
                else if (type == m_houseType)
                {
                    if (done)
                        ++c.houseDone;
                    else
                        ++c.houseSite;
                }
                else if (type == m_barracksType)
                {
                    if (done)
                    {
                        ++c.barracksDone;
                        c.barracks = entity;
                    }
                    else
                        ++c.barracksSite;
                }
            });
        return c;
    }

  private:
    uint8_t m_playerId;
    int m_baseX;
    int m_baseY;

    bool m_ready = false;
    core::Ref<core::Player> m_player;
    core::Ref<core::StateManager> m_stateMan;
    core::Ref<core::EntityTypeRegistry> m_types;

    uint32_t m_villagerType = 0;
    uint32_t m_militiaType = 0;
    uint32_t m_tcType = 0;
    uint32_t m_houseType = 0;
    uint32_t m_barracksType = 0;

    int m_slot = 0;
    int m_elapsedMs = 0;
    int m_sinceStepMs = 0;

    bool m_waveActive = false;
    int m_nextWaveMs = FIRST_WAVE_MS;
    int m_waveEndMs = 0;
    int m_lastRetargetMs = 0;
};
} // namespace game

#endif // GAME_ENEMYAI_H
