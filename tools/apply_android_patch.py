#!/usr/bin/env python3
"""Menerapkan perubahan loader JSON (build tanpa Python) pada kode asli OpenEmpires.

Dijalankan oleh .github/workflows/android.yml setelah kode asli diambil, dari root repo:
    python tools/apply_android_patch.py
Setiap penggantian di-assert tepat satu kali, jadi kalau kode asli berubah, skrip gagal
dengan jelas dan tidak merusak file diam-diam.
"""
import sys

GAME = 'src/cpp/game/'

JSON_BLOCK = r'''#else // OE_USE_PYTHON

// Pembaca JSON untuk struktur grafis di atas. Nilai bawaan (mis. drs_file, frame_count) sama
// dengan yang dipakai binding pybind di build Python.
namespace nlohmann
{
template <> struct adl_serializer<core::Vec2>
{
    static void from_json(const json& j, core::Vec2& v)
    {
        v = core::Vec2(j.at("x").get<int>(), j.at("y").get<int>());
    }
};

template <> struct adl_serializer<core::Rect<int>>
{
    static void from_json(const json& j, core::Rect<int>& r)
    {
        r = core::Rect<int>(j.at("x").get<int>(), j.at("y").get<int>(), j.at("w").get<int>(),
                            j.at("h").get<int>());
    }
};
} // namespace nlohmann

namespace
{
template <typename T> std::optional<T> optField(const nlohmann::json& j, const char* key)
{
    const auto it = j.find(key);
    if (it == j.end() || it->is_null())
        return std::nullopt;
    return it->template get<T>();
}

template <typename T> T fieldOr(const nlohmann::json& j, const char* key, const T& fallback)
{
    return optField<T>(j, key).value_or(fallback);
}
} // namespace

void from_json(const nlohmann::json& j, SingleGraphic& g)
{
    g.drsFile = fieldOr<std::string>(j, "drs_file", "graphics.drs");
    g.slp_id = j.at("slp_id").get<int>();
    g.anchor = optField<Vec2>(j, "anchor");
    g.frameIndex = optField<int>(j, "frame_index");
    g.clipRect = optField<Rect<int>>(j, "clip_rect");
    g.flip = optField<bool>(j, "flip");
}

void from_json(const nlohmann::json& j, CompositeGraphic& g)
{
    g.parts = j.at("parts").get<std::vector<SingleGraphic>>();
    g.anchor = j.at("anchor").get<Vec2>();
    g.flip = optField<bool>(j, "flip");
}

void from_json(const nlohmann::json& j, GraphicVariant& v)
{
    const auto& graphic = j.at("graphic");
    if (graphic.at("_type").get<std::string>() == "CompositeGraphic")
        v.graphic = graphic.get<CompositeGraphic>();
    else
        v.graphic = graphic.get<SingleGraphic>();

    v.variationFilter = fieldOr<std::map<std::string, std::string>>(j, "variation_filter", {});
}

void from_json(const nlohmann::json& j, Graphic& g)
{
    g.variants = j.at("variants").get<std::vector<GraphicVariant>>();
    g.layer = j.at("layer").get<GraphicLayer>();
}

void from_json(const nlohmann::json& j, AnimationVariant& a)
{
    a.name = j.at("name").get<std::string>();
    a.frameCount = fieldOr<int>(j, "frame_count", 15);
    a.speed = fieldOr<float>(j, "speed", 10.0f);
    a.slpId = j.at("slp_id").get<int>();
    a.drsFile = fieldOr<std::string>(j, "drs_file", "graphics.drs");
    a.repeatable = fieldOr<bool>(j, "repeatable", true);
    a.variationFilter = fieldOr<std::map<std::string, std::string>>(j, "variation_filter", {});
    a.layer = j.at("layer").get<GraphicLayer>();
}

void from_json(const nlohmann::json& j, Animation& a)
{
    a.variants = j.at("variants").get<std::vector<AnimationVariant>>();
}

void from_json(const nlohmann::json& j, Shortcut& s)
{
    s.name = j.at("name").get<std::string>();
    s.shortcut = j.at("shortcut").get<std::string>();
}

#endif // OE_USE_PYTHON

'''

STORE_BLOCK = r'''void EntityModelLoaderV2::storeUnprocessedFields(const std::string& entityName,
                                                 const ModelRef& obj,
                                                 const std::list<std::string>& processedFields)
{
    UnprocessedFields unprocessed;

#ifdef OE_USE_PYTHON
    py::dict dict = obj.attr("__dict__");

    for (auto item : dict)
    {
        std::string key = py::cast<std::string>(item.first);

        auto it = std::find(processedFields.begin(), processedFields.end(), key);

        if (it == processedFields.end())
        {
            py::object value = py::reinterpret_borrow<py::object>(item.second);
            unprocessed.fields[key] = value;
        }
    }
#else
    for (auto item = obj.begin(); item != obj.end(); ++item)
    {
        const std::string& key = item.key();

        // Kunci berawalan "_" (_type, _bases) adalah metadata dari export_models.py
        if (key.starts_with('_'))
            continue;

        auto it = std::find(processedFields.begin(), processedFields.end(), key);

        if (it == processedFields.end())
            unprocessed.fields[key] = item.value();
    }
#endif

    if (not unprocessed.fields.empty())
        m_unprocessedFieldsByEntityName[entityName] = unprocessed;
}

'''

LOADJSON_BLOCK = r'''#else
ModelValue EntityModelLoaderV2::loadModelImporterModule()
{
    // models.json dibuat oleh tools/export_models.py dari assets/scripts/models.py
    const std::string path = m_scriptDir + "/models.json";
    std::ifstream file(path);

    if (not file)
        throw std::runtime_error("Failed to open entity models file: " + path);

    return nlohmann::json::parse(file);
}

void EntityModelLoaderV2::initPython()
{
    // Tidak ada interpreter Python di build ini.
}
#endif

void EntityModelLoaderV2::loadUnprogressedFields()
{
'''

VALIDATE_BLOCK = r'''#ifdef OE_USE_PYTHON
void validateEntities(py::object module)
{
    py::object validateAllFunc = module.attr("validate_all");
    py::object result = validateAllFunc();
    bool success = result.cast<bool>();

    if (success == false)
    {
        throw std::runtime_error("Entity validation failed");
    }
    else
    {
        spdlog::debug("Entity validation passed");
    }
}

bool isInstanceOf(const ModelValue& module,
                  const ModelValue& entityDefinition,
                  const std::string& baseClass)
{
    if (py::hasattr(module, baseClass.c_str()))
    {
        py::object cls = module.attr(baseClass.c_str());
        if (py::isinstance(entityDefinition, cls))
        {
            return true;
        }
    }
    return false;
}
#else
bool isInstanceOf(const ModelValue&,
                  const ModelValue& entityDefinition,
                  const std::string& baseClass)
{
    // export_models.py menyimpan nama semua kelas induk (MRO) di "_bases"
    const auto it = entityDefinition.find("_bases");
    if (it == entityDefinition.end())
        return false;

    return std::find(it->begin(), it->end(), baseClass) != it->end();
}
#endif

'''

PROJ_BLOCK = r'''core::ProjectileProperties getProjectile(const std::any& value)
{
    auto pyObj = std::any_cast<ModelValue>(value);
    ModelValue attackObj = mv::get(pyObj, "attack");
    auto attacks = getAttackOrArmorPerClass(attackObj);
    ModelValue attackMulObj = mv::get(pyObj, "attack_multiplier");
    auto attackMultipliers = getMultiplierPerClass(attackMulObj);
    auto accuracy = mv::as<float>(mv::get(pyObj, "accuracy"));
    auto reloadTimeS = mv::as<float>(mv::get(pyObj, "reload_time"));

    return ProjectileProperties(attacks, attackMultipliers, accuracy, reloadTimeS);
}

std::vector<core::ProjectileProperties> getProjectilesList(const std::any& value)
{
    auto pyObj = std::any_cast<ModelValue>(value);

    std::vector<ProjectileProperties> projectiles;
    for (const auto& item : mv::items(pyObj))
    {
        projectiles.push_back(getProjectile(item));
    }
    return projectiles;
}
'''


def edit_header():
    p = GAME + 'EntityModelLoaderV2.h'
    s = open(p, encoding='utf-8').read().replace('\r\n', '\n')

    def rep(old, new):
        nonlocal s
        assert s.count(old) == 1, (old[:70], s.count(old))
        s = s.replace(old, new)

    rep('#include "GraphicsLoadupDataProvider.h"\n', '#include "GraphicsLoadupDataProvider.h"\n#include "ModelValue.h"\n')
    rep('#include <optional>\n#include <pybind11/embed.h>\n#include <variant>', '#include <optional>\n#include <variant>')
    rep('    void loadAll(const pybind11::object& module);\n    void loadEntityTypes(const pybind11::object& module);', '    void loadAll(const ModelValue& module);\n    void loadEntityTypes(const ModelValue& module);')
    rep('    pybind11::object loadModelImporterModule();', '    ModelValue loadModelImporterModule();')
    rep('template <typename T> std::list<std::string> enrich(T& comp, const pybind11::object& obj)', 'template <typename T> std::list<std::string> enrich(T& comp, const ModelValue& obj)')
    rep('if (pybind11::hasattr(obj, name.c_str()))', 'if (mv::has(obj, name))')
    rep('pybind11::object value = obj.attr(name.c_str());', 'ModelValue value = mv::get(obj, name);')
    rep('(*mappings.converterFuncStr)(value.cast<std::string>());', '(*mappings.converterFuncStr)(mv::as<std::string>(value));')
    rep('(*mappings.converterFuncInt)(value.cast<int>());', '(*mappings.converterFuncInt)(mv::as<int>(value));')
    rep('value.cast<Value>());', 'mv::as<Value>(value));')
    rep('(*mappings.converterFunc)(value);', '(*mappings.converterFunc)(std::any(value));')
    rep('std::list<std::string> createAndEnrichComponent(ComponentType& c, const pybind11::object& obj)', 'std::list<std::string> createAndEnrichComponent(ComponentType& c, const ModelValue& obj)')
    rep('std::list<std::string> (EntityModelLoaderV2::*)(ComponentType&, const pybind11::object&);', 'std::list<std::string> (EntityModelLoaderV2::*)(ComponentType&, const ModelValue&);')
    rep('std::map<std::string, pybind11::handle> fields;', 'std::map<std::string, ModelRef> fields;')
    rep('                                const pybind11::handle& obj,', '                                const ModelRef& obj,')
    assert 'pybind11' not in s
    open(p, 'w', encoding='utf-8', newline='').write(s)


def edit_cpp():
    p = GAME + 'EntityModelLoaderV2.cpp'
    raw=open(p,'rb').read()
    bom=raw.startswith(b'\xef\xbb\xbf'); crlf=b'\r\n' in raw
    s=raw.decode('utf-8-sig').replace('\r\n','\n')
    print("bom",bom,"crlf",crlf)

    def rep(old,new,count=1):
        nonlocal s
        assert s.count(old)==count,(old[:70],s.count(old))
        s=s.replace(old,new)

    rep('#include <array>\n#include <filesystem>\n#include <pybind11/stl.h>\n#include <variant>',
        '#include <algorithm>\n#include <array>\n#include <filesystem>\n#include <fstream>\n#include <variant>')
    rep('namespace py = pybind11;\n','#ifdef OE_USE_PYTHON\nnamespace py = pybind11;\n#endif\n')
    rep('void validatePython();\nvoid validateEntities(py::object module);\nbool isInstanceOf(py::object module, py::handle entityDefinition, const std::string& baseClass);\n',
        '#ifdef OE_USE_PYTHON\nvoid validatePython();\nvoid validateEntities(py::object module);\n#endif\nbool isInstanceOf(const ModelValue& module,\n                  const ModelValue& entityDefinition,\n                  const std::string& baseClass);\n')

    a=s.index('template <typename T> static T readValue(py::handle object')
    b=s.index('template <typename Variant, typename F> struct VariantForEach;')
    s=s[:a]+'#ifdef OE_USE_PYTHON\n'+s[a:b].rstrip('\n')+'\n#endif\n\n'+s[b:]

    a=s.index('PYBIND11_EMBEDDED_MODULE(graphic_defs, m)')
    marker='//////////////////////////////////////////////////////////////////////////\n// Implementation of EntityModelLoaderV2'
    b=s.index(marker)
    pybind_block=s[a:b].rstrip('\n')+'\n'
    json_block=JSON_BLOCK
    s=s[:a]+'#ifdef OE_USE_PYTHON\n'+pybind_block+'\n'+json_block+s[b:]

    rep('    initPython();\n    validatePython();\n    auto module = loadModelImporterModule();\n    validateEntities(module);\n',
        '    initPython();\n#ifdef OE_USE_PYTHON\n    validatePython();\n#endif\n    auto module = loadModelImporterModule();\n#ifdef OE_USE_PYTHON\n    validateEntities(module);\n#endif\n')

    rep('void EntityModelLoaderV2::loadEntityTypes(const py::object& module)\n{\n    py::object pyNames = module.attr("all_entity_names");\n    std::vector<std::string> entityNames = pyNames.cast<std::vector<std::string>>();\n',
        'void EntityModelLoaderV2::loadEntityTypes(const ModelValue& module)\n{\n#ifdef OE_USE_PYTHON\n    py::object pyNames = module.attr("all_entity_names");\n    std::vector<std::string> entityNames = pyNames.cast<std::vector<std::string>>();\n#else\n    auto entityNames = module.at("entity_names").get<std::vector<std::string>>();\n#endif\n')

    rep('void EntityModelLoaderV2::loadAll(const py::object& module)\n{\n    for (auto pyModel : module.attr("all_models"))\n    {\n        py::object pyObj = py::reinterpret_borrow<py::object>(pyModel);\n',
        'void EntityModelLoaderV2::loadAll(const ModelValue& module)\n{\n#ifdef OE_USE_PYTHON\n    const auto allModels = mv::items(module.attr("all_models"));\n#else\n    const auto allModels = mv::items(module.at("all_models"));\n#endif\n\n    for (const ModelValue& pyObj : allModels)\n    {\n')
    rep('if (isInstanceOf(module, pyModel, modelNameStr))','if (isInstanceOf(module, pyObj, modelNameStr))')
    rep('storeUnprocessedFields(entityName, pyObj.ptr(), allProcessedFields);','storeUnprocessedFields(entityName, mv::ref(pyObj), allProcessedFields);')

    a=s.index('void EntityModelLoaderV2::storeUnprocessedFields(')
    b=s.index('void EntityModelLoaderV2::preprocessComponents()')
    s=s[:a]+STORE_BLOCK+s[b:]

    rep('auto graphic = pyObj.cast<Graphic>();','auto graphic = mv::as<Graphic>(pyObj);')
    rep('auto animation = pyObj.cast<Animation>();','auto animation = mv::as<Animation>(pyObj);')

    rep('py::object EntityModelLoaderV2::loadModelImporterModule()','#ifdef OE_USE_PYTHON\nModelValue EntityModelLoaderV2::loadModelImporterModule()')
    rep('void EntityModelLoaderV2::loadUnprogressedFields()\n{', LOADJSON_BLOCK)

    rep('void validatePython()\n{','#ifdef OE_USE_PYTHON\nvoid validatePython()\n{')
    rep('std::unordered_map<char, uint32_t> getShortcuts(const std::any& value)','#endif // OE_USE_PYTHON\n\nstd::unordered_map<char, uint32_t> getShortcuts(const std::any& value)')
    a=s.index('void validateEntities(py::object module)\n{')   # definisi, bukan deklarasi
    b=s.index('std::vector<int> getAttackOrArmorPerClass(const std::any& value)\n{')
    s=s[:a]+VALIDATE_BLOCK+s[b:]

    print("any_cast count",s.count('auto pyObj = std::any_cast<py::object>(value);'))
    s=s.replace('auto pyObj = std::any_cast<py::object>(value);','auto pyObj = std::any_cast<ModelValue>(value);')
    rep('auto shortcuts = pyObj.cast<std::list<Shortcut>>();','auto shortcuts = mv::as<std::list<Shortcut>>(pyObj);')
    rep('auto acceptedResources = pyObj.cast<std::list<std::string>>();','auto acceptedResources = mv::as<std::list<std::string>>(pyObj);')
    rep('auto unitTypeInts = pyObj.cast<std::list<uint32_t>>();','auto unitTypeInts = mv::as<std::list<uint32_t>>(pyObj);')
    rep('auto valuesPerClass = pyObj.cast<std::map<int, int>>();','auto valuesPerClass = mv::as<std::map<int, int>>(pyObj);')
    rep('auto valuesPerClass = pyObj.cast<std::map<int, float>>();','auto valuesPerClass = mv::as<std::map<int, float>>(pyObj);')
    rep('auto valueInt = pyObj.cast<int>();','auto valueInt = mv::as<int>(pyObj);')
    a=s.index('core::ProjectileProperties getProjectile(const std::any& value)\n{')
    print("DIBUANG:\n"+s[a:][-260:])
    s=s[:a]+PROJ_BLOCK
    out=s
    if crlf: out=out.replace('\n','\r\n')
    open(p,'wb').write((b'\xef\xbb\xbf' if bom else b'')+out.encode('utf-8'))
    print("cpp patched")

    s = open(p, encoding='utf-8').read()
    for old, new in [
        ('auto attacks = getAttackOrArmorPerClass(attackObj);', 'auto attacks = getAttackOrArmorPerClass(std::any(attackObj));'),
        ('auto attackMultipliers = getMultiplierPerClass(attackMulObj);', 'auto attackMultipliers = getMultiplierPerClass(std::any(attackMulObj));'),
        ('projectiles.push_back(getProjectile(item));', 'projectiles.push_back(getProjectile(std::any(item)));'),
    ]:
        assert s.count(old) == 1, old
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8', newline='').write(s)


def edit_game_h():
    p = GAME + 'Game.h'
    s = open(p, encoding='utf-8').read()
    old = '#include <pybind11/embed.h>\n'
    assert s.count(old) == 1
    open(p, 'w', encoding='utf-8', newline='').write(s.replace(old, ''))


if __name__ == '__main__':
    edit_header()
    edit_cpp()
    edit_game_h()
    print('Patch Android diterapkan.')
