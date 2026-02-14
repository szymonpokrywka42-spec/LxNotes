#include "text_utils.hpp"

#include <algorithm>
#include <cctype>

namespace lx::engine {

bool is_utf8_boundary(unsigned char c) { return (c & 0xC0) != 0x80; }

bool is_word_char(unsigned char c) {
    if (c > 127) {
        return true;
    }
    return std::isalnum(c) || c == '_';
}

int get_line_offset(const std::string& text, int line_number) {
    if (line_number <= 1) {
        return 0;
    }

    int current_line = 1;
    for (size_t i = 0; i < text.length(); ++i) {
        if (text[i] == '\n') {
            ++current_line;
            if (current_line == line_number) {
                return static_cast<int>(i + 1);
            }
        }
    }
    return -1;
}

std::vector<int> get_line_offsets(const std::string& text) {
    std::vector<int> offsets;
    offsets.reserve(64);
    offsets.push_back(0);

    for (size_t i = 0; i < text.length(); ++i) {
        if (text[i] == '\n' && i + 1 < text.length()) {
            offsets.push_back(static_cast<int>(i + 1));
        }
    }
    return offsets;
}

std::string prepare_large_text(const std::string& input) {
    if (input.length() < 50000) {
        return input;
    }

    std::string result;
    result.reserve(input.length() + (input.length() / 1000) + 1);

    const size_t chunk = 1000;
    for (size_t i = 0; i < input.length(); i += chunk) {
        const size_t len = std::min(chunk, input.length() - i);
        result.append(input, i, len);
        if (i + chunk < input.length()) {
            result.push_back('\n');
        }
    }
    return result;
}

}  // namespace lx::engine
