"""Optional (deliverable 6): static figure of levels 0-2 across snapshots, saved to figures/. No interactive frontend.

    python scripts/visualize.py [--config CFG] [--out DIR] [--figures DIR]

An icicle per snapshot: one row per level (0 on top), each super-node a box whose width is
its number of concept nodes, ordered under its parent. Colour = the persistent id of the
level-0 ancestor (tkh/temporal ids), so a colour that keeps its place from one snapshot to
the next is a top-level super-node that persisted.
"""

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from tkh.config import add_config_args, config_from_args  # noqa: E402
from tkh.io import load  # noqa: E402
from tkh.semantic import CONCEPT_TYPES  # noqa: E402


def icicle(ax, h, concept, colour_of):
    sns = h["supernodes"]
    kids = {}
    for s in sns:
        kids.setdefault(s["parent_id"], []).append(s)
    size = {s["id"]: sum(v in concept for v in s["member_ids"]) for s in sns}

    def draw(s, x, root):
        w = size[s["id"]]
        ax.add_patch(plt.Rectangle((x, -s["level"] - 1), w, 0.92, facecolor=colour_of(root), edgecolor="white", linewidth=0.3))
        if s["level"] == 0 and w > 0.05 * len(concept):
            n = max(4, int(150 * w / len(concept)))  # characters that fit the box at this font size
            lab = s["label"] if len(s["label"]) <= n else s["label"][:n - 1] + "…"
            ax.text(x + w / 2, -0.54, lab, ha="center", va="center", fontsize=6, clip_on=True)
        cx = x
        for c in sorted(kids.get(s["id"], []), key=lambda c: -size[c["id"]]):
            draw(c, cx, root)
            cx += size[c["id"]]

    x = 0
    for s in sorted(kids[None], key=lambda s: s["id"]):
        draw(s, x, s["id"])
        x += size[s["id"]]
    ax.set_xlim(0, x)
    ax.set_ylim(-h["levels"] - 0.1, 0.05)
    ax.set_yticks([-k - 0.54 for k in range(h["levels"])], [f"level {k}" for k in range(h["levels"])])
    ax.set_xlabel("concept nodes")


def main(argv=None):
    p = add_config_args(argparse.ArgumentParser(description=__doc__.split("\n")[0]))
    p.add_argument("--out", type=Path, help="output directory with <cutoff>/hierarchy.json (default: config out_dir)")
    p.add_argument("--figures", type=Path, help="figure directory (default: config figures_dir)")
    args = p.parse_args(argv)
    cfg = config_from_args(args)
    out = Path(args.out or cfg.out_dir)
    figs = Path(args.figures or cfg.figures_dir)
    figs.mkdir(parents=True, exist_ok=True)
    tkh = load(cfg)
    ntype = tkh.nodes["type"].to_dict()
    hier = {c: json.loads((out / str(c) / "hierarchy.json").read_text()) for c in cfg.cutoffs}
    roots = sorted({s["id"] for h in hier.values() for s in h["supernodes"] if s["level"] == 0})
    cmap = plt.get_cmap("tab20")
    colour_of = lambda r: cmap(roots.index(r) % 20)  # noqa: E731
    fig, axes = plt.subplots(len(hier), 1, figsize=(11, 2.1 * len(hier)))
    for ax, (c, h) in zip(axes, hier.items()):
        concept = {v for s in h["supernodes"] if s["level"] == 0 for v in s["member_ids"] if ntype[v] in CONCEPT_TYPES}
        icicle(ax, h, concept, colour_of)
        ax.set_title(f"≤{c}: {len(concept)} concept nodes", loc="left", fontsize=9)
    fig.tight_layout()
    path = figs / "hierarchy_levels.png"
    fig.savefig(path, dpi=160)
    print(f"-> {path}")


if __name__ == "__main__":
    main()
