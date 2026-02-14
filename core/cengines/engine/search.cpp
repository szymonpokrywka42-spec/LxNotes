#include "search.hpp"

#include "logger.hpp"
#include "text_utils.hpp"

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

        bool full_match = true;
        for (size_t j = 1; j < qlen; ++j) {
            if (fold_char(text[i + j], case_sensitive) != fold_char(query[j], case_sensitive)) {
                full_match = false;
                break;
            }
        }

        if (!full_match) {
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

std::string replace_all(const std::string& text, const std::string& query, const std::string& replacement, bool case_sensitive) {
    if (query.empty()) {
        return text;
    }

    const std::vector<int> targets = find_all(text, query, case_sensitive, false);
    if (targets.empty()) {
        return text;
    }

    const long long delta = static_cast<long long>(replacement.size()) - static_cast<long long>(query.size());
    const size_t expected_size = static_cast<size_t>(
        std::max<long long>(0, static_cast<long long>(text.size()) + delta * static_cast<long long>(targets.size())));

    std::string result;
    result.reserve(expected_size);

    size_t last_pos = 0;
    for (int pos : targets) {
        const size_t current = static_cast<size_t>(pos);
        result.append(text, last_pos, current - last_pos);
        result.append(replacement);
        last_pos = current + query.size();
    }
    result.append(text, last_pos, text.size() - last_pos);

    log_to_py("Replaced " + std::to_string(targets.size()) + " occurrences.", "SUCCESS");
    return result;
}

}  // namespace lx::engine

