#pragma once

#include <string>
#include <vector>

namespace lx::engine {

std::vector<int> find_all(const std::string& text, const std::string& query, bool case_sensitive, bool whole_words);
std::string replace_all(const std::string& text, const std::string& query, const std::string& replacement, bool case_sensitive);

}  // namespace lx::engine

