#pragma once

#include <cstddef>
#include <string>

namespace lx::engine {

struct TextStatistics {
    size_t chars = 0;
    size_t words = 0;
    size_t lines = 0;
    size_t bytes = 0;
};

TextStatistics get_statistics_native(const std::string& text);

}  // namespace lx::engine

