#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize2.h"

#include <VTFFile.h>

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <future>
#include <sstream>
#include <string>
#include <vector>

static unsigned int floor_pot(unsigned int x) {
    if (x == 0) return 1;
    unsigned int p = 1;
    while (p * 2 <= x) p *= 2;
    return p;
}

static int process_one(const std::string& vtf_path, const std::string& png_path, int max_size) {
    VTFLib::CVTFFile vtf;
    if (!vtf.Load(vtf_path.c_str())) {
        std::fprintf(stderr, "Failed to load: %s\n", vtf_path.c_str());
        return 1;
    }

    vlUInt w   = vtf.GetWidth();
    vlUInt h   = vtf.GetHeight();
    VTFImageFormat fmt = vtf.GetFormat();

    vlByte* raw = vtf.GetData(0, 0, 0, 0);

    vlUInt rgba_size = w * h * 4;
    vlByte* rgba = static_cast<vlByte*>(std::malloc(rgba_size));
    if (!rgba) {
        std::fprintf(stderr, "Out of memory: %s\n", vtf_path.c_str());
        return 1;
    }

    if (!VTFLib::CVTFFile::ConvertToRGBA8888(raw, rgba, w, h, fmt)) {
        std::fprintf(stderr, "Conversion failed: %s\n", vtf_path.c_str());
        std::free(rgba);
        return 1;
    }

    unsigned int nw = floor_pot(w);
    unsigned int nh = floor_pot(h);
    if (max_size > 0) {
        while (nw > (unsigned int)max_size) nw /= 2;
        while (nh > (unsigned int)max_size) nh /= 2;
    }

    while (nw * nh * 2 > 4096) {
        if (nw >= nh) nw /= 2; else nh /= 2;
        if (nw < 1) nw = 1;
        if (nh < 1) nh = 1;
    }

    vlByte* pixels = rgba;
    vlByte* resized = nullptr;
    if (nw != w || nh != h) {
        resized = static_cast<vlByte*>(std::malloc(nw * nh * 4));
        if (!resized) {
            std::fprintf(stderr, "Out of memory (resize): %s\n", vtf_path.c_str());
            std::free(rgba);
            return 1;
        }
        stbir_resize_uint8_srgb(rgba, (int)w, (int)h, 0, resized, (int)nw, (int)nh, 0, STBIR_RGBA);
        pixels = resized;
    }

    int ok = stbi_write_png(png_path.c_str(), (int)nw, (int)nh, 4, pixels, (int)(nw * 4));
    std::free(rgba);
    if (resized) std::free(resized);

    if (!ok) {
        std::fprintf(stderr, "stbi_write_png failed: %s\n", png_path.c_str());
        return 1;
    }

    return 0;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::fprintf(stderr, "Usage: vtf2png <max_size> <in1.vtf> <out1.png> ...\n");
        std::fprintf(stderr, "       vtf2png @ <listfile>  (listfile: line 0 = max_size, then vtf/png pairs)\n");
        return 1;
    }

    int max_size = 0;
    std::vector<std::pair<std::string,std::string>> pairs;

    if (std::string(argv[1]) == "@") {
        if (argc != 3) {
            std::fprintf(stderr, "Usage: vtf2png @ <listfile>\n");
            return 1;
        }
        std::ifstream f(argv[2]);
        if (!f) {
            std::fprintf(stderr, "Cannot open list file: %s\n", argv[2]);
            return 1;
        }
        std::string line;
        if (std::getline(f, line)) max_size = std::atoi(line.c_str());
        std::string vtf, png;
        while (std::getline(f, vtf) && std::getline(f, png))
            pairs.emplace_back(std::move(vtf), std::move(png));
    } else {
        if (argc < 2 || (argc - 2) % 2 != 0) {
            std::fprintf(stderr, "Usage: vtf2png <max_size> <in1.vtf> <out1.png> ...\n");
            return 1;
        }
        max_size = std::atoi(argv[1]);
        for (int i = 2; i < argc; i += 2)
            pairs.emplace_back(argv[i], argv[i+1]);
    }

    std::vector<std::future<int>> futures;
    futures.reserve(pairs.size());
    for (auto& [vtf, png] : pairs)
        futures.push_back(std::async(std::launch::async, process_one, vtf, png, max_size));

    int ret = 0;
    for (auto& f : futures)
        ret |= f.get();
    return ret;
}
