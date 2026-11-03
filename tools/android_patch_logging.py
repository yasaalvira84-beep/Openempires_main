#!/usr/bin/env python3
"""Patch logging untuk Android (dijalankan otomatis oleh workflow setelah apply_android_patch.py).

1. tcp_sink.h: spdlog di Linux/Android hanya punya connect(host, port) dengan 2 argumen,
   sedangkan kode asli (ditulis untuk klien TCP Windows) memanggilnya dengan 3 argumen.
2. Logger.cpp: sink TCP (localhost:5000, alat debug) dilewati di Android karena tidak ada penerimanya.
"""

CORE = 'src/cpp/core/logging/'


def edit(path, pairs):
    s = open(path, encoding='utf-8').read().replace('\r\n', '\n')
    for old, new, count in pairs:
        assert s.count(old) == count, (path, old[:60], s.count(old))
        s = s.replace(old, new)
    open(path, 'w', encoding='utf-8', newline='').write(s)


edit(CORE + 'tcp_sink.h', [
    ('#include <spdlog/details/tcp_client.h>\n#endif\n',
     '#include <spdlog/details/tcp_client.h>\n#endif\n\n'
     '#ifdef _WIN32\n'
     '#define OE_TCP_CONNECT(client, config) \\\n'
     '    (client).connect((config).server_host, (config).server_port, (config).timeout_ms)\n'
     '#else\n'
     '#define OE_TCP_CONNECT(client, config) \\\n'
     '    (client).connect((config).server_host, (config).server_port)\n'
     '#endif\n', 1),
    ('client_.connect(config_.server_host, config_.server_port, config_.timeout_ms);',
     'OE_TCP_CONNECT(client_, config_);', 3),
])

edit(CORE + 'Logger.cpp', [
    ('    spdlog::sinks_init_list sinks{consoleSink, fileSink, tcpSink};\n',
     '#ifdef __ANDROID__\n'
     '    // Tidak ada penerima log TCP di Android\n'
     '    spdlog::sinks_init_list sinks{consoleSink, fileSink};\n'
     '#else\n'
     '    spdlog::sinks_init_list sinks{consoleSink, fileSink, tcpSink};\n'
     '#endif\n', 1),
])
print('Patch logging Android diterapkan.')
