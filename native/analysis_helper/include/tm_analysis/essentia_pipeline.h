#pragma once

#include <string>

#include "tm_analysis/analysis_result.h"

namespace tunematrix::analysis {

AnalysisResult run_analysis(const std::string& input_path);

}  // namespace tunematrix::analysis
