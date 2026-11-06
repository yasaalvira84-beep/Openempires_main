#ifndef CORE_PROBELABELS_H
#define CORE_PROBELABELS_H

// Label teks yang digambar Renderer di atas petak (dipakai peta uji medan untuk menampilkan
// nomor SLP langsung di layar). Lihat tools/android_patch_terrain_labels.py. SEMENTARA.

#include <mutex>
#include <string>
#include <vector>

namespace core
{
struct ProbeLabel
{
    int tileX;
    int tileY;
    std::string text;
};

inline std::vector<ProbeLabel>& probeLabels()
{
    static std::vector<ProbeLabel> labels;
    return labels;
}

inline std::mutex& probeLabelsMutex()
{
    static std::mutex m;
    return m;
}
} // namespace core

#endif // CORE_PROBELABELS_H
