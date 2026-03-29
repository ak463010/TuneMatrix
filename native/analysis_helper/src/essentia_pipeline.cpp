#include "tm_analysis/essentia_pipeline.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#if defined(TM_ANALYSIS_HELPER_ENABLE_ESSENTIA)
#include <essentia/algorithmfactory.h>
#include <essentia/essentia.h>
#endif

namespace tunematrix::analysis {

#if defined(TM_ANALYSIS_HELPER_ENABLE_ESSENTIA)
namespace {

using essentia::Real;
using essentia::standard::Algorithm;
using essentia::standard::AlgorithmFactory;

constexpr uint16_t kWaveFormatPcm = 0x0001;
constexpr uint16_t kWaveFormatIeeeFloat = 0x0003;
constexpr uint16_t kWaveFormatExtensible = 0xFFFE;
constexpr int kTargetSampleRate = 16000;
constexpr int kKeyFrameSize = 4096;
constexpr int kKeyHopSize = 4096;
constexpr int kMinimumAnalysisSamples = kKeyFrameSize;

struct WavFormat {
    uint16_t format_tag = 0;
    uint16_t channels = 0;
    uint32_t sample_rate = 0;
    uint16_t block_align = 0;
    uint16_t bits_per_sample = 0;
    uint16_t valid_bits_per_sample = 0;
    uint16_t subtype_tag = 0;
    bool is_float = false;
};

struct LoadedAudio {
    std::vector<Real> mono_audio;
    int sample_rate = 0;
    double duration_seconds = 0.0;
};

class EssentiaRuntimeGuard {
public:
    EssentiaRuntimeGuard() { essentia::init(); }
    ~EssentiaRuntimeGuard() { essentia::shutdown(); }
};

uint16_t read_u16(std::istream& input) {
    std::array<unsigned char, 2> bytes{};
    input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    if (!input) {
        throw std::runtime_error("Unexpected end of WAV file.");
    }
    return static_cast<uint16_t>(bytes[0] | (bytes[1] << 8));
}

uint32_t read_u32(std::istream& input) {
    std::array<unsigned char, 4> bytes{};
    input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    if (!input) {
        throw std::runtime_error("Unexpected end of WAV file.");
    }
    return static_cast<uint32_t>(bytes[0]) |
           (static_cast<uint32_t>(bytes[1]) << 8) |
           (static_cast<uint32_t>(bytes[2]) << 16) |
           (static_cast<uint32_t>(bytes[3]) << 24);
}

std::string read_fourcc(std::istream& input) {
    std::array<char, 4> bytes{};
    input.read(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    if (!input) {
        throw std::runtime_error("Unexpected end of WAV file.");
    }
    return std::string(bytes.data(), bytes.size());
}

void skip_chunk_padding(std::istream& input, uint32_t chunk_size) {
    if ((chunk_size & 1U) != 0U) {
        input.ignore(1);
    }
}

void skip_bytes(std::istream& input, std::streamoff count) {
    input.seekg(count, std::ios::cur);
    if (!input) {
        throw std::runtime_error("Failed to seek inside WAV file.");
    }
}

double clamp_sample(double value) {
    return std::clamp(value, -1.0, 1.0);
}

double read_pcm_sample(std::istream& input, uint16_t bits_per_sample) {
    switch (bits_per_sample) {
        case 8: {
            unsigned char sample = 0;
            input.read(reinterpret_cast<char*>(&sample), 1);
            if (!input) {
                throw std::runtime_error("Unexpected end of WAV sample data.");
            }
            return (static_cast<int>(sample) - 128) / 128.0;
        }
        case 16: {
            int16_t sample = 0;
            input.read(reinterpret_cast<char*>(&sample), sizeof(sample));
            if (!input) {
                throw std::runtime_error("Unexpected end of WAV sample data.");
            }
            return static_cast<double>(sample) / 32768.0;
        }
        case 24: {
            std::array<unsigned char, 3> bytes{};
            input.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
            if (!input) {
                throw std::runtime_error("Unexpected end of WAV sample data.");
            }
            int32_t sample = static_cast<int32_t>(bytes[0]) |
                             (static_cast<int32_t>(bytes[1]) << 8) |
                             (static_cast<int32_t>(bytes[2]) << 16);
            if ((sample & 0x00800000) != 0) {
                sample |= ~0x00FFFFFF;
            }
            return static_cast<double>(sample) / 8388608.0;
        }
        case 32: {
            int32_t sample = 0;
            input.read(reinterpret_cast<char*>(&sample), sizeof(sample));
            if (!input) {
                throw std::runtime_error("Unexpected end of WAV sample data.");
            }
            return static_cast<double>(sample) / 2147483648.0;
        }
        default:
            throw std::runtime_error("Unsupported PCM bit depth in WAV file.");
    }
}

double read_float_sample(std::istream& input, uint16_t bits_per_sample) {
    switch (bits_per_sample) {
        case 32: {
            float sample = 0.0f;
            input.read(reinterpret_cast<char*>(&sample), sizeof(sample));
            if (!input) {
                throw std::runtime_error("Unexpected end of WAV sample data.");
            }
            return static_cast<double>(sample);
        }
        case 64: {
            double sample = 0.0;
            input.read(reinterpret_cast<char*>(&sample), sizeof(sample));
            if (!input) {
                throw std::runtime_error("Unexpected end of WAV sample data.");
            }
            return sample;
        }
        default:
            throw std::runtime_error("Unsupported float bit depth in WAV file.");
    }
}

double read_wave_sample(std::istream& input, const WavFormat& format) {
    if (format.is_float) {
        return clamp_sample(read_float_sample(input, format.bits_per_sample));
    }
    return clamp_sample(read_pcm_sample(input, format.bits_per_sample));
}

std::string lowercase_extension(const std::filesystem::path& path) {
    std::string extension = path.extension().string();
    std::transform(
        extension.begin(),
        extension.end(),
        extension.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); }
    );
    return extension;
}

WavFormat parse_fmt_chunk(std::istream& input, uint32_t chunk_size) {
    if (chunk_size < 16) {
        throw std::runtime_error("Invalid WAV fmt chunk.");
    }

    WavFormat format;
    format.format_tag = read_u16(input);
    format.channels = read_u16(input);
    format.sample_rate = read_u32(input);
    (void)read_u32(input);  // byteRate
    format.block_align = read_u16(input);
    format.bits_per_sample = read_u16(input);
    format.valid_bits_per_sample = format.bits_per_sample;
    format.subtype_tag = format.format_tag;

    uint32_t remaining = chunk_size - 16;
    if (format.format_tag == kWaveFormatExtensible) {
        if (remaining < 24) {
            throw std::runtime_error("Invalid WAV extensible fmt chunk.");
        }
        const uint16_t extension_size = read_u16(input);
        if (extension_size < 22) {
            throw std::runtime_error("Unsupported WAV extensible fmt chunk.");
        }
        format.valid_bits_per_sample = read_u16(input);
        (void)read_u32(input);  // channelMask
        format.subtype_tag = read_u16(input);
        skip_bytes(input, 14);
        remaining -= 24;
    }

    if (remaining > 0) {
        skip_bytes(input, static_cast<std::streamoff>(remaining));
    }

    const uint16_t effective_tag = (format.format_tag == kWaveFormatExtensible) ? format.subtype_tag : format.format_tag;
    format.is_float = (effective_tag == kWaveFormatIeeeFloat);
    if (effective_tag != kWaveFormatPcm && effective_tag != kWaveFormatIeeeFloat) {
        throw std::runtime_error("Unsupported WAV encoding. Only PCM and IEEE float are supported.");
    }

    if (format.channels == 0 || format.sample_rate == 0 || format.block_align == 0) {
        throw std::runtime_error("Invalid WAV format parameters.");
    }

    return format;
}

LoadedAudio load_wav_file(const std::string& input_path) {
    const std::filesystem::path path(input_path);
    if (lowercase_extension(path) != ".wav") {
        throw std::runtime_error("Native Essentia analysis currently supports WAV files only.");
    }

    std::ifstream input(input_path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("Failed to open input audio file.");
    }

    if (read_fourcc(input) != "RIFF") {
        throw std::runtime_error("Input file is not a RIFF WAV file.");
    }
    (void)read_u32(input);  // file size
    if (read_fourcc(input) != "WAVE") {
        throw std::runtime_error("Input file is not a WAVE file.");
    }

    std::optional<WavFormat> format;
    std::optional<uint32_t> data_size;
    std::streampos data_position = std::streampos(-1);

    while (input && (!format.has_value() || !data_size.has_value())) {
        if (input.peek() == std::char_traits<char>::eof()) {
            break;
        }

        const std::string chunk_id = read_fourcc(input);
        const uint32_t chunk_size = read_u32(input);

        if (chunk_id == "fmt ") {
            format = parse_fmt_chunk(input, chunk_size);
            skip_chunk_padding(input, chunk_size);
            continue;
        }

        if (chunk_id == "data") {
            data_position = input.tellg();
            data_size = chunk_size;
            skip_bytes(input, static_cast<std::streamoff>(chunk_size));
            skip_chunk_padding(input, chunk_size);
            continue;
        }

        skip_bytes(input, static_cast<std::streamoff>(chunk_size));
        skip_chunk_padding(input, chunk_size);
    }

    if (!format.has_value() || !data_size.has_value() || data_position == std::streampos(-1)) {
        throw std::runtime_error("WAV file is missing fmt or data chunks.");
    }

    const WavFormat& wav = *format;
    const uint64_t frame_count = static_cast<uint64_t>(*data_size) / static_cast<uint64_t>(wav.block_align);
    if (frame_count == 0) {
        throw std::runtime_error("WAV file contains no audio frames.");
    }

    input.clear();
    input.seekg(data_position);
    if (!input) {
        throw std::runtime_error("Failed to seek to WAV audio data.");
    }

    LoadedAudio loaded;
    loaded.sample_rate = static_cast<int>(wav.sample_rate);
    loaded.duration_seconds = static_cast<double>(frame_count) / static_cast<double>(wav.sample_rate);
    loaded.mono_audio.reserve(static_cast<std::size_t>(frame_count));

    for (uint64_t frame = 0; frame < frame_count; ++frame) {
        double mixed = 0.0;
        for (uint16_t channel = 0; channel < wav.channels; ++channel) {
            mixed += read_wave_sample(input, wav);
        }
        mixed /= static_cast<double>(wav.channels);
        loaded.mono_audio.push_back(static_cast<Real>(mixed));
    }

    return loaded;
}

std::vector<Real> resample_linear(const std::vector<Real>& input, int source_rate, int target_rate) {
    if (input.empty() || source_rate <= 0 || target_rate <= 0 || source_rate == target_rate) {
        return input;
    }

    const double duration_seconds = static_cast<double>(input.size()) / static_cast<double>(source_rate);
    std::size_t output_size = static_cast<std::size_t>(std::llround(duration_seconds * static_cast<double>(target_rate)));
    output_size = std::max<std::size_t>(1, output_size);

    std::vector<Real> output;
    output.reserve(output_size);

    for (std::size_t index = 0; index < output_size; ++index) {
        const double source_position = (static_cast<double>(index) * static_cast<double>(source_rate)) /
                                       static_cast<double>(target_rate);
        const std::size_t left_index =
            std::min<std::size_t>(static_cast<std::size_t>(source_position), input.size() - 1);
        const std::size_t right_index = std::min<std::size_t>(left_index + 1, input.size() - 1);
        const double fraction = source_position - static_cast<double>(left_index);
        const double value =
            static_cast<double>(input[left_index]) +
            (static_cast<double>(input[right_index]) - static_cast<double>(input[left_index])) * fraction;
        output.push_back(static_cast<Real>(value));
    }

    return output;
}

void ensure_minimum_samples(std::vector<Real>& audio) {
    if (audio.size() < static_cast<std::size_t>(kMinimumAnalysisSamples)) {
        audio.resize(static_cast<std::size_t>(kMinimumAnalysisSamples), 0.0f);
    }
}

std::string title_case_scale(const std::string& scale) {
    if (scale.empty()) {
        return scale;
    }

    std::string result = scale;
    result[0] = static_cast<char>(std::toupper(static_cast<unsigned char>(result[0])));
    for (std::size_t index = 1; index < result.size(); ++index) {
        result[index] = static_cast<char>(std::tolower(static_cast<unsigned char>(result[index])));
    }
    return result;
}

std::string combine_key_and_scale(const std::string& key, const std::string& scale) {
    if (key.empty()) {
        return {};
    }
    if (scale.empty()) {
        return key;
    }
    return key + " " + title_case_scale(scale);
}

}  // namespace
#endif

AnalysisResult run_analysis(const std::string& input_path) {
    AnalysisResult result;
#if defined(TM_ANALYSIS_HELPER_ENABLE_ESSENTIA)
    try {
        const LoadedAudio loaded = load_wav_file(input_path);
        std::vector<Real> analysis_audio = resample_linear(loaded.mono_audio, loaded.sample_rate, kTargetSampleRate);
        ensure_minimum_samples(analysis_audio);

        EssentiaRuntimeGuard runtime_guard;
        AlgorithmFactory& factory = AlgorithmFactory::instance();

        std::unique_ptr<Algorithm> bpm_estimator(
            factory.create(
                "PercivalBpmEstimator",
                "sampleRate", kTargetSampleRate
            )
        );

        Real bpm = 0.0f;
        bpm_estimator->input("signal").set(analysis_audio);
        bpm_estimator->output("bpm").set(bpm);
        bpm_estimator->compute();

        std::unique_ptr<Algorithm> key_extractor(
            factory.create(
                "KeyExtractor",
                "sampleRate", static_cast<Real>(kTargetSampleRate),
                "frameSize", kKeyFrameSize,
                "hopSize", kKeyHopSize,
                "hpcpSize", 12,
                "maxFrequency", static_cast<Real>(3500.0),
                "minFrequency", static_cast<Real>(25.0),
                "maximumSpectralPeaks", 60,
                "pcpThreshold", static_cast<Real>(0.2),
                "profileType", "bgate",
                "spectralPeaksThreshold", static_cast<Real>(0.0001),
                "tuningFrequency", static_cast<Real>(440.0),
                "weightType", "cosine",
                "windowType", "hann"
            )
        );

        std::string key;
        std::string scale;
        Real strength = 0.0f;
        key_extractor->input("audio").set(analysis_audio);
        key_extractor->output("key").set(key);
        key_extractor->output("scale").set(scale);
        key_extractor->output("strength").set(strength);
        key_extractor->compute();

        const std::string combined_key = combine_key_and_scale(key, scale);
        if (combined_key.empty()) {
            result.error = "Essentia did not return a key.";
            return result;
        }

        result.duration_seconds = loaded.duration_seconds;
        result.bpm = (bpm > 0.0f) ? std::optional<double>(static_cast<double>(bpm)) : std::nullopt;
        result.key = combined_key;
        result.scale = scale.empty() ? std::nullopt : std::optional<std::string>(scale);
        result.confidence = static_cast<double>(strength);
        result.candidates.push_back(Candidate{combined_key, static_cast<double>(strength)});
        return result;
    } catch (const std::exception& exc) {
        result.error = exc.what();
    } catch (...) {
        result.error = "Essentia analysis failed with an unknown error.";
    }
#else
    (void)input_path;
    result.error = "Essentia support is not compiled into this helper yet.";
#endif
    return result;
}

}  // namespace tunematrix::analysis
