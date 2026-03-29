#include "tm_analysis/json_io.h"

#include <iomanip>
#include <sstream>

namespace tm::analysis {

namespace {

std::string escape_json(const std::string& value) {
    std::ostringstream output;
    for (const char ch : value) {
        switch (ch) {
            case '\\':
                output << "\\\\";
                break;
            case '"':
                output << "\\\"";
                break;
            case '\b':
                output << "\\b";
                break;
            case '\f':
                output << "\\f";
                break;
            case '\n':
                output << "\\n";
                break;
            case '\r':
                output << "\\r";
                break;
            case '\t':
                output << "\\t";
                break;
            default:
                output << ch;
                break;
        }
    }
    return output.str();
}

void write_optional_number(std::ostringstream& output, const char* key, const std::optional<double>& value) {
    output << '"' << key << "\": ";
    if (value.has_value()) {
        output << std::fixed << std::setprecision(6) << *value;
    } else {
        output << "null";
    }
}

void write_optional_string(std::ostringstream& output, const char* key, const std::optional<std::string>& value) {
    output << '"' << key << "\": ";
    if (value.has_value()) {
        output << '"' << escape_json(*value) << '"';
    } else {
        output << "null";
    }
}

}  // namespace

std::string to_json(const AnalysisResult& result) {
    std::ostringstream output;
    output << "{\n";
    output << "  \"backend\": \"" << escape_json(result.backend) << "\",\n";
    write_optional_number(output, "duration", result.duration_seconds);
    output << ",\n";
    write_optional_number(output, "bpm", result.bpm);
    output << ",\n";
    write_optional_string(output, "key", result.key);
    output << ",\n";
    write_optional_string(output, "scale", result.scale);
    output << ",\n";
    write_optional_number(output, "confidence", result.confidence);
    output << ",\n";
    output << "  \"candidates\": [";
    for (std::size_t index = 0; index < result.candidates.size(); ++index) {
        const Candidate& candidate = result.candidates[index];
        if (index > 0) {
            output << ", ";
        }
        output << "{\"key\": \"" << escape_json(candidate.key) << "\", \"score\": " << std::fixed
               << std::setprecision(6) << candidate.score << "}";
    }
    output << "],\n";
    write_optional_string(output, "error", result.error);
    output << "\n}\n";
    return output.str();
}

std::string contract_json() {
    AnalysisResult result;
    result.duration_seconds = 191.0;
    result.bpm = 110.02;
    result.key = "F# Major";
    result.scale = "major";
    result.confidence = 0.91;
    result.candidates = {
        Candidate{"F# Major", 0.91},
        Candidate{"D# Minor", 0.07},
        Candidate{"A# Minor", 0.02},
    };
    return to_json(result);
}

}  // namespace tm::analysis
