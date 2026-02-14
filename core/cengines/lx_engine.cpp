#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <pybind11/pytypes.h>

#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

#include "engine/io_codec.hpp"
#include "engine/logger.hpp"
#include "engine/search.hpp"
#include "engine/stats.hpp"
#include "engine/text_utils.hpp"

namespace py = pybind11;

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
    if (value == "latin1") return "latin-1";
    return value;
}

py::dict get_statistics_dict(const std::string& text) {
    const lx::engine::TextStatistics stats = lx::engine::get_statistics_native(text);
    py::dict d;
    d["chars"] = stats.chars;
    d["words"] = stats.words;
    d["lines"] = stats.lines;
    d["bytes"] = stats.bytes;
    return d;
}

py::dict decode_bytes_binding(
    const py::bytes& raw,
    const std::string& preferred_encoding,
    py::list fallback_encodings,
    bool replace_errors) {
    const std::string raw_data = raw;

    std::vector<std::string> candidates;
    candidates.reserve(8 + static_cast<size_t>(py::len(fallback_encodings)));

    if (!preferred_encoding.empty()) {
        candidates.push_back(normalize_encoding(preferred_encoding));
    }

    if (raw_data.size() >= 3 &&
        static_cast<unsigned char>(raw_data[0]) == 0xEF &&
        static_cast<unsigned char>(raw_data[1]) == 0xBB &&
        static_cast<unsigned char>(raw_data[2]) == 0xBF) {
        candidates.push_back("utf-8-sig");
    } else if (raw_data.size() >= 2) {
        const unsigned char b0 = static_cast<unsigned char>(raw_data[0]);
        const unsigned char b1 = static_cast<unsigned char>(raw_data[1]);
        if (b0 == 0xFF && b1 == 0xFE) candidates.push_back("utf-16le");
        if (b0 == 0xFE && b1 == 0xFF) candidates.push_back("utf-16be");
    }

    candidates.push_back("utf-8");
    candidates.push_back("utf-8-sig");
    candidates.push_back("utf-16");

    for (py::handle item : fallback_encodings) {
        candidates.push_back(normalize_encoding(py::str(item).cast<std::string>()));
    }

    const std::string preferred_norm = normalize_encoding(preferred_encoding);

    std::vector<std::string> uniq;
    uniq.reserve(candidates.size());
    for (const auto& c : candidates) {
        if (c.empty()) continue;
        if (std::find(uniq.begin(), uniq.end(), c) == uniq.end()) {
            uniq.push_back(c);
        }
    }

    std::vector<std::string> native_candidates;
    native_candidates.reserve(uniq.size());
    for (const auto& enc : uniq) {
        if (enc == "utf-8" || enc == "utf-8-sig" || enc == "utf-16" || enc == "utf-16le" || enc == "utf-16be") {
            native_candidates.push_back(enc);
            continue;
        }
        if (enc == "latin-1" && preferred_norm == "latin-1") {
            native_candidates.push_back(enc);
        }
    }

    // Najpierw strict-native decode, żeby nie "zamaskować" lepszego kodowania replacementem.
    lx::engine::DecodeResult decoded = lx::engine::decode_bytes_native(raw_data, native_candidates, false);

    py::dict result;
    result["attempts"] = uniq;
    result["used_fallback"] = py::bool_(false);

    if (decoded.ok) {
        result["ok"] = py::bool_(true);
        result["text"] = py::str(decoded.text);
        result["encoding"] = py::str(decoded.encoding);
        return result;
    }

    py::module codecs = py::module::import("codecs");
    py::bytes raw_obj(raw_data);
    for (const auto& enc : uniq) {
        try {
            py::object text_obj = codecs.attr("decode")(raw_obj, enc, "strict");
            result["ok"] = py::bool_(true);
            result["text"] = py::str(text_obj);
            result["encoding"] = py::str(enc);
            result["used_fallback"] = py::bool_(true);
            return result;
        } catch (const py::error_already_set&) {
            continue;
        }
    }

    if (replace_errors) {
        py::object text_obj = codecs.attr("decode")(raw_obj, "utf-8", "replace");
        result["ok"] = py::bool_(false);
        result["text"] = py::str(text_obj);
        result["encoding"] = py::str("utf-8-replace");
        result["used_fallback"] = py::bool_(true);
        return result;
    }

    throw py::value_error("Unable to decode bytes with provided encodings");
}
}  // namespace

// --- EXPORT MODUŁU ---

PYBIND11_MODULE(lx_engine, m) {
    m.doc() = "LxNotes Evergreen Core Engine";
    
    m.def("set_logger", [](py::object func) {
        lx::engine::set_logger(func.cast<std::function<void(const std::string&, const std::string&)>>());
    });
    m.def("clear_logger", &lx::engine::clear_logger);

    m.def("prepare_large_text", &lx::engine::prepare_large_text, 
          py::arg("input"), 
          py::call_guard<py::gil_scoped_release>());
          
    m.def("find_all", &lx::engine::find_all, 
          py::arg("text"), py::arg("query"), py::arg("case_sensitive"), py::arg("whole_words"),
          py::call_guard<py::gil_scoped_release>());
          
    m.def("replace_all", &lx::engine::replace_all, 
          py::arg("text"), py::arg("query"), py::arg("replacement"), py::arg("case_sensitive"),
          py::call_guard<py::gil_scoped_release>());

    m.def("get_statistics", &get_statistics_dict, py::arg("text"));

    m.def("get_line_offset", &lx::engine::get_line_offset, 
          py::arg("text"), py::arg("line_number"),
          py::call_guard<py::gil_scoped_release>());

    m.def("get_line_offsets", &lx::engine::get_line_offsets,
          py::arg("text"),
          py::call_guard<py::gil_scoped_release>());

    m.def("decode_bytes", &decode_bytes_binding,
          py::arg("raw"),
          py::arg("preferred_encoding") = "",
          py::arg("fallback_encodings") = py::list(),
          py::arg("replace_errors") = true);
}
