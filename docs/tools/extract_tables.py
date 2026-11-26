# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

"""Extract the benchmark numbers from the paper's LaTeX tables into assets/data/results.json.

    python tools/extract_tables.py [PAPER_REPO]

The site never carries a hand-typed score: rerun this after the tables change.
"""
import json
import re
import sys
from pathlib import Path

PAPER = Path(sys.argv[1] if len(sys.argv) > 1 else "/p/3dllmselftraining/infd4rt/reference/cvpr_2027_metric_4d_modeling")
OUT = Path(__file__).resolve().parent.parent / "assets" / "data" / "results.json"
NUM = re.compile(r"(?<![\w.])\d+\.\d+(?![\w.])")
MARKS = {r"\dagger": "dagger", r"\ddagger": "ddagger", r"\S": "section", "*": "tto"}


def rows(path):
    """Table rows of a .tex file with comments removed, as one string per `\\\\`-terminated row."""
    text = "\n".join(l for l in path.read_text().splitlines() if not l.lstrip().startswith("%"))
    body = text[text.index(r"\begin{tabular"):text.index(r"\end{tabular")]
    return [r.strip() for r in re.split(r"\\\\", body)]


def label(cell):
    """Clean method name and its scale-convention marks from a LaTeX cell."""
    marks = []
    for sup in re.findall(r"\$\^\{([^}]*)\}\$", cell):
        for tex, name in MARKS.items():
            if tex == r"\dagger" and r"\ddagger" in sup:
                continue
            if tex in sup:
                marks.append(name)
    s = re.sub(r"\$\^\{[^}]*\}\$", "", cell)
    s = re.sub(r"~?\\cite\{[^}]*\}", "", s)
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\textsc\{([^}]*)\}", lambda m: "-" + m.group(1).capitalize(), s)
    s = re.sub(r"\\multirow\{[^}]*\}(\[[^\]]*\])?\{[^}]*\}\{([^}]*)\}", r"\2", s)
    return " ".join(s.split()), marks


def tracking():
    out = {"Metric": [], "Non-metric": []}
    block = None
    for r in rows(PAPER / "tables" / "tab_main_tracking.tex"):
        r = re.sub(r"\\(cmidrule|midrule|toprule|bottomrule)(\(\w+\))?(\{[^}]*\})?", " ", r)
        m = re.search(r"\\multirow\{\d+\}\{\*\}\{\\textbf\{(Metric|Non-metric)\}\}", r)
        if m:
            block = m.group(1)
            r = r[m.end():]
        cells = [c.strip() for c in r.split("&")]
        vals = [float(x) for x in NUM.findall(re.sub(r"\\(first|second|third)\b", " ", r))]
        if block and len(vals) == 12:
            name, marks = label(next(c for c in cells if c and not NUM.search(c)))
            out[block].append({"method": name, "marks": marks, "values": vals})
    return out


def multiview():
    out, method = [], None
    for r in rows(PAPER / "tables" / "tab_mv_tracking.tex"):
        r = re.sub(r"\\(cmidrule|midrule|toprule|bottomrule)(\(\w+\))?(\{[^}]*\})?", " ", r)
        m = re.search(r"\\multirow\{\d+\}\{\*\}\{(\w+)~\\cite\{[^}]*\}\}", r)
        if m:
            method = m.group(1)
            r = r[m.end():]
        vals = [float(x) for x in NUM.findall(re.sub(r"\\(first|second|third)\b", " ", r))]
        if len(vals) != 12:
            continue
        cells = [c.strip() for c in r.split("&")]
        if "Ours" in r:
            out.append({"method": "Ours", "depth": None, "values": vals})
        else:
            depth = next(c for c in cells if c and not NUM.search(c))
            out.append({"method": method, "depth": label(depth)[0], "values": vals})
    return out


def depth():
    out = []
    for r in rows(PAPER / "tables" / "tab_main_video_depth.tex"):
        r = re.sub(r"\\(cmidrule|midrule|toprule|bottomrule)(\(\w+\))?(\{[^}]*\})?", " ", r)
        vals = [float(x) for x in NUM.findall(re.sub(r"\\(first|second|third)\b", " ", r))]
        if len(vals) == 6:
            name, marks = label(r.split("&")[0].strip())
            out.append({"method": name, "marks": marks, "values": vals})
    return out


def main():
    data = {"tracking": tracking(), "multiview": multiview(), "depth": depth()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1))
    print({k: len(v) for k, v in data["tracking"].items()}, len(data["multiview"]), len(data["depth"]))
    for k, v in data["tracking"].items():
        print(k, [(e["method"], e["marks"], e["values"][0]) for e in v])
    print([(e["method"], e["depth"], e["values"][0]) for e in data["multiview"]])
    print([(e["method"], e["marks"], e["values"]) for e in data["depth"]])


if __name__ == "__main__":
    main()
