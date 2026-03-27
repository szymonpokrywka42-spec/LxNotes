#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <pybind11/pytypes.h>

#include <algorithm>
#include <atomic>
#include <cctype>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "engine/io_codec.hpp"
#include "engine/logger.hpp"
#include "engine/search.hpp"
#include "engine/stats.hpp"
#include "engine/text_utils.hpp"

namespace py = pybind11;

namespace {
struct TextBuffer {
    std::string text;
    std::vector<int> line_offsets;
};

std::mutex g_text_buffers_mutex;
std::unordered_map<int, TextBuffer> g_text_buffers;
std::atomic<int> g_next_text_buffer_id{1};

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

int create_text_buffer_binding(const std::string& text) {
    TextBuffer buffer;
    buffer.text = text;
    buffer.line_offsets = lx::engine::get_line_offsets(buffer.text);

    const int handle = g_next_text_buffer_id.fetch_add(1);
    std::lock_guard<std::mutex> lock(g_text_buffers_mutex);
    g_text_buffers.emplace(handle, std::move(buffer));
    return handle;
}

void release_text_buffer_binding(int handle) {
    std::lock_guard<std::mutex> lock(g_text_buffers_mutex);
    g_text_buffers.erase(handle);
}

py::dict get_text_buffer_info_binding(int handle, int lines_per_chunk) {
    if (lines_per_chunk <= 0) {
        lines_per_chunk = 4000;
    }

    std::lock_guard<std::mutex> lock(g_text_buffers_mutex);
    auto it = g_text_buffers.find(handle);
    if (it == g_text_buffers.end()) {
        throw py::value_error("Invalid text buffer handle");
    }

    const auto& buffer = it->second;
    const int line_count = static_cast<int>(buffer.line_offsets.size());
    const int chunk_count = std::max(1, (line_count + lines_per_chunk - 1) / lines_per_chunk);

    py::dict info;
    info["chars"] = static_cast<py::int_>(buffer.text.size());
    info["line_count"] = line_count;
    info["chunk_count"] = chunk_count;
    info["lines_per_chunk"] = lines_per_chunk;
    return info;
}

py::dict get_text_buffer_chunk_binding(int handle, int chunk_index, int lines_per_chunk) {
    if (lines_per_chunk <= 0) {
        lines_per_chunk = 4000;
    }

    std::lock_guard<std::mutex> lock(g_text_buffers_mutex);
    auto it = g_text_buffers.find(handle);
    if (it == g_text_buffers.end()) {
        throw py::value_error("Invalid text buffer handle");
    }

    const auto& buffer = it->second;
    const int line_count = static_cast<int>(buffer.line_offsets.size());
    const int chunk_count = std::max(1, (line_count + lines_per_chunk - 1) / lines_per_chunk);
    if (chunk_index < 0 || chunk_index >= chunk_count) {
        throw py::value_error("Chunk index out of range");
    }

    const int start_line = chunk_index * lines_per_chunk + 1;
    const int end_line = std::min(line_count, start_line + lines_per_chunk - 1);

    const int start_offset = buffer.line_offsets[start_line - 1];
    const int end_offset = (end_line < line_count) ? buffer.line_offsets[end_line] : static_cast<int>(buffer.text.size());
    const int chunk_len = std::max(0, end_offset - start_offset);

    py::dict d;
    d["text"] = py::str(buffer.text.substr(static_cast<size_t>(start_offset), static_cast<size_t>(chunk_len)));
    d["chunk_index"] = chunk_index;
    d["chunk_count"] = chunk_count;
    d["start_line"] = start_line;
    d["end_line"] = end_line;
    return d;
}

int get_text_buffer_line_count_binding(int handle) {
    std::lock_guard<std::mutex> lock(g_text_buffers_mutex);
    auto it = g_text_buffers.find(handle);
    if (it == g_text_buffers.end()) {
        throw py::value_error("Invalid text buffer handle");
    }
    return static_cast<int>(it->second.line_offsets.size());
}

int get_text_buffer_line_offset_binding(int handle, int line_number) {
    std::lock_guard<std::mutex> lock(g_text_buffers_mutex);
    auto it = g_text_buffers.find(handle);
    if (it == g_text_buffers.end()) {
        throw py::value_error("Invalid text buffer handle");
    }

    if (line_number <= 0) {
        return -1;
    }
    const auto& offsets = it->second.line_offsets;
    const int line_count = static_cast<int>(offsets.size());
    if (line_number > line_count) {
        return -1;
    }
    return offsets[static_cast<size_t>(line_number - 1)];
}

py::dict get_text_buffer_chunk_for_line_binding(int handle, int line_number, int lines_per_chunk) {
    if (lines_per_chunk <= 0) {
        lines_per_chunk = 4000;
    }

    std::lock_guard<std::mutex> lock(g_text_buffers_mutex);
    auto it = g_text_buffers.find(handle);
    if (it == g_text_buffers.end()) {
        throw py::value_error("Invalid text buffer handle");
    }

    if (line_number <= 0) {
        throw py::value_error("line_number must be >= 1");
    }

    const auto& offsets = it->second.line_offsets;
    const int line_count = static_cast<int>(offsets.size());
    if (line_number > line_count) {
        throw py::value_error("line_number out of range");
    }

    const int chunk_index = (line_number - 1) / lines_per_chunk;
    const int start_line = chunk_index * lines_per_chunk + 1;
    const int end_line = std::min(line_count, start_line + lines_per_chunk - 1);

    py::dict d;
    d["chunk_index"] = chunk_index;
    d["start_line"] = start_line;
    d["end_line"] = end_line;
    d["line_count"] = line_count;
    return d;
}

std::string get_text_buffer_full_binding(int handle) {
    std::lock_guard<std::mutex> lock(g_text_buffers_mutex);
    auto it = g_text_buffers.find(handle);
    if (it == g_text_buffers.end()) {
        throw py::value_error("Invalid text buffer handle");
    }
    return it->second.text;
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

    m.def("find_next_position", &lx::engine::find_next_position,
          py::arg("text"),
          py::arg("query"),
          py::arg("case_sensitive"),
          py::arg("whole_words"),
          py::arg("start_pos"),
          py::arg("wrap") = false,
          py::call_guard<py::gil_scoped_release>());
          
    m.def("replace_all",
          static_cast<std::string (*)(const std::string&, const std::string&, const std::string&, bool)>(
              &lx::engine::replace_all),
          py::arg("text"),
          py::arg("query"),
          py::arg("replacement"),
          py::arg("case_sensitive"),
          py::call_guard<py::gil_scoped_release>());

    m.def("replace_all_with_options",
          static_cast<std::string (*)(const std::string&, const std::string&, const std::string&, bool, bool)>(
              &lx::engine::replace_all),
          py::arg("text"),
          py::arg("query"),
          py::arg("replacement"),
          py::arg("case_sensitive"),
          py::arg("whole_words") = false,
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

    m.def("create_text_buffer", &create_text_buffer_binding,
          py::arg("text"));
    m.def("release_text_buffer", &release_text_buffer_binding,
          py::arg("handle"));
    m.def("get_text_buffer_info", &get_text_buffer_info_binding,
          py::arg("handle"),
          py::arg("lines_per_chunk") = 4000);
    m.def("get_text_buffer_chunk", &get_text_buffer_chunk_binding,
          py::arg("handle"),
          py::arg("chunk_index"),
          py::arg("lines_per_chunk") = 4000);
    m.def("get_text_buffer_line_count", &get_text_buffer_line_count_binding,
          py::arg("handle"));
    m.def("get_text_buffer_line_offset", &get_text_buffer_line_offset_binding,
          py::arg("handle"),
          py::arg("line_number"));
    m.def("get_text_buffer_chunk_for_line", &get_text_buffer_chunk_for_line_binding,
          py::arg("handle"),
          py::arg("line_number"),
          py::arg("lines_per_chunk") = 4000);
    m.def("get_text_buffer_full", &get_text_buffer_full_binding,
          py::arg("handle"));
}
