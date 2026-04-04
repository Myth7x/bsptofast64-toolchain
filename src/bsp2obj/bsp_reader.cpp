#include "bsp_reader.h"

#include <cstring>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

static constexpr int32_t VBSP_IDENT = ('P' << 24) | ('S' << 16) | ('B' << 8) | 'V';

static std::vector<uint8_t> read_file_bytes(const std::string& path) {
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f) throw std::runtime_error("Cannot open BSP: " + path);
    auto sz = f.tellg();
    f.seekg(0);
    std::vector<uint8_t> buf(static_cast<size_t>(sz));
    f.read(reinterpret_cast<char*>(buf.data()), sz);
    return buf;
}

template<typename T>
static std::vector<T> lump_as(const std::vector<uint8_t>& data, const BSPLump& lump) {
    if (lump.fileofs < 0 || lump.filelen <= 0) return {};
    size_t ofs = static_cast<size_t>(lump.fileofs);
    size_t len = static_cast<size_t>(lump.filelen);
    if (ofs >= data.size()) return {};
    len = std::min(len, data.size() - ofs);
    size_t count = len / sizeof(T);
    std::vector<T> out(count);
    if (count > 0)
        std::memcpy(out.data(), data.data() + ofs, count * sizeof(T));
    return out;
}

BSPData load_bsp(const std::string& path) {
    auto data = read_file_bytes(path);
    if (data.size() < sizeof(BSPHeader))
        throw std::runtime_error("File too small to be a BSP");

    BSPHeader hdr;
    std::memcpy(&hdr, data.data(), sizeof(hdr));

    if (hdr.ident != VBSP_IDENT)
        throw std::runtime_error("Not a VBSP file (bad magic)");
    if (hdr.version < 19 || hdr.version > 21)
        throw std::runtime_error("Unsupported BSP version: " + std::to_string(hdr.version));

    BSPData bsp;

    bsp.planes    = lump_as<BSPPlane>   (data, hdr.lumps[LUMP_PLANES]);
    bsp.vertices  = lump_as<BSPVertex>  (data, hdr.lumps[LUMP_VERTICES]);
    bsp.edges     = lump_as<BSPEdge>    (data, hdr.lumps[LUMP_EDGES]);
    bsp.surfedges = lump_as<int32_t>    (data, hdr.lumps[LUMP_SURFEDGES]);
    bsp.faces     = lump_as<BSPFace>    (data, hdr.lumps[LUMP_FACES]);
    bsp.texinfos  = lump_as<BSPTexInfo> (data, hdr.lumps[LUMP_TEXINFO]);
    bsp.texdatas  = lump_as<BSPTexData> (data, hdr.lumps[LUMP_TEXDATA]);
    bsp.brushes   = lump_as<BSPBrush>   (data, hdr.lumps[LUMP_BRUSHES]);
    bsp.brushsides = lump_as<BSPBrushSide>(data, hdr.lumps[LUMP_BRUSHSIDES]);
    bsp.dispinfos  = lump_as<BSPDispInfo> (data, hdr.lumps[LUMP_DISPINFO]);
    bsp.dispverts  = lump_as<BSPDispVert> (data, hdr.lumps[LUMP_DISP_VERTS]);

    {
        const auto& el = hdr.lumps[LUMP_ENTITIES];
        if (el.fileofs >= 0 && el.filelen > 0) {
            size_t ofs = static_cast<size_t>(el.fileofs);
            size_t len = static_cast<size_t>(el.filelen);
            if (ofs < data.size()) {
                len = std::min(len, data.size() - ofs);
                bsp.entities.assign(
                    reinterpret_cast<const char*>(data.data() + ofs), len);
            }
        }
    }

    {
        const auto& tbl = hdr.lumps[LUMP_TEXDATA_STRING_TABLE];
        const auto& dat = hdr.lumps[LUMP_TEXDATA_STRING_DATA];
        size_t n = (tbl.fileofs >= 0 && tbl.filelen > 0)
            ? static_cast<size_t>(tbl.filelen) / sizeof(int32_t) : 0;
        bsp.texnames.resize(n);
        for (size_t i = 0; i < n; ++i) {
            size_t tbl_ofs = static_cast<size_t>(tbl.fileofs) + i * 4;
            if (tbl_ofs + 4 > data.size()) { bsp.texnames[i] = ""; continue; }
            int32_t off;
            std::memcpy(&off, data.data() + tbl_ofs, 4);
            if (off < 0 || dat.fileofs < 0) { bsp.texnames[i] = ""; continue; }
            size_t str_ofs = static_cast<size_t>(dat.fileofs) + static_cast<size_t>(off);
            if (str_ofs >= data.size()) { bsp.texnames[i] = ""; continue; }
            const char* s = reinterpret_cast<const char*>(data.data() + str_ofs);
            bsp.texnames[i] = std::string(s, strnlen(s, data.size() - str_ofs));
        }
    }

    {
        const auto& gl_lump = hdr.lumps[LUMP_GAME_LUMP];
        size_t gl_off = static_cast<size_t>(gl_lump.fileofs);
        size_t gl_len = static_cast<size_t>(gl_lump.filelen);

        if (gl_len >= 4 && gl_off + gl_len <= data.size()) {
            const uint8_t* p     = data.data() + gl_off;
            const uint8_t* p_end = p + gl_len;

            int32_t lumpCount;
            std::memcpy(&lumpCount, p, 4);
            p += 4;

            for (int32_t li = 0; li < lumpCount; ++li) {
                if (p + 16 > p_end) break;

                uint32_t id;
                uint16_t gl_flags, gl_version;
                int32_t  gl_fileofs, gl_filelen;
                std::memcpy(&id,         p,      4);
                std::memcpy(&gl_flags,   p + 4,  2);
                std::memcpy(&gl_version, p + 6,  2);
                std::memcpy(&gl_fileofs, p + 8,  4);
                std::memcpy(&gl_filelen, p + 12, 4);
                p += 16;

                if (id != GAMELUMP_SPRP) continue;
                if (gl_filelen < 4) continue;

                size_t soff = static_cast<size_t>(gl_fileofs);
                if (soff + static_cast<size_t>(gl_filelen) > data.size()) continue;

                const uint8_t* sp     = data.data() + soff;
                const uint8_t* sp_end = sp + gl_filelen;

                if (sp + 4 > sp_end) break;
                int32_t nameCount;
                std::memcpy(&nameCount, sp, 4);
                sp += 4;

                if (nameCount < 0 || nameCount > 65536) break;
                std::vector<std::string> names;
                names.reserve(static_cast<size_t>(nameCount));
                for (int32_t ni = 0; ni < nameCount; ++ni) {
                    if (sp + 128 > sp_end) break;
                    const char* s = reinterpret_cast<const char*>(sp);
                    size_t len = strnlen(s, 128);
                    names.emplace_back(s, len);
                    sp += 128;
                }

                if (sp + 4 > sp_end) break;
                int32_t leafCount;
                std::memcpy(&leafCount, sp, 4);
                sp += 4;

                if (leafCount < 0) break;
                size_t leaf_stride = (gl_version >= 12) ? 4u : 2u;
                if (static_cast<size_t>(leafCount) * leaf_stride > static_cast<size_t>(sp_end - sp)) break;
                sp += static_cast<size_t>(leafCount) * leaf_stride;

                if (sp + 4 > sp_end) break;
                int32_t propCount;
                std::memcpy(&propCount, sp, 4);
                sp += 4;

                if (propCount <= 0) break;

                ptrdiff_t prop_bytes = sp_end - sp;
                if (prop_bytes <= 0) break;
                if (propCount > 1000000) break;
                if (prop_bytes < static_cast<ptrdiff_t>(56) * propCount) break;

                size_t struct_size = static_cast<size_t>(prop_bytes) / static_cast<size_t>(propCount);
                if (struct_size < 56) break;

                bsp.static_props.reserve(static_cast<size_t>(propCount));
                for (int32_t pi = 0; pi < propCount; ++pi) {
                    const uint8_t* prop = sp + static_cast<size_t>(pi) * struct_size;
                    if (prop + 56 > sp_end) break;

                    float    origin[3], angles[3];
                    uint16_t propType;
                    int32_t  skin = 0;

                    std::memcpy(origin,    prop,      12);
                    std::memcpy(angles,    prop + 12, 12);
                    std::memcpy(&propType, prop + 24,  2);
                    if (struct_size >= 36)
                        std::memcpy(&skin, prop + 32, 4);

                    StaticProp sp_out;
                    sp_out.origin[0] = origin[0];
                    sp_out.origin[1] = origin[1];
                    sp_out.origin[2] = origin[2];
                    sp_out.angles[0] = angles[0];
                    sp_out.angles[1] = angles[1];
                    sp_out.angles[2] = angles[2];
                    sp_out.skin      = skin;
                    if (static_cast<size_t>(propType) < names.size())
                        sp_out.model = names[propType];

                    bsp.static_props.push_back(std::move(sp_out));
                }
                break;
            }
        }
    }

    return bsp;
}
