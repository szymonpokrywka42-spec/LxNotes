#pragma once

#include <string>
#include <vector>

namespace lx::engine {

struct DecodeResult {
    bool ok = false;
    std::string text;
    std::string encoding;
    bool used_fallback = false;
    std::vector<std::string> attempts;
};

DecodeResult decode_bytes_native(
    const std::string& raw,
    const std::vector<std::string>& encodings,
    bool replace_errors = true);

}  // namespace lx::engine

