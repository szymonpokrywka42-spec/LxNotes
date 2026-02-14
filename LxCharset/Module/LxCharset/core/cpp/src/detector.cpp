#include "detector.hpp"

#include <algorithm>
#include <array>
#include <cmath>

namespace lx::encoding {

namespace {
constexpr std::size_t EARLY_EXIT_BYTES = 4096;
constexpr double EARLY_EXIT_CONFIDENCE = 0.98;
constexpr double AMBIGUITY_DELTA = 0.03;
static constexpr std::array<const char*, 13> LANGUAGE_FALLBACK_ORDER = {
    "utf-8",
    "utf-8-sig",
    "utf-16-le",
    "utf-16-be",
    "utf-32-le",
    "utf-32-be",
    "iso-2022-jp",
    "shift_jis",
    "euc_jp",
    "big5",
    "windows-1250",
    "iso-8859-2",
    "latin-1",
};

bool has_prefix(const std::vector<std::uint8_t>& bytes, std::initializer_list<std::uint8_t> prefix) {
    if (bytes.size() < prefix.size()) {
        return false;
    }

    std::size_t i = 0;
    for (auto b : prefix) {
        if (bytes[i++] != b) {
            return false;
        }
    }
    return true;
}

bool contains_byte(const std::array<std::uint8_t, 18>& set, std::uint8_t value) {
    for (std::uint8_t b : set) {
        if (b == value) {
            return true;
        }
    }
    return false;
}

int language_fallback_rank(const std::string& encoding) {
    for (std::size_t i = 0; i < LANGUAGE_FALLBACK_ORDER.size(); ++i) {
        if (encoding == LANGUAGE_FALLBACK_ORDER[i]) {
            return static_cast<int>(i);
        }
    }
    return static_cast<int>(LANGUAGE_FALLBACK_ORDER.size());
}

std::pair<std::string, double> choose_by_language_fallback_map(
    const std::vector<std::pair<std::string, double>>& candidates) {
    if (candidates.empty()) {
        return {"", 0.0};
    }

    double best_conf = -1.0;
    for (const auto& c : candidates) {
        if (!c.first.empty()) {
            best_conf = std::max(best_conf, c.second);
        }
    }
    if (best_conf < 0.0) {
        return {"", 0.0};
    }

    std::string best_encoding;
    double best_selected_conf = 0.0;
    int best_rank = static_cast<int>(LANGUAGE_FALLBACK_ORDER.size()) + 1;
    for (const auto& c : candidates) {
        if (c.first.empty()) {
            continue;
        }
        if ((best_conf - c.second) > AMBIGUITY_DELTA) {
            continue;
        }

        const int rank = language_fallback_rank(c.first);
        if (best_encoding.empty() || rank < best_rank || (rank == best_rank && c.second > best_selected_conf)) {
            best_encoding = c.first;
            best_selected_conf = c.second;
            best_rank = rank;
        }
    }

    if (best_encoding.empty()) {
        return {"", 0.0};
    }
    return {best_encoding, best_selected_conf};
}

}  // namespace

std::array<std::size_t, 256> build_byte_frequency_table(const std::vector<std::uint8_t>& bytes) {
    std::array<std::size_t, 256> table{};
    table.fill(0);
    for (std::uint8_t b : bytes) {
        ++table[b];
    }
    return table;
}

double byte_frequency_ratio(const std::vector<std::uint8_t>& bytes, std::uint8_t byte_value) {
    if (bytes.empty()) {
        return 0.0;
    }
    const auto table = build_byte_frequency_table(bytes);
    return static_cast<double>(table[byte_value]) / static_cast<double>(bytes.size());
}

double distribution_match_score(const std::vector<std::uint8_t>& bytes, bool cp1250) {
    if (bytes.empty()) {
        return 0.0;
    }

    struct DistPoint {
        std::uint8_t byte_value;
        double expected_ratio;
        double weight;
    };

    static constexpr std::array<DistPoint, 14> CP1250_PATTERN{{
        {0xA5, 0.0030, 1.2}, {0xB9, 0.0032, 1.2}, {0x8C, 0.0012, 1.0}, {0x9C, 0.0015, 1.0},
        {0x8F, 0.0010, 1.0}, {0x9F, 0.0012, 1.0}, {0xC6, 0.0025, 0.8}, {0xE6, 0.0028, 0.8},
        {0xCA, 0.0020, 0.8}, {0xEA, 0.0021, 0.8}, {0xD1, 0.0018, 0.7}, {0xF1, 0.0020, 0.7},
        {0xD3, 0.0040, 0.7}, {0xF3, 0.0042, 0.7},
    }};
    static constexpr std::array<DistPoint, 14> ISO88592_PATTERN{{
        {0xA1, 0.0030, 1.2}, {0xB1, 0.0032, 1.2}, {0xA6, 0.0012, 1.0}, {0xB6, 0.0015, 1.0},
        {0xAC, 0.0010, 1.0}, {0xBC, 0.0012, 1.0}, {0xC6, 0.0025, 0.8}, {0xE6, 0.0028, 0.8},
        {0xCA, 0.0020, 0.8}, {0xEA, 0.0021, 0.8}, {0xD1, 0.0018, 0.7}, {0xF1, 0.0020, 0.7},
        {0xD3, 0.0040, 0.7}, {0xF3, 0.0042, 0.7},
    }};

    const auto& pattern = cp1250 ? CP1250_PATTERN : ISO88592_PATTERN;
    const auto table = build_byte_frequency_table(bytes);
    const double total = static_cast<double>(bytes.size());

    double weighted_distance = 0.0;
    double weight_sum = 0.0;
    for (const auto& p : pattern) {
        const double actual_ratio = static_cast<double>(table[p.byte_value]) / total;
        weighted_distance += std::abs(actual_ratio - p.expected_ratio) * p.weight;
        weight_sum += p.weight;
    }

    if (weight_sum <= 0.0) {
        return 0.0;
    }
    const double normalized_distance = weighted_distance / weight_sum;
    return std::max(0.0, std::min(1.0, 1.0 - normalized_distance * 20.0));
}

double calculate_transition_confidence(int valid_transitions, int invalid_transitions) {
    const int v = std::max(0, valid_transitions);
    const int i = std::max(0, invalid_transitions);
    return static_cast<double>(v + 1) / static_cast<double>(v + i + 2);
}

bool validate_utf8_dfa(
    const std::vector<std::uint8_t>& bytes,
    int* valid_transitions,
    int* invalid_transitions) {
    int remaining = 0;
    bool first_continuation = false;
    std::uint8_t first_min = 0x80;
    std::uint8_t first_max = 0xBF;
    int valid = 0;
    int invalid = 0;

    for (std::uint8_t byte : bytes) {
        if (remaining == 0) {
            if (byte <= 0x7F) {
                ++valid;
                continue;
            }
            if (byte >= 0xC2 && byte <= 0xDF) {
                remaining = 1;
                first_continuation = true;
                first_min = 0x80;
                first_max = 0xBF;
                ++valid;
                continue;
            }
            if (byte == 0xE0) {
                remaining = 2;
                first_continuation = true;
                first_min = 0xA0;
                first_max = 0xBF;
                ++valid;
                continue;
            }
            if ((byte >= 0xE1 && byte <= 0xEC) || (byte >= 0xEE && byte <= 0xEF)) {
                remaining = 2;
                first_continuation = true;
                first_min = 0x80;
                first_max = 0xBF;
                ++valid;
                continue;
            }
            if (byte == 0xED) {
                remaining = 2;
                first_continuation = true;
                first_min = 0x80;
                first_max = 0x9F;
                ++valid;
                continue;
            }
            if (byte == 0xF0) {
                remaining = 3;
                first_continuation = true;
                first_min = 0x90;
                first_max = 0xBF;
                ++valid;
                continue;
            }
            if (byte >= 0xF1 && byte <= 0xF3) {
                remaining = 3;
                first_continuation = true;
                first_min = 0x80;
                first_max = 0xBF;
                ++valid;
                continue;
            }
            if (byte == 0xF4) {
                remaining = 3;
                first_continuation = true;
                first_min = 0x80;
                first_max = 0x8F;
                ++valid;
                continue;
            }
            ++invalid;
            if (valid_transitions != nullptr) {
                *valid_transitions = valid;
            }
            if (invalid_transitions != nullptr) {
                *invalid_transitions = invalid;
            }
            return false;
        }

        if (first_continuation) {
            if (byte < first_min || byte > first_max) {
                ++invalid;
                if (valid_transitions != nullptr) {
                    *valid_transitions = valid;
                }
                if (invalid_transitions != nullptr) {
                    *invalid_transitions = invalid;
                }
                return false;
            }
            first_continuation = false;
            --remaining;
            ++valid;
            continue;
        }

        if (byte < 0x80 || byte > 0xBF) {
            ++invalid;
            if (valid_transitions != nullptr) {
                *valid_transitions = valid;
            }
            if (invalid_transitions != nullptr) {
                *invalid_transitions = invalid;
            }
            return false;
        }
        --remaining;
        ++valid;
    }

    if (remaining != 0) {
        ++invalid;
    }
    if (valid_transitions != nullptr) {
        *valid_transitions = valid;
    }
    if (invalid_transitions != nullptr) {
        *invalid_transitions = invalid;
    }
    return remaining == 0;
}

bool validate_utf16_surrogate_pairs(
    const std::vector<std::uint8_t>& bytes,
    bool little_endian,
    int* valid_transitions,
    int* invalid_transitions) {
    if (bytes.size() % 2 != 0) {
        if (valid_transitions != nullptr) {
            *valid_transitions = 0;
        }
        if (invalid_transitions != nullptr) {
            *invalid_transitions = 1;
        }
        return false;
    }

    bool expect_low = false;
    int valid = 0;
    int invalid = 0;
    for (std::size_t i = 0; i < bytes.size(); i += 2) {
        std::uint16_t unit = 0;
        if (little_endian) {
            unit = static_cast<std::uint16_t>(bytes[i] | (bytes[i + 1] << 8));
        } else {
            unit = static_cast<std::uint16_t>((bytes[i] << 8) | bytes[i + 1]);
        }

        if (unit >= 0xD800 && unit <= 0xDBFF) {
            if (expect_low) {
                ++invalid;
                if (valid_transitions != nullptr) {
                    *valid_transitions = valid;
                }
                if (invalid_transitions != nullptr) {
                    *invalid_transitions = invalid;
                }
                return false;
            }
            expect_low = true;
            ++valid;
            continue;
        }

        if (unit >= 0xDC00 && unit <= 0xDFFF) {
            if (!expect_low) {
                ++invalid;
                if (valid_transitions != nullptr) {
                    *valid_transitions = valid;
                }
                if (invalid_transitions != nullptr) {
                    *invalid_transitions = invalid;
                }
                return false;
            }
            expect_low = false;
            ++valid;
            continue;
        }

        if (expect_low) {
            ++invalid;
            if (valid_transitions != nullptr) {
                *valid_transitions = valid;
            }
            if (invalid_transitions != nullptr) {
                *invalid_transitions = invalid;
            }
            return false;
        }
        ++valid;
    }

    if (expect_low) {
        ++invalid;
    }
    if (valid_transitions != nullptr) {
        *valid_transitions = valid;
    }
    if (invalid_transitions != nullptr) {
        *invalid_transitions = invalid;
    }
    return !expect_low;
}

bool validate_shift_jis(const std::vector<std::uint8_t>& bytes, int* signal) {
    int local_signal = 0;
    int pair_count = 0;
    bool has_high = false;
    std::size_t i = 0;
    while (i < bytes.size()) {
        const std::uint8_t b = bytes[i];
        if (b <= 0x7F) {
            ++i;
            continue;
        }
        has_high = true;
        if (b >= 0xA1 && b <= 0xDF) {
            ++local_signal;
            ++i;
            continue;
        }
        if ((b >= 0x81 && b <= 0x9F) || (b >= 0xE0 && b <= 0xFC)) {
            if (i + 1 >= bytes.size()) {
                return false;
            }
            const std::uint8_t t = bytes[i + 1];
            const bool valid_trail = ((t >= 0x40 && t <= 0x7E) || (t >= 0x80 && t <= 0xFC)) && t != 0x7F;
            if (!valid_trail) {
                return false;
            }
            local_signal += 2;
            ++pair_count;
            i += 2;
            continue;
        }
        return false;
    }
    if (has_high && pair_count == 0) {
        return false;
    }
    if (signal != nullptr) {
        *signal = local_signal;
    }
    return true;
}

bool validate_euc_jp(const std::vector<std::uint8_t>& bytes, int* signal) {
    int local_signal = 0;
    std::size_t i = 0;
    while (i < bytes.size()) {
        const std::uint8_t b = bytes[i];
        if (b <= 0x7F) {
            ++i;
            continue;
        }
        if (b == 0x8E) {
            if (i + 1 >= bytes.size()) {
                return false;
            }
            const std::uint8_t t = bytes[i + 1];
            if (!(t >= 0xA1 && t <= 0xDF)) {
                return false;
            }
            local_signal += 2;
            i += 2;
            continue;
        }
        if (b == 0x8F) {
            if (i + 2 >= bytes.size()) {
                return false;
            }
            const std::uint8_t t1 = bytes[i + 1];
            const std::uint8_t t2 = bytes[i + 2];
            if (!(t1 >= 0xA1 && t1 <= 0xFE && t2 >= 0xA1 && t2 <= 0xFE)) {
                return false;
            }
            local_signal += 3;
            i += 3;
            continue;
        }
        if (b >= 0xA1 && b <= 0xFE) {
            if (i + 1 >= bytes.size()) {
                return false;
            }
            const std::uint8_t t = bytes[i + 1];
            if (!(t >= 0xA1 && t <= 0xFE)) {
                return false;
            }
            local_signal += 2;
            i += 2;
            continue;
        }
        return false;
    }
    if (signal != nullptr) {
        *signal = local_signal;
    }
    return true;
}

bool validate_big5(const std::vector<std::uint8_t>& bytes, int* signal) {
    int local_signal = 0;
    std::size_t i = 0;
    while (i < bytes.size()) {
        const std::uint8_t b = bytes[i];
        if (b <= 0x7F) {
            ++i;
            continue;
        }
        if (b >= 0x81 && b <= 0xFE) {
            if (i + 1 >= bytes.size()) {
                return false;
            }
            const std::uint8_t t = bytes[i + 1];
            if (!((t >= 0x40 && t <= 0x7E) || (t >= 0xA1 && t <= 0xFE))) {
                return false;
            }
            local_signal += 2;
            i += 2;
            continue;
        }
        return false;
    }
    if (signal != nullptr) {
        *signal = local_signal;
    }
    return true;
}

std::pair<std::string, double> probe_escape_sequence_encoding(const std::vector<std::uint8_t>& bytes) {
    constexpr std::uint8_t ESC = 0x1B;

    bool has_esc = false;
    for (std::uint8_t b : bytes) {
        if (b == ESC) {
            has_esc = true;
        }
        if (b >= 0x80) {
            return {"", 0.0};
        }
    }
    if (!has_esc) {
        return {"", 0.0};
    }

    int hits = 0;
    std::size_t i = 0;
    while (i < bytes.size()) {
        const std::uint8_t b = bytes[i];
        if (b != ESC) {
            ++i;
            continue;
        }

        if (i + 2 >= bytes.size()) {
            return {"", 0.0};
        }

        const std::uint8_t b1 = bytes[i + 1];
        const std::uint8_t b2 = bytes[i + 2];

        if (b1 == 0x28 && (b2 == 0x42 || b2 == 0x4A || b2 == 0x49)) {  // ESC ( B/J/I
            ++hits;
            i += 3;
            continue;
        }
        if (b1 == 0x24 && (b2 == 0x40 || b2 == 0x42)) {  // ESC $ @ / ESC $ B
            ++hits;
            i += 3;
            continue;
        }
        if (b1 == 0x24 && b2 == 0x28) {  // ESC $ ( D
            if (i + 3 >= bytes.size() || bytes[i + 3] != 0x44) {
                return {"", 0.0};
            }
            ++hits;
            i += 4;
            continue;
        }
        if (b1 == 0x26 && b2 == 0x40) {  // ESC & @
            ++hits;
            i += 3;
            continue;
        }

        return {"", 0.0};
    }

    if (hits == 0) {
        return {"", 0.0};
    }

    const double conf = std::max(0.8, std::min(0.99, calculate_transition_confidence(hits, 0)));
    return {"iso-2022-jp", conf};
}

std::pair<std::string, double> probe_multi_byte_encoding(const std::vector<std::uint8_t>& bytes) {
    struct Candidate {
        const char* encoding;
        bool (*validator)(const std::vector<std::uint8_t>&, int*);
    };
    static constexpr Candidate CANDIDATES[] = {
        {"shift_jis", validate_shift_jis},
        {"euc_jp", validate_euc_jp},
        {"big5", validate_big5},
    };

    std::string best_encoding;
    int best_signal = -1;
    int best_big5_low_trails = -1;
    double best_ratio = 0.0;

    for (const auto& c : CANDIDATES) {
        int signal = 0;
        if (!c.validator(bytes, &signal)) {
            continue;
        }
        int big5_low_trails = 0;
        if (std::string(c.encoding) == "big5") {
            for (std::size_t i = 0; i + 1 < bytes.size(); ++i) {
                const std::uint8_t b = bytes[i];
                const std::uint8_t t = bytes[i + 1];
                if (b >= 0x81 && b <= 0xFE && t >= 0x40 && t <= 0x7E) {
                    ++big5_low_trails;
                }
            }
        }
        const double ratio = static_cast<double>(signal) / std::max<std::size_t>(1, bytes.size());
        if (signal > best_signal ||
            (signal == best_signal && big5_low_trails > best_big5_low_trails) ||
            (signal == best_signal && big5_low_trails == best_big5_low_trails && ratio > best_ratio)) {
            best_signal = signal;
            best_big5_low_trails = big5_low_trails;
            best_ratio = ratio;
            best_encoding = c.encoding;
        }
    }

    if (best_encoding.empty() || best_signal <= 0) {
        return {"", 0.0};
    }

    const double conf = std::max(0.55, std::min(0.95, calculate_transition_confidence(best_signal, 0)));
    return {best_encoding, conf};
}

std::pair<std::string, double> probe_single_byte_encoding(const std::vector<std::uint8_t>& bytes) {
    static constexpr std::array<std::uint8_t, 18> PL_CP1250{
        0xA5, 0xB9, 0xC6, 0xE6, 0xCA, 0xEA, 0xA3, 0xB3, 0xD1,
        0xF1, 0xD3, 0xF3, 0x8C, 0x9C, 0x8F, 0x9F, 0xAF, 0xBF};
    static constexpr std::array<std::uint8_t, 18> PL_ISO88592{
        0xA1, 0xB1, 0xC6, 0xE6, 0xCA, 0xEA, 0xA3, 0xB3, 0xD1,
        0xF1, 0xD3, 0xF3, 0xA6, 0xB6, 0xAC, 0xBC, 0xAF, 0xBF};
    static constexpr std::array<std::pair<std::uint8_t, double>, 16> CP1250_WEIGHTS{{
        {0xA5, 2.00}, {0xB9, 2.00}, {0x8C, 1.70}, {0x9C, 1.70},
        {0x8F, 1.70}, {0x9F, 1.70}, {0xC6, 0.80}, {0xE6, 0.80},
        {0xCA, 0.80}, {0xEA, 0.80}, {0xA3, 0.70}, {0xB3, 0.70},
        {0xD1, 0.70}, {0xF1, 0.70}, {0xD3, 0.70}, {0xF3, 0.70},
    }};
    static constexpr std::array<std::pair<std::uint8_t, double>, 16> ISO88592_WEIGHTS{{
        {0xA1, 2.00}, {0xB1, 2.00}, {0xA6, 1.70}, {0xB6, 1.70},
        {0xAC, 1.70}, {0xBC, 1.70}, {0xC6, 0.80}, {0xE6, 0.80},
        {0xCA, 0.80}, {0xEA, 0.80}, {0xA3, 0.70}, {0xB3, 0.70},
        {0xD1, 0.70}, {0xF1, 0.70}, {0xD3, 0.70}, {0xF3, 0.70},
    }};

    const auto table = build_byte_frequency_table(bytes);
    const double len = std::max<std::size_t>(1, bytes.size());

    auto polish_weight = [&](bool cp1250) -> double {
        const auto& own = cp1250 ? CP1250_WEIGHTS : ISO88592_WEIGHTS;
        const auto& opp = cp1250 ? ISO88592_WEIGHTS : CP1250_WEIGHTS;
        double own_score = 0.0;
        double opp_score = 0.0;
        for (const auto& it : own) {
            own_score += (static_cast<double>(table[it.first]) / len) * it.second;
        }
        for (const auto& it : opp) {
            opp_score += (static_cast<double>(table[it.first]) / len) * it.second;
        }
        return own_score - opp_score * 0.75;
    };

    auto score_for = [&](bool cp1250) -> double {
        int printable = 0;
        int c1_controls = 0;
        int polish_hits = 0;
        int suspicious = 0;

        for (std::uint8_t b : bytes) {
            if ((b >= 0x20 && b != 0x7F) || b == '\n' || b == '\r' || b == '\t') {
                ++printable;
            }
            if (b >= 0x80 && b <= 0x9F) {
                if (cp1250) {
                    if (b != 0x8C && b != 0x8F && b != 0x9C && b != 0x9F) {
                        ++suspicious;
                    }
                } else {
                    ++c1_controls;
                }
            }

            if (cp1250) {
                if (contains_byte(PL_CP1250, b)) {
                    ++polish_hits;
                }
            } else {
                if (contains_byte(PL_ISO88592, b)) {
                    ++polish_hits;
                }
            }
        }

        const double printable_ratio = static_cast<double>(printable) / len;
        const double c1_ratio = static_cast<double>(c1_controls) / len;
        const double polish_ratio = static_cast<double>(polish_hits) / len;
        const double suspicious_ratio = static_cast<double>(suspicious) / len;

        double score = printable_ratio;
        score += std::min(0.35, polish_ratio * 4.0);
        score += std::max(-0.9, std::min(0.9, polish_weight(cp1250)));
        score += (distribution_match_score(bytes, cp1250) - 0.5) * 1.1;
        score -= c1_ratio * 2.5;
        score -= suspicious_ratio * 0.8;
        return score;
    };

    const double score_cp1250 = score_for(true);
    const double score_iso88592 = score_for(false);

    if (score_cp1250 >= score_iso88592) {
        const double conf = std::max(0.0, std::min(0.93, 0.45 + score_cp1250 * 0.32));
        return {"windows-1250", conf};
    }
    const double conf = std::max(0.0, std::min(0.93, 0.45 + score_iso88592 * 0.32));
    return {"iso-8859-2", conf};
}

DetectionResult detect_encoding_core(const std::vector<std::uint8_t>& bytes) {
    if (has_prefix(bytes, {0x00, 0x00, 0xFE, 0xFF})) {
        return DetectionResult{"utf-32-be", 1.0, false, true};
    }
    if (has_prefix(bytes, {0xFF, 0xFE, 0x00, 0x00})) {
        return DetectionResult{"utf-32-le", 1.0, false, true};
    }
    if (has_prefix(bytes, {0xEF, 0xBB, 0xBF})) {
        return DetectionResult{"utf-8-sig", 1.0, false, true};
    }
    if (has_prefix(bytes, {0xFE, 0xFF})) {
        std::vector<std::uint8_t> payload(bytes.begin() + 2, bytes.end());
        int valid = 0;
        int invalid = 0;
        if (validate_utf16_surrogate_pairs(payload, false, &valid, &invalid)) {
            const double conf = std::max(0.9, calculate_transition_confidence(valid, invalid));
            return DetectionResult{"utf-16-be", conf, false, true};
        }
        const double conf = std::min(0.49, calculate_transition_confidence(valid, invalid));
        return DetectionResult{"utf-16-be", conf, true, true};
    }
    if (has_prefix(bytes, {0xFF, 0xFE})) {
        std::vector<std::uint8_t> payload(bytes.begin() + 2, bytes.end());
        int valid = 0;
        int invalid = 0;
        if (validate_utf16_surrogate_pairs(payload, true, &valid, &invalid)) {
            const double conf = std::max(0.9, calculate_transition_confidence(valid, invalid));
            return DetectionResult{"utf-16-le", conf, false, true};
        }
        const double conf = std::min(0.49, calculate_transition_confidence(valid, invalid));
        return DetectionResult{"utf-16-le", conf, true, true};
    }

    if (bytes.empty()) {
        return DetectionResult{"utf-8", 1.0, false, false};
    }

    auto esc_guess = probe_escape_sequence_encoding(bytes);
    if (!esc_guess.first.empty()) {
        return DetectionResult{esc_guess.first, esc_guess.second, false, false};
    }

    int utf8_valid = 0;
    int utf8_invalid = 0;
    if (validate_utf8_dfa(bytes, &utf8_valid, &utf8_invalid)) {
        const double conf = std::max(0.7, std::min(0.97, calculate_transition_confidence(utf8_valid, utf8_invalid)));
        return DetectionResult{"utf-8", conf, false, false};
    }

    bool has_high_bytes = false;
    for (std::uint8_t b : bytes) {
        if (b >= 0x80) {
            has_high_bytes = true;
            break;
        }
    }
    if (has_high_bytes) {
        auto multi = probe_multi_byte_encoding(bytes);
        auto guess = probe_single_byte_encoding(bytes);
        std::vector<std::pair<std::string, double>> candidates;
        if (!multi.first.empty()) {
            candidates.push_back(multi);
        }
        if (!guess.first.empty()) {
            candidates.push_back(guess);
        }
        const auto selected = choose_by_language_fallback_map(candidates);
        if (!selected.first.empty()) {
            return DetectionResult{selected.first, selected.second, false, false};
        }
        return DetectionResult{"utf-8", 0.0, true, false};
    }

    // Placeholder fallback for non-text/binary.
    return DetectionResult{"utf-8", 0.0, true, false};
}

DetectionResult detect_encoding(const std::vector<std::uint8_t>& bytes) {
    if (bytes.size() > EARLY_EXIT_BYTES) {
        const std::vector<std::uint8_t> prefix(bytes.begin(), bytes.begin() + EARLY_EXIT_BYTES);
        const auto prefix_result = detect_encoding_core(prefix);
        if (prefix_result.confidence > EARLY_EXIT_CONFIDENCE) {
            return prefix_result;
        }
    }
    return detect_encoding_core(bytes);
}

}  // namespace lx::encoding
