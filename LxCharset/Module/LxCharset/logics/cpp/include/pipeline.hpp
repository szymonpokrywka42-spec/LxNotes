#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace lx::charset::logic {

struct PipelineResult {
    std::string encoding;
    double confidence;
    bool used_fallback;
};

PipelineResult detect_with_pipeline(const std::vector<std::uint8_t>& bytes);

}  // namespace lx::charset::logic
