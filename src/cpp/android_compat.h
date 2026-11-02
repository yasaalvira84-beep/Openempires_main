// Header kompatibilitas Android. Di-include paksa ke setiap file C++ lewat flag compiler
// (-include), lihat .github/workflows/android.yml.
//
// Kode asli hanya diuji dengan MSVC, yang menyertakan banyak header standar secara tidak
// langsung. Dengan libc++ (NDK) header-header itu harus disertakan secara eksplisit.
#pragma once

#include <math.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include <numeric>
#include <optional>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <variant>
#include <vector>

// <math.h> milik Bionic mendefinisikan makro HUGE, yang bentrok dengan enum
// FlameLevel::HUGE di core/utils/Types.h.
#ifdef HUGE
#undef HUGE
#endif
