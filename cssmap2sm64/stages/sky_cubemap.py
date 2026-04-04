"""
sky_cubemap.py — Extract CS:S sky_* cubemap faces from VPK and build a skybox OBJ.

Usage:
    faces = extract_sky_faces(game_path, skyname, tex_dir, vtf2png_bin)
    if faces:
        generate_cubemap_obj(out_obj_path, skyname, box_radius=200000)
        # Merge or use as sky OBJ in blend_export
"""
import os
import subprocess
from pathlib import Path

FACE_NAMES = ["ft", "bk", "lf", "rt", "up", "dn"]

# UV coords for each cube face (blender-convention V, inward-facing normals)
# Each entry: (face_id, normal, 4 verts as (x,y,z), UV as (u,v) for each vert)
# Convention: +Y = Blender forward, +Z = up, +X = right
def _cube_quads(r):
    """Return 6 quads (face_name, [(x,y,z,u,v), ...]) for an inward-facing cube of half-size r.
    Face order matches CS:S conventions: ft=forward(+Y), bk=back(-Y), lf=left(-X), rt=right(+X), dn=bottom(-Z), up=top(+Z)
    UV (0,0) = bottom-left. The faces are visible from INSIDE the box."""
    return [
        # ft: forward face (+Y), seen from inside so flip winding
        ("ft", [(-r, r, -r, 1,0), (r, r, -r, 0,0), (r, r, r, 0,1), (-r, r, r, 1,1)]),
        # bk: back face (-Y), seen from inside
        ("bk", [(r,-r,-r, 1,0), (-r,-r,-r, 0,0), (-r,-r, r, 0,1), (r,-r, r, 1,1)]),
        # lf: left face (-X), seen from inside
        ("lf", [(-r,-r,-r, 1,0), (-r, r,-r, 0,0), (-r, r, r, 0,1), (-r,-r, r, 1,1)]),
        # rt: right face (+X), seen from inside
        ("rt", [(r, r,-r, 1,0), (r,-r,-r, 0,0), (r,-r, r, 0,1), (r, r, r, 1,1)]),
        # dn: bottom face (-Z), seen from inside (looking up)
        ("dn", [(-r, r,-r, 0,0), (r, r,-r, 1,0), (r,-r,-r, 1,1), (-r,-r,-r, 0,1)]),
        # up: top face (+Z), seen from inside (looking up)
        ("up", [(-r,-r, r, 0,0), (r,-r, r, 1,0), (r, r, r, 1,1), (-r, r, r, 0,1)]),
    ]


def extract_sky_faces(game_path: str, skyname: str, tex_dir: str, vtf2png_bin: str) -> list:
    """
    Extract sky cubemap VTF files for ``skyname`` from the CS:S VPK and convert to PNG.
    Returns list of PNG paths that were created (up to 6).
    """
    if not game_path or not Path(game_path).is_dir():
        return []

    from .extract_vpk import build_game_index, extract_vtf

    idx = build_game_index(game_path)
    # Output flat to tex_dir/materials/ so find_png("skybox_tidesft") hits directly
    out_dir = Path(tex_dir) / "materials"
    out_dir.mkdir(parents=True, exist_ok=True)

    vtf_paths = []
    for face in FACE_NAMES:
        slug_key = f"skybox_{skyname}{face}.vtf"
        if slug_key not in idx:
            print(f"  [sky_cubemap] {slug_key} not found in VPK", flush=True)
            continue
        vtf_out = out_dir / f"skybox_{skyname}{face}.vtf"
        png_out  = out_dir / f"skybox_{skyname}{face}.png"
        if not png_out.exists():
            extract_vtf(idx[slug_key], str(vtf_out))
            vtf_paths.append((str(vtf_out), str(png_out)))
        else:
            print(f"  [sky_cubemap] {png_out.name} already exists, skipping", flush=True)

    if vtf_paths:
        list_file = out_dir / "_sky_cubemap_list.txt"
        with open(list_file, "w") as lf:
            lf.write("32\n")  # max_size=32 → 32x32 square cubemap tiles
            for vtf, png in vtf_paths:
                lf.write(vtf + "\n")
                lf.write(png + "\n")
        subprocess.run([vtf2png_bin, "@", str(list_file)], check=True)
        print(f"  [sky_cubemap] converted {len(vtf_paths)} cubemap faces to PNG", flush=True)

    # Return existing PNGs
    found = []
    for face in FACE_NAMES:
        p = out_dir / f"skybox_{skyname}{face}.png"
        if p.exists():
            found.append(str(p))
    return found


def generate_cubemap_obj(out_obj_path: str, skyname: str, box_radius: int = 20000,
                         tex_dir: str = None, sm64_origin: tuple = (0, 0, 0)) -> None:
    """
    Write an OBJ file containing 6 inward-facing quads (a skybox cube) of half-size ``box_radius``.
    Each face uses material name ``skybox_{skyname}{face}`` so blend_export can find the PNG.
    sm64_origin offsets the box centre to the SM64 sky origin so the sky camera is inside the cube.
    If tex_dir is provided, map_Kd entries are written into the MTL for pre-loading by Blender.
    """
    out_obj_path = Path(out_obj_path)
    mtl_path = out_obj_path.with_suffix(".sky_cube.mtl")

    quads = _cube_quads(box_radius)

    with open(mtl_path, "w") as mtl:
        for face, _ in quads:
            mat_name = f"skybox_{skyname}{face}"
            mtl.write(f"newmtl {mat_name}\n")
            if tex_dir:
                png = Path(tex_dir) / "materials" / f"{mat_name}.png"
                if png.exists():
                    mtl.write(f"map_Kd {png.as_posix()}\n")
            mtl.write("\n")

    with open(out_obj_path, "w") as obj:
        obj.write(f"mtllib {mtl_path.name}\n\n")

        # Write all vertices
        ox, oy, oz = sm64_origin
        v_idx = 1
        face_vi = []
        for _face, verts in quads:
            face_vi.append(v_idx)
            for x, y, z, u, v in verts:
                # Blender import: -Z forward, Y up → OBJ(x, z, -y) maps to SM64(x, z, -y)
                # Adding sm64_origin offsets the cube centre to the SM64 sky origin.
                obj.write(f"v {x + ox} {z + oy} {-y + oz}\n")
            v_idx += len(verts)
        obj.write("\n")

        # Write all UVs
        vt_idx = 1
        face_vti = []
        for _face, verts in quads:
            face_vti.append(vt_idx)
            for x, y, z, u, v in verts:
                obj.write(f"vt {u} {v}\n")
            vt_idx += len(verts)
        obj.write("\n")

        # Write faces
        for i, (face, verts) in enumerate(quads):
            vi = face_vi[i]
            vti = face_vti[i]
            n = len(verts)  # 4 = quad
            obj.write(f"o skybox_{skyname}{face}\n")
            obj.write(f"usemtl skybox_{skyname}{face}\n")
            # Quad split into 2 triangles, winding: inward normals
            # 0,1,2,3 → tri 0,1,2 and tri 0,2,3
            # 'up' (top) and 'dn' (bottom) faces have their winding reversed by the
            # OBJ-to-Blender axis transform so their normals end up pointing outward
            # (away from the camera inside the box).  Flip them here so they are
            # inward-facing and pass G_CULL_BACK.
            if face in ('up', 'dn'):
                obj.write(f"f {vi+0}/{vti+0} {vi+2}/{vti+2} {vi+1}/{vti+1}\n")
                obj.write(f"f {vi+0}/{vti+0} {vi+3}/{vti+3} {vi+2}/{vti+2}\n")
            else:
                obj.write(f"f {vi+0}/{vti+0} {vi+1}/{vti+1} {vi+2}/{vti+2}\n")
                obj.write(f"f {vi+0}/{vti+0} {vi+2}/{vti+2} {vi+3}/{vti+3}\n")
            obj.write("\n")

    print(f"  [sky_cubemap] wrote {out_obj_path.name}", flush=True)
