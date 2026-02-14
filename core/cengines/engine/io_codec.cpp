#include "io_codec.hpp"

#include <algorithm>
#include <cctype>
#include <cstdint>

namespace lx::engine {
namespace {

std::string normalize_encoding(std::string value) {
    std::transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char c) { return static_cast<char>(std::tolower(c)); });

    if (value == "utf8") return "utf-8";
    if (value == "utf_8") return "utf-8";
    if (value == "utf8-sig") return "utf-8-sig";
    if (value == "utf_8_sig") return "utf-8-sig";
    if (value == "utf16") return "utf-16";
    if (value == "utf_16") return "utf-16";
    if (value == "utf16le") return "utf-16le";
    if (value == "utf16be") return "utf-16be";
    if (value == "latin1") return "latin-1";
    if (value == "iso8859-1") return "latin-1";
    if (value == "cp819") return "latin-1";
    return value;
}

void append_utf8(std::string& out, uint32_t cp) {
    if (cp <= 0x7F) {
        out.push_back(static_cast<char>(cp));
    } else if (cp <= 0x7FF) {
        out.push_back(static_cast<char>(0xC0 | ((cp >> 6) & 0x1F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else if (cp <= 0xFFFF) {
        out.push_back(static_cast<char>(0xE0 | ((cp >> 12) & 0x0F)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else {
        out.push_back(static_cast<char>(0xF0 | ((cp >> 18) & 0x07)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    }
}

bool decode_utf8(const std::string& raw, std::string& out, bool replace_errors) {
    out.clear();
    out.reserve(raw.size());

    const auto* data = reinterpret_cast<const unsigned char*>(raw.data());
    const size_t len = raw.size();
    size_t i = 0;

    while (i < len) {
        const unsigned char c = data[i];
        if (c <= 0x7F) {
            out.push_back(static_cast<char>(c));
            ++i;
            continue;
        }

        int trailing = 0;
        uint32_t cp = 0;
        if ((c & 0xE0) == 0xC0) {
            trailing = 1;
            cp = c & 0x1F;
            if (cp == 0) {  // overlong
                if (!replace_errors) return false;
                append_utf8(out, 0xFFFD);
                ++i;
                continue;
            }
        } else if ((c & 0xF0) == 0xE0) {
            trailing = 2;
            cp = c & 0x0F;
        } else if ((c & 0xF8) == 0xF0) {
            trailing = 3;
            cp = c & 0x07;
        } else {
            if (!replace_errors) return false;
            append_utf8(out, 0xFFFD);
            ++i;
            continue;
        }

        if (i + trailing >= len) {
            if (!replace_errors) return false;
            append_utf8(out, 0xFFFD);
            break;
        }

        bool ok = true;
        for (int t = 1; t <= trailing; ++t) {
            const unsigned char cc = data[i + t];
            if ((cc & 0xC0) != 0x80) {
                ok = false;
                break;
            }
            cp = (cp << 6) | (cc & 0x3F);
        }

        if (!ok || cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF)) {
            if (!replace_errors) return false;
            append_utf8(out, 0xFFFD);
            ++i;
            continue;
        }

        append_utf8(out, cp);
        i += static_cast<size_t>(trailing + 1);
    }

    return true;
}

bool decode_utf16_impl(const std::string& raw, std::string& out, bool little_endian, bool replace_errors) {
    out.clear();
    out.reserve(raw.size());

    if (raw.size() % 2 != 0 && !replace_errors) {
        return false;
    }

    auto read16 = [&](size_t idx) -> uint16_t {
        const auto b0 = static_cast<unsigned char>(raw[idx]);
        const auto b1 = static_cast<unsigned char>(raw[idx + 1]);
        return little_endian ? static_cast<uint16_t>(b0 | (b1 << 8))
                             : static_cast<uint16_t>((b0 << 8) | b1);
    };

    size_t i = 0;
    while (i + 1 < raw.size()) {
        uint16_t w1 = read16(i);
        i += 2;

        if (w1 >= 0xD800 && w1 <= 0xDBFF) {
            if (i + 1 >= raw.size()) {
                if (!replace_errors) return false;
                append_utf8(out, 0xFFFD);
                break;
            }

            uint16_t w2 = read16(i);
            if (w2 < 0xDC00 || w2 > 0xDFFF) {
                if (!replace_errors) return false;
                append_utf8(out, 0xFFFD);
                continue;
            }
            i += 2;

            const uint32_t cp =
                0x10000 + ((static_cast<uint32_t>(w1 - 0xD800) << 10) | static_cast<uint32_t>(w2 - 0xDC00));
            append_utf8(out, cp);
            continue;
        }

        if (w1 >= 0xDC00 && w1 <= 0xDFFF) {
            if (!replace_errors) return false;
            append_utf8(out, 0xFFFD);
            continue;
        }

        append_utf8(out, static_cast<uint32_t>(w1));
    }

    if (i < raw.size() && replace_errors) {
        append_utf8(out, 0xFFFD);
    }

    return true;
}

bool decode_latin1(const std::string& raw, std::string& out) {
    out.clear();
    out.reserve(raw.size() * 2);
    for (unsigned char c : raw) {
        append_utf8(out, static_cast<uint32_t>(c));
    }
    return true;
}

bool try_decode_known(
    const std::string& raw,
    const std::string& encoding,
    bool replace_errors,
    std::string& out_text,
    std::string& out_used_encoding) {
    const std::string enc = normalize_encoding(encoding);

    if (enc == "utf-8") {
        const bool ok = decode_utf8(raw, out_text, replace_errors);
        if (ok) out_used_encoding = "utf-8";
        return ok;
    }

    if (enc == "utf-8-sig") {
        std::string trimmed = raw;
        if (trimmed.size() >= 3 &&
            static_cast<unsigned char>(trimmed[0]) == 0xEF &&
            static_cast<unsigned char>(trimmed[1]) == 0xBB &&
            static_cast<unsigned char>(trimmed[2]) == 0xBF) {
            trimmed = trimmed.substr(3);
        }
        const bool ok = decode_utf8(trimmed, out_text, replace_errors);
        if (ok) out_used_encoding = "utf-8-sig";
        return ok;
    }

    if (enc == "utf-16") {
        if (raw.size() >= 2) {
            const unsigned char b0 = static_cast<unsigned char>(raw[0]);
            const unsigned char b1 = static_cast<unsigned char>(raw[1]);
            if (b0 == 0xFF && b1 == 0xFE) {
                const bool ok = decode_utf16_impl(raw.substr(2), out_text, true, replace_errors);
                if (ok) out_used_encoding = "utf-16le";
                return ok;
            }
            if (b0 == 0xFE && b1 == 0xFF) {
                const bool ok = decode_utf16_impl(raw.substr(2), out_text, false, replace_errors);
                if (ok) out_used_encoding = "utf-16be";
                return ok;
            }
        }
        return false;
    }

    if (enc == "utf-16le") {
        std::string payload = raw;
        if (payload.size() >= 2 &&
            static_cast<unsigned char>(payload[0]) == 0xFF &&
            static_cast<unsigned char>(payload[1]) == 0xFE) {
            payload = payload.substr(2);
        }
        const bool ok = decode_utf16_impl(payload, out_text, true, replace_errors);
        if (ok) out_used_encoding = "utf-16le";
        return ok;
    }

    if (enc == "utf-16be") {
        std::string payload = raw;
        if (payload.size() >= 2 &&
            static_cast<unsigned char>(payload[0]) == 0xFE &&
            static_cast<unsigned char>(payload[1]) == 0xFF) {
            payload = payload.substr(2);
        }
        const bool ok = decode_utf16_impl(payload, out_text, false, replace_errors);
        if (ok) out_used_encoding = "utf-16be";
        return ok;
    }

    if (enc == "latin-1") {
        const bool ok = decode_latin1(raw, out_text);
        if (ok) out_used_encoding = "latin-1";
        return ok;
    }

    return false;
}

}  // namespace

DecodeResult decode_bytes_native(const std::string& raw, const std::vector<std::string>& encodings, bool replace_errors) {
    DecodeResult res;
    std::string decoded;
    std::string used_encoding;

    for (const auto& enc : encodings) {
        const std::string normalized = normalize_encoding(enc);
        if (normalized.empty()) {
            continue;
        }

        res.attempts.push_back(normalized);
        if (try_decode_known(raw, normalized, replace_errors, decoded, used_encoding)) {
            res.ok = true;
            res.text = std::move(decoded);
            res.encoding = std::move(used_encoding);
            return res;
        }
    }

    return res;
}

}  // namespace lx::engine
