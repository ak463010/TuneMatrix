#include "tm_analysis/essentia_pipeline.h"

namespace tm::analysis {

AnalysisResult run_analysis(const std::string& input_path) {
    AnalysisResult result;
    (void)input_path;
#if defined(TM_ANALYSIS_HELPER_ENABLE_ESSENTIA)
    result.error = "Essentia integration is not implemented in this scaffold yet.";
#else
    result.error = "Essentia support is not compiled into this helper yet.";
#endif
    return result;
}

}  // namespace tm::analysis
