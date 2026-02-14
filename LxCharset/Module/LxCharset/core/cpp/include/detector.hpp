#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace lx::encoding {

struct DetectionResult {
    std::string encoding;
    double confidence;
    bool used_fallback;
    bool detected_by_bom;
};

std::array<std::size_t, 256> build_byte_frequency_table(const std::vector<std::uint8_t>& bytes);
double byte_frequency_ratio(const std::vector<std::uint8_t>& bytes, std::uint8_t byte_value);
double distribution_match_score(const std::vector<std::uint8_t>& bytes, bool cp1250);
double calculate_transition_confidence(int valid_transitions, int invalid_transitions);
bool validate_utf8_dfa(
    const std::vector<std::uint8_t>& bytes,
    int* valid_transitions = nullptr,
    int* invalid_transitions = nullptr);
bool validate_utf16_surrogate_pairs(
    const std::vector<std::uint8_t>& bytes,
    bool little_endian,
    int* valid_transitions = nullptr,
    int* invalid_transitions = nullptr);
bool validate_shift_jis(const std::vector<std::uint8_t>& bytes, int* signal);
bool validate_euc_jp(const std::vector<std::uint8_t>& bytes, int* signal);
bool validate_big5(const std::vector<std::uint8_t>& bytes, int* signal);
std::pair<std::string, double> probe_escape_sequence_encoding(const std::vector<std::uint8_t>& bytes);
std::pair<std::string, double> probe_multi_byte_encoding(const std::vector<std::uint8_t>& bytes);
std::pair<std::string, double> probe_single_byte_encoding(const std::vector<std::uint8_t>& bytes);
DetectionResult detect_encoding(const std::vector<std::uint8_t>& bytes);

}  // namespace lx::encoding
