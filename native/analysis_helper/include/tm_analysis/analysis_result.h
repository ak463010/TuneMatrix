#pragma once

#include <optional>
#include <string>
#include <vector>

namespace tunematrix::analysis {

struct Candidate {
    std::string key;
    double score = 0.0;
};

struct AnalysisResult {
    std::string backend = "essentia-cpp";
    std::optional<double> duration_seconds;
    std::optional<double> bpm;
    std::optional<std::string> key;
    std::optional<std::string> scale;
    std::optional<double> confidence;
    std::vector<Candidate> candidates;
    std::optional<std::string> error;
};

}  // namespace tunematrix::analysis
