#pragma once

#include <string>

#include "tm_analysis/analysis_result.h"

namespace tunematrix::analysis {

std::string to_json(const AnalysisResult& result);
std::string contract_json();

}  // namespace tunematrix::analysis
