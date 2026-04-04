import re
import sys
from pathlib import Path

MAX_VERTS = 32767


def split_collision_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")

    m = re.search(r'COL_VERTEX_INIT\((\d+)\)', text)
    if not m:
        return False
    vcount = int(m.group(1))
    if vcount <= MAX_VERTS:
        return False

    print(f"  vertex count {vcount} > {MAX_VERTS}, splitting {path}")

    decl_m = re.search(r'(const Collision \w+\[\] = \{)', text)
    if not decl_m:
        print("  could not find array declaration, skipping")
        return False

    preamble = text[:decl_m.start()]
    decl = decl_m.group(1)

    raw_vertices = re.findall(r'COL_VERTEX\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)', text)
    vertices = [(int(x), int(y), int(z)) for x, y, z in raw_vertices]

    tri_groups = []
    for tm in re.finditer(r'COL_TRI_INIT\((\w+)\s*,\s*\d+\)', text):
        surf_type = tm.group(1)
        after = text[tm.end():]
        stop_m = re.search(r'COL_TRI_STOP\s*\(\s*\)|COL_TRI_INIT\s*\(', after)
        chunk = after[:stop_m.start()] if stop_m else after
        tris = [(int(a), int(b), int(c)) for a, b, c in
                re.findall(r'COL_TRI\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', chunk)]
        tri_groups.append((surf_type, tris))

    specials_m = re.search(
        r'(COL_SPECIAL_INIT\(.*?\)(?:.*?\n)*?.*?(?=\s*COL_WATER_BOX|\s*COL_END))',
        text, re.DOTALL)
    water_m = re.search(
        r'(COL_WATER_BOX_INIT\(.*?\)(?:.*?\n)*?.*?(?=\s*COL_END))',
        text, re.DOTALL)

    specials_block = specials_m.group(1).strip() if specials_m else ""
    water_block = water_m.group(1).strip() if water_m else ""

    all_tris = []
    for surf_type, tris in tri_groups:
        for tri in tris:
            all_tris.append((surf_type, tri))

    blocks = []
    cur_vmap = {}
    cur_verts = []
    cur_tris_by_type = {}

    for surf_type, (g0, g1, g2) in all_tris:
        needed = sum(1 for v in (g0, g1, g2) if v not in cur_vmap)
        if len(cur_verts) + needed > MAX_VERTS:
            if cur_verts:
                blocks.append((list(cur_verts), dict(cur_tris_by_type)))
            cur_vmap = {}
            cur_verts = []
            cur_tris_by_type = {}

        local = []
        for v in (g0, g1, g2):
            if v not in cur_vmap:
                cur_vmap[v] = len(cur_verts)
                cur_verts.append(vertices[v])
            local.append(cur_vmap[v])

        if surf_type not in cur_tris_by_type:
            cur_tris_by_type[surf_type] = []
        cur_tris_by_type[surf_type].append(tuple(local))

    if cur_verts:
        blocks.append((list(cur_verts), dict(cur_tris_by_type)))

    total_verts_out = sum(len(b[0]) for b in blocks)
    total_tris_out = sum(sum(len(ts) for ts in b[1].values()) for b in blocks)
    print(f"  split into {len(blocks)} blocks, total verts={total_verts_out} tris={total_tris_out}")

    out = preamble + decl + "\n"

    for verts, tris_by_type in blocks:
        out += "\tCOL_INIT(),\n"
        out += f"\tCOL_VERTEX_INIT({len(verts)}),\n"
        for x, y, z in verts:
            out += f"\tCOL_VERTEX({x}, {y}, {z}),\n"
        for surf_type, tris in tris_by_type.items():
            out += f"\tCOL_TRI_INIT({surf_type}, {len(tris)}),\n"
            for v1, v2, v3 in tris:
                out += f"\tCOL_TRI({v1}, {v2}, {v3}),\n"
        out += "\tCOL_TRI_STOP(),\n"

    if specials_block:
        out += "\t" + specials_block + "\n"
    if water_block:
        out += "\t" + water_block + "\n"

    out += "\tCOL_END()\n};\n"

    path.write_text(out, encoding="utf-8")
    print(f"  wrote {path}")
    return True


if __name__ == "__main__":
    paths = sys.argv[1:] if len(sys.argv) > 1 else []
    for p in paths:
        split_collision_file(Path(p))
