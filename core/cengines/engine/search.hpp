#pragma once

#include <string>
#include <vector>

namespace lx::engine {

std::vector<int> find_all(const std::string& text, const std::string& query, bool case_sensitive, bool whole_words);
int find_next_position(
    const std::string& text,
    const std::string& query,
    bool case_sensitive,
    bool whole_words,
    int start_pos,
    bool wrap);
std::string replace_all(const std::string& text, const std::string& query, const std::string& replacement, bool case_sensitive);
std::string replace_all(
    const std::string& text,
    const std::string& query,
    const std::string& replacement,
    bool case_sensitive,
    bool whole_words);

}  // namespace lx::engine
