#pragma once

#include <functional>
#include <string>

namespace lx::engine {

using LoggerCallback = std::function<void(const std::string&, const std::string&)>;

void set_logger(LoggerCallback logger);
void clear_logger();
void log_to_py(const std::string& msg, const std::string& level = "ENGINE");

}  // namespace lx::engine
