#include "search.hpp"

#include "logger.hpp"
#include "text_utils.hpp"

#include <algorithm>
#include <chrono>
#include <cctype>

namespace lx::engine {
namespace {

inline char fold_char(char c, bool case_sensitive) {
    if (case_sensitive) {
        return c;
    }
    return static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
}

inline bool is_word_match(const std::string& text, size_t pos, size_t len) {
    if (pos > 0 && is_word_char(static_cast<unsigned char>(text[pos - 1]))) {
        return false;
    }
    if (pos + len < text.size() && is_word_char(static_cast<unsigned char>(text[pos + len]))) {
        return false;
    }
    return true;
}

inline bool matches_at(const std::string& text, const std::string& query, size_t pos, bool case_sensitive) {
    for (size_t j = 0; j < query.size(); ++j) {
        if (fold_char(text[pos + j], case_sensitive) != fold_char(query[j], case_sensitive)) {
            return false;
        }
    }
    return true;
}

inline int find_next_position_impl(
    const std::string& text,
    const std::string& query,
    bool case_sensitive,
    bool whole_words,
    size_t start_pos,
    bool wrap) {
    if (query.empty() || text.empty() || query.size() > text.size()) {
        return -1;
    }

    const size_t tlen = text.size();
    const size_t qlen = query.size();
    const size_t max_pos = tlen - qlen;
    const size_t normalized_start = std::min(start_pos, max_pos + 1);
    const char first_query = fold_char(query[0], case_sensitive);

    auto scan_range = [&](size_t begin, size_t end_exclusive) -> int {
        if (begin >= end_exclusive) {
            return -1;
        }

        for (size_t i = begin; i < end_exclusive; ++i) {
            if (fold_char(text[i], case_sensitive) != first_query) {
                continue;
            }
            if (!matches_at(text, query, i, case_sensitive)) {
                continue;
            }
            if (whole_words && !is_word_match(text, i, qlen)) {
                continue;
            }
            return static_cast<int>(i);
        }

        return -1;
    };

    const int direct = scan_range(normalized_start, max_pos + 1);
    if (direct >= 0 || !wrap || normalized_start == 0) {
        return direct;
    }

    return scan_range(0, normalized_start);
}

}  // namespace

std::vector<int> find_all(const std::string& text, const std::string& query, bool case_sensitive, bool whole_words) {
    const auto start = std::chrono::high_resolution_clock::now();
    std::vector<int> positions;

    if (query.empty() || text.empty() || query.size() > text.size()) {
        return positions;
    }

    const size_t tlen = text.size();
    const size_t qlen = query.size();
    const char first_query = fold_char(query[0], case_sensitive);

    for (size_t i = 0; i + qlen <= tlen; ++i) {
        if (fold_char(text[i], case_sensitive) != first_query) {
            continue;
        }

        if (!matches_at(text, query, i, case_sensitive)) {
            continue;
        }

        if (whole_words && !is_word_match(text, i, qlen)) {
            continue;
        }

        positions.push_back(static_cast<int>(i));
    }

    const auto end = std::chrono::high_resolution_clock::now();
    const std::chrono::duration<double, std::milli> elapsed = end - start;
    log_to_py(
        "Found " + std::to_string(positions.size()) + " matches in " + std::to_string(elapsed.count()) + " ms",
        "SUCCESS");

    return positions;
}

int find_next_position(
    const std::string& text,
    const std::string& query,
    bool case_sensitive,
    bool whole_words,
    int start_pos,
    bool wrap) {
    const size_t normalized_start = start_pos <= 0 ? 0 : static_cast<size_t>(start_pos);
    return find_next_position_impl(text, query, case_sensitive, whole_words, normalized_start, wrap);
}

std::string replace_all(const std::string& text, const std::string& query, const std::string& replacement, bool case_sensitive) {
    return replace_all(text, query, replacement, case_sensitive, false);
}

std::string replace_all(
    const std::string& text,
    const std::string& query,
    const std::string& replacement,
    bool case_sensitive,
    bool whole_words) {
    if (query.empty()) {
        return text;
    }

    std::string result;
    result.reserve(text.size());

    const size_t tlen = text.size();
    const size_t qlen = query.size();
    const char first_query = fold_char(query[0], case_sensitive);

    size_t last_pos = 0;
    size_t i = 0;
    size_t replacements = 0;

    while (i + qlen <= tlen) {
        if (fold_char(text[i], case_sensitive) == first_query &&
            matches_at(text, query, i, case_sensitive) &&
            (!whole_words || is_word_match(text, i, qlen))) {
            result.append(text, last_pos, i - last_pos);
            result.append(replacement);
            last_pos = i + qlen;
            i = last_pos;
            ++replacements;
            continue;
        }

        ++i;
    }

    if (replacements == 0) {
        return text;
    }

    result.append(text, last_pos, text.size() - last_pos);
    log_to_py("Replaced " + std::to_string(replacements) + " occurrences.", "SUCCESS");
    return result;
}

}  // namespace lx::engine
