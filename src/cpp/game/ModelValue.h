#ifndef GAME_MODELVALUE_H
#define GAME_MODELVALUE_H

// Lapisan tipis yang memisahkan EntityModelLoaderV2 dari sumber definisi entitas.
//
//  - OE_USE_PYTHON terdefinisi : definisi dibaca langsung dari objek Python (desktop,
//                                perilaku lama tidak berubah).
//  - OE_USE_PYTHON tidak ada   : definisi dibaca dari models.json yang dibuat oleh
//                                tools/export_models.py (mis. build Android).

#include <map>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <vector>

#ifdef OE_USE_PYTHON
#include <pybind11/embed.h>
#include <pybind11/stl.h>
#else
#include <nlohmann/json.hpp>
#endif

namespace game
{
#ifdef OE_USE_PYTHON

using ModelValue = pybind11::object; // Pemilik referensi
using ModelRef = pybind11::handle;   // Referensi pinjaman

namespace mv
{
inline bool has(const ModelValue& obj, const std::string& name)
{
    return pybind11::hasattr(obj, name.c_str());
}

inline ModelValue get(const ModelValue& obj, const std::string& name)
{
    return obj.attr(name.c_str());
}

template <typename T> T as(const ModelRef& value)
{
    return value.cast<T>();
}

inline ModelRef ref(const ModelValue& value)
{
    return value;
}

// Elemen dari sebuah list/tuple Python
inline std::vector<ModelValue> items(const ModelValue& list)
{
    std::vector<ModelValue> result;
    for (auto item : list)
        result.push_back(pybind11::reinterpret_borrow<pybind11::object>(item));
    return result;
}
} // namespace mv

#else

using ModelValue = nlohmann::json;
using ModelRef = nlohmann::json;

namespace mv
{
namespace detail
{
template <typename T> struct IsIntKeyMap : std::false_type
{
};
template <typename V, typename C, typename A>
struct IsIntKeyMap<std::map<int, V, C, A>> : std::true_type
{
};
template <typename V, typename H, typename E, typename A>
struct IsIntKeyMap<std::unordered_map<int, V, H, E, A>> : std::true_type
{
};
} // namespace detail

inline bool has(const ModelValue& obj, const std::string& name)
{
    return obj.is_object() && obj.contains(name);
}

inline ModelValue get(const ModelValue& obj, const std::string& name)
{
    return obj.at(name);
}

template <typename T> T as(const ModelRef& value)
{
    if constexpr (detail::IsIntKeyMap<T>::value)
    {
        // Kunci objek JSON selalu string, sedangkan di Python kuncinya int (mis. ArmorClass).
        T result;
        for (auto it = value.begin(); it != value.end(); ++it)
            result.emplace(std::stoi(it.key()), it.value().template get<typename T::mapped_type>());
        return result;
    }
    else
    {
        return value.template get<T>();
    }
}

inline ModelRef ref(const ModelValue& value)
{
    return value;
}

inline std::vector<ModelValue> items(const ModelValue& array)
{
    return std::vector<ModelValue>(array.begin(), array.end());
}
} // namespace mv

#endif
} // namespace game

#endif // GAME_MODELVALUE_H
