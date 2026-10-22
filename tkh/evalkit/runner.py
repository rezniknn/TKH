"""The one hook through which the evaluator re-runs a method: [eval] build_cmd.

build_cmd is a shell template with {python}, {graph} and {out} placeholders plus any extra text configured per run
(e.g. method parameters). The evaluator writes a graph export (perturbed or null), calls the command, and reads the
artefacts the method writes to {out}. Builds are cached: a stamp records the graph file hash and the command, and a
build is skipped if both match.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import shlex
import subprocess
import sys

from tkh.evalkit.exports import file_hash


def command(template, graph, out, extra=""):
    return template.format(python=shlex.quote(sys.executable), graph=shlex.quote(str(graph)), out=shlex.quote(str(out)),
                           extra=extra).strip()


def build(template, graph, out, extra="", cwd=None, force=False):
    out = Path(out)
    cmd = command(template, graph, out, extra)
    stamp = {"graph": file_hash(graph), "cmd": cmd}
    sp = out / ".eval_stamp.json"
    if not force and sp.exists() and json.loads(sp.read_text()) == stamp:
        return out
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
           "VECLIB_MAXIMUM_THREADS": "1"}
    r = subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"build_cmd failed ({r.returncode}): {cmd}\n{r.stderr[-2000:]}")
    sp.write_text(json.dumps(stamp))
    return out


def build_many(template, jobs, n_jobs=8, cwd=None, log=print):
    """jobs: [(graph, out, extra)]; runs builds in parallel subprocesses (the method runs out of process)."""
    done = []
    with ThreadPoolExecutor(n_jobs) as ex:
        futs = [ex.submit(build, template, g, o, x, cwd) for g, o, x in jobs]
        for i, f in enumerate(futs, 1):
            done.append(f.result())
            if i % 10 == 0 or i == len(futs):
                log(f"  builds {i}/{len(futs)}")
    return done
