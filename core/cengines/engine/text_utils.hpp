#pragma once

#include <string>
#include <vector>

namespace lx::engine {

bool is_utf8_boundary(unsigned char c);
bool is_word_char(unsigned char c);

int get_line_offset(const std::string& text, int line_number);
std::vector<int> get_line_offsets(const std::string& text);
std::string prepare_large_text(const std::string& input);

}  // namespace lx::engine

