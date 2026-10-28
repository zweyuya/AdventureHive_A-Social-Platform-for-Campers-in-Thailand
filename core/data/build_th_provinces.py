"""Rebuild core/data/th_provinces.json from geoBoundaries (simplified) downloads.

Thai provinces (THA ADM1) + outlines of neighbouring countries (ADM0) near Thailand.
"""
import json
import sys
from pathlib import Path

RENAME = {"Phangnga": "Phang Nga"}
NEIGHBOURS = {"LAO": "Laos", "KHM": "Cambodia", "MMR": "Myanmar", "MYS": "Malaysia"}
BOX = (96.5, 4.5, 106.5, 21.5)  # lng/lat window around Thailand; farther polygons are dropped

src_dir, dst = Path(sys.argv[1]), sys.argv[2]


def rnd(c):
    return [round(c[0], 5), round(c[1], 5)]


def polygons(geometry):
    polys = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    return [[[rnd(c) for c in ring] for ring in poly] for poly in polys]


def near_thailand(poly):
    xs = [c[0] for c in poly[0]]
    ys = [c[1] for c in poly[0]]
    return max(xs) >= BOX[0] and min(xs) <= BOX[2] and max(ys) >= BOX[1] and min(ys) <= BOX[3]


provinces = []
for f in json.loads((src_dir / "gb.geojson").read_text())["features"]:
    name = f["properties"]["shapeName"].removesuffix(" Province")
    provinces.append({"name": RENAME.get(name, name), "iso": f["properties"]["shapeISO"],
                      "polygons": polygons(f["geometry"])})
provinces.sort(key=lambda p: p["name"])

neighbours = []
for code, name in NEIGHBOURS.items():
    polys = [p for f in json.loads((src_dir / f"{code}.geojson").read_text())["features"]
             for p in polygons(f["geometry"]) if near_thailand(p)]
    neighbours.append({"name": name, "polygons": polys})

out = {
    "source": "geoBoundaries (gbOpen, simplified): THA ADM1; LAO, KHM, MMR, MYS ADM0 — "
              "https://www.geoboundaries.org",
    "license": "Data © OpenStreetMap contributors. ODbL 1.0 (Thailand, Laos, Cambodia, Malaysia); "
               "CC BY-SA 2.0 (Myanmar).",
    "provinces": provinces,
    "neighbours": neighbours,
}
Path(dst).write_text(json.dumps(out, separators=(",", ":")))
print(len(provinces), "provinces,", [(n["name"], len(n["polygons"])) for n in neighbours])

# Usage (download the files into one folder first, then run from the project root):
#   gb.geojson  = THA ADM1 simplified  (https://www.geoboundaries.org/api/current/gbOpen/THA/ADM1/)
#   LAO/KHM/MMR/MYS.geojson = ADM0 simplified for each neighbour (same API, .../<ISO>/ADM0/)
#   python core/data/build_th_provinces.py <download-folder> core/data/th_provinces.json
