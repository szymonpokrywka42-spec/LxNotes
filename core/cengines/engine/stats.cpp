#include "stats.hpp"

#include "text_utils.hpp"

#include <cctype>

namespace lx::engine {

TextStatistics get_statistics_native(const std::string& text) {
    TextStatistics stats;
    stats.lines = text.empty() ? 0 : 1;
    stats.bytes = text.length();

    bool in_word = false;
    for (size_t i = 0; i < text.length(); ++i) {
        const unsigned char c = static_cast<unsigned char>(text[i]);

        if (is_utf8_boundary(c)) {
            ++stats.chars;
        }
        if (c == '\n') {
            ++stats.lines;
        }

        if (std::isspace(c)) {
            in_word = false;
        } else if (!in_word) {
            in_word = true;
            ++stats.words;
        }
    }

    return stats;
}

}  // namespace lx::engine

