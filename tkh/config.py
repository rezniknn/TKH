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
import os
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "configs" / "default.toml"
ENV_VAR = "TKH_CONFIG"


@dataclass(frozen=True)
class Config:
    graph: Path                          # TKH export: JSON with meta, nodes, hyperedges
    articles: Path | None = None         # optional CSV with columns id, year (title, arxiv_id used if present)
    questions: Path | None = None        # optional; T6 extrinsic task queries
    ground_truth: Path | None = None     # optional; T6 targets and faithfulness references
    cutoffs: tuple = (2020, 2022, 2024, 2026)
    out_dir: Path = REPO_ROOT / "out"
    figures_dir: Path = REPO_ROOT / "figures"
    source: Path | None = field(default=None, compare=False)  # the file this config was read from


INPUTS = ("graph", "articles", "questions", "ground_truth")
OUTPUTS = ("out_dir", "figures_dir")


def load_config(path=None):
    path = Path(path or os.environ.get(ENV_VAR) or DEFAULT_CONFIG).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"config file not found: {path}")
    raw = tomllib.loads(path.read_text())
    inputs, snaps, outputs = raw.get("inputs", {}), raw.get("snapshots", {}), raw.get("outputs", {})
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
    cfg = Config(source=path, **kw)
    check_inputs(cfg)
    return cfg


def check_inputs(cfg):
    for name in INPUTS:
        p = getattr(cfg, name)
        if p is not None and not p.is_file():
            raise FileNotFoundError(f"input '{name}' not found: {p} (config: {cfg.source})")
    if len(cfg.cutoffs) < 3:
        raise ValueError(f"need at least 3 snapshot cutoffs, got {cfg.cutoffs}")


def add_config_args(parser: argparse.ArgumentParser):
    parser.add_argument("--config", help=f"TOML config (default: ${ENV_VAR} or {DEFAULT_CONFIG.relative_to(REPO_ROOT)})")
    for name in INPUTS + OUTPUTS:
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, help=f"override {name}")
    parser.add_argument("--cutoffs", type=int, nargs="+", help="override snapshot cutoff years")
    return parser


def config_from_args(args):
    cfg = load_config(args.config)
    over = {n: getattr(args, n).expanduser().resolve() for n in INPUTS + OUTPUTS if getattr(args, n, None)}
    if getattr(args, "cutoffs", None):
        over["cutoffs"] = tuple(sorted(args.cutoffs))
    cfg = replace(cfg, **over)
    check_inputs(cfg)
    return cfg
