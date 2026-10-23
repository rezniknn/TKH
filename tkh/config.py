"""Run configuration: input paths, snapshot cutoffs and output locations, read from a TOML file.

Which config file is used, in order of precedence:
1. an explicit path (a script's --config flag, or load_config(path));
2. the TKH_CONFIG environment variable;
3. configs/default.toml in this repository.

Relative paths in a config file are resolved against the directory of that file,
so a config can live next to the data it describes. Scripts can override single
values on the command line via add_config_args() / config_from_args().
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
import argparse
import json
import os
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "configs" / "default.toml"
ENV_VAR = "TKH_CONFIG"


@dataclass(frozen=True)
class Config:
    graph: Path                          # TKH export: JSON with meta, nodes, hyperedges
    articles: Path | None = None         # optional CSV with columns id, year (title, arxiv_id used if present)
    cutoffs: tuple = (2020, 2022, 2024, 2026)
    budgets: tuple = (15, 60, 240)       # P2: max super-nodes at level 0, 1, 2, ... (hard limits)
    out_dir: Path = REPO_ROOT / "out"
    figures_dir: Path = REPO_ROOT / "figures"
    method: dict = field(default_factory=dict)   # [method]: clustering parameters (tkh.hierarchy.Params)
    source: Path | None = field(default=None, compare=False)  # the file this config was read from


INPUTS = ("graph", "articles")
OUTPUTS = ("out_dir", "figures_dir")


def load_config(path=None):
    path = Path(path or os.environ.get(ENV_VAR) or DEFAULT_CONFIG).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    raw = tomllib.loads(path.read_text())
    inputs, snaps, outputs = raw.get("inputs", {}), raw.get("snapshots", {}), raw.get("outputs", {})
    hier = raw.get("hierarchy", {})
    unknown = set(inputs) - set(INPUTS) | set(outputs) - set(OUTPUTS)
    if unknown:
        raise ValueError(f"{path}: unknown keys {sorted(unknown)}")
    if "graph" not in inputs:
        raise ValueError(f"{path}: [inputs] graph is required")

    def resolve(p):
        p = Path(p).expanduser()
        return p if p.is_absolute() else (path.parent / p).resolve()

    kw = {k: resolve(v) for k, v in {**inputs, **outputs}.items() if v}
    if "cutoffs" in snaps:
        kw["cutoffs"] = tuple(sorted(int(c) for c in snaps["cutoffs"]))
    if "budgets" in hier:
        kw["budgets"] = tuple(int(b) for b in hier["budgets"])
    kw["method"] = dict(raw.get("method", {}))
    cfg = Config(source=path, **kw)
    check_inputs(cfg)
    return cfg


def check_inputs(cfg):
    for name in INPUTS:
        p = getattr(cfg, name)
        if p is not None and not p.is_file():
            raise FileNotFoundError(f"input '{name}' not found: {p} (config: {cfg.source})")
    if len(set(cfg.cutoffs)) != len(cfg.cutoffs) or len(cfg.cutoffs) < 3:
        raise ValueError(f"need at least 3 distinct snapshot cutoffs, got {cfg.cutoffs}")
    if len(cfg.budgets) < 2 or any(b < 1 for b in cfg.budgets) or list(cfg.budgets) != sorted(cfg.budgets):
        raise ValueError(f"need >= 2 positive, non-decreasing budgets from level 0 (levels 0 and 1 are labelled), got {cfg.budgets}")


def add_config_args(parser: argparse.ArgumentParser):
    parser.add_argument("--config", help=f"TOML config (default: ${ENV_VAR} or {DEFAULT_CONFIG.relative_to(REPO_ROOT)})")
    for name in INPUTS + OUTPUTS:
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, help=f"override {name}")
    parser.add_argument("--cutoffs", type=int, nargs="+", help="override snapshot cutoff years")
    parser.add_argument("--budgets", type=int, nargs="+", help="override per-level super-node budgets")
    return parser


def config_from_args(args):
    cfg = load_config(args.config)
    over = {n: getattr(args, n).expanduser().resolve() for n in INPUTS + OUTPUTS if getattr(args, n, None)}
    if getattr(args, "cutoffs", None):
        over["cutoffs"] = tuple(sorted(args.cutoffs))
    if getattr(args, "budgets", None):
        over["budgets"] = tuple(args.budgets)
    cfg = replace(cfg, **over)
    check_inputs(cfg)
    return cfg


def parse_overrides(pairs):
    """['alpha=0.25', 'rho="inf"', ...] -> {key: JSON-decoded value, or the raw string}."""
    out = {}
    for p in pairs or []:
        k, v = p.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def to_toml(cfg, method, where):
    """The resolved run configuration as TOML text for a file in directory `where` (input paths relative to it),
    so a run can be re-validated or rebuilt on its own, also from another checkout."""
    val = lambda v: f'"{v}"' if isinstance(v, (str, Path)) else str(list(v)) if isinstance(v, (list, tuple)) else str(v).lower() if isinstance(v, bool) else str(v)  # noqa: E731
    rel = lambda p: os.path.relpath(Path(p).resolve(), Path(where).resolve())  # noqa: E731
    lines = ["[inputs]", f"graph = {val(rel(cfg.graph))}"] + ([f"articles = {val(rel(cfg.articles))}"] if cfg.articles else [])
    lines += ["", "[snapshots]", f"cutoffs = {val(cfg.cutoffs)}", "", "[hierarchy]", f"budgets = {val(cfg.budgets)}", "", "[method]"]
    lines += [f"{k} = {val(v)}" for k, v in method.items()]
    return "\n".join(lines) + "\n"
