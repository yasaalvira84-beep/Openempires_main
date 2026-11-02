#!/usr/bin/env python3
"""Ekspor definisi entitas Python (assets/scripts/models.py) ke JSON.

Hanya memakai pustaka standar (tanpa pydantic), supaya bisa dijalankan di
GitHub Actions saat build. Hasilnya dimuat oleh C++ (build tanpa Python,
mis. Android) sebagai ganti interpreter Python yang tertanam.

Pemakaian:
    python tools/export_models.py [folder_scripts] [file_keluaran]
Bawaan: assets/scripts -> assets/scripts/models.json
"""
import enum
import json
import sys
from pathlib import Path

# Kelas pembantu yang tidak mewakili komponen perilaku.
SKIP_BASES = {"object", "Constructible", "_Constructible"}

# Nilai bawaan kelas-kelas grafis diatur di sisi C++ (sama seperti binding
# pybind), jadi tidak digabung di sini supaya perilakunya identik.
SKIP_DEFAULTS_MODULES = {"graphic_defs"}


def serialize(value):
    if isinstance(value, enum.Enum):
        return value.value
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple, set, frozenset)):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(serialize(k)): serialize(v) for k, v in value.items()}
    if hasattr(value, "__dict__"):
        return serialize_object(value)
    raise TypeError(f"Tipe tidak didukung: {type(value)!r}")


def serialize_object(obj):
    cls = type(obj)
    out = {"_type": cls.__name__}

    if cls.__module__ not in SKIP_DEFAULTS_MODULES:
        # Nilai bawaan tingkat kelas (mis. base_armor = 1000).
        for klass in reversed(cls.__mro__):
            for name in getattr(klass, "__annotations__", {}):
                if name not in obj.__dict__ and hasattr(cls, name):
                    out[name] = serialize(getattr(cls, name))

    for name, val in obj.__dict__.items():
        out[name] = serialize(val)

    out["_bases"] = [c.__name__ for c in cls.__mro__ if c.__name__ not in SKIP_BASES]
    return out


def main():
    scripts = Path(sys.argv[1] if len(sys.argv) > 1 else "assets/scripts").resolve()
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else scripts / "models.json"
    sys.path.insert(0, str(scripts))

    import models  # noqa: E402  (bergantung pada sys.path di atas)

    data = {
        "entity_names": list(models.all_entity_names),
        "all_models": [serialize(x) for x in models.all_models],
    }
    target.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Ditulis {target} ({target.stat().st_size} byte): {len(data['all_models'])} entitas")


if __name__ == "__main__":
    main()
