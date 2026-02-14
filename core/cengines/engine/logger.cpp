#include "logger.hpp"

#include <utility>

namespace lx::engine {

namespace {
LoggerCallback g_py_logger;
}  // namespace

void set_logger(LoggerCallback logger) { g_py_logger = std::move(logger); }

void clear_logger() { g_py_logger = nullptr; }

void log_to_py(const std::string& msg, const std::string& level) {
    if (g_py_logger) {
        g_py_logger(msg, level);
    }
}

}  // namespace lx::engine
