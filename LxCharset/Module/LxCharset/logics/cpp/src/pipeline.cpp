#include "pipeline.hpp"

namespace lx::charset::logic {

PipelineResult detect_with_pipeline(const std::vector<std::uint8_t>& /*bytes*/) {
    // Placeholder for multi-stage heuristics and score aggregation.
    return PipelineResult{"utf-8", 0.0, true};
}

}  // namespace lx::charset::logic
