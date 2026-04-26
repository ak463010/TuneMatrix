#include <filesystem>
#include <iostream>
#include <string>

#include "tm_analysis/essentia_pipeline.h"
#include "tm_analysis/json_io.h"

namespace {

constexpr int kSuccessExitCode = 0;
constexpr int kBadInputExitCode = 2;
constexpr int kAnalysisFailureExitCode = 3;
constexpr int kDependencyFailureExitCode = 4;

void print_usage() {
    std::cerr
        << "Usage:\n"
        << "  tm-analysis-helper analyze --input <audio-file> --output-json\n"
        << "  tm-analysis-helper --print-contract\n";
}

}  // namespace

int main(int argc, char* argv[]) {
    if (argc <= 1) {
        print_usage();
        return kBadInputExitCode;
    }

    const std::string first_arg = argv[1];
    if (first_arg == "--print-contract") {
        std::cout << tunematrix::analysis::contract_json();
        return kSuccessExitCode;
    }

    if (first_arg != "analyze") {
        print_usage();
        return kBadInputExitCode;
    }

    std::string input_path;
    bool output_json = false;
    for (int index = 2; index < argc; ++index) {
        const std::string arg = argv[index];
        if (arg == "--input" && index + 1 < argc) {
            input_path = argv[++index];
        } else if (arg == "--output-json") {
            output_json = true;
        } else {
            print_usage();
            return kBadInputExitCode;
        }
    }

    if (input_path.empty() || !output_json) {
        print_usage();
        return kBadInputExitCode;
    }

    if (!std::filesystem::exists(input_path)) {
        tunematrix::analysis::AnalysisResult result;
        result.error = "Input file does not exist.";
        std::cout << tunematrix::analysis::to_json(result);
        return kBadInputExitCode;
    }

    const tunematrix::analysis::AnalysisResult result = tunematrix::analysis::run_analysis(input_path);
    std::cout << tunematrix::analysis::to_json(result);
    if (result.error.has_value()) {
        return kDependencyFailureExitCode;
    }
    return kSuccessExitCode;
}
