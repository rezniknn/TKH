"""Static guard for notebooks: matplotlib keywords that only exist in some supported versions must be version-gated.

Supported range (README): matplotlib 3.7 - 3.11. `Axes.boxplot(orientation=...)` exists only from 3.10
and `boxplot(labels=...)` was renamed `tick_labels` in 3.9; both have broken a notebook in an older
environment before. Allowed form: build the keyword dict under a version check, e.g.
    horizontal = {"orientation": "horizontal"} if MPL >= (3, 10) else {"vert": False}
"""

from pathlib import Path
import re

import nbformat
import pytest

NOTEBOOKS = sorted((Path(__file__).resolve().parent.parent / "notebooks").glob("*.ipynb"))


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_version_specific_matplotlib_keywords_are_gated(path):
    nb = nbformat.read(path, 4)
    problems = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        for line in cell.source.splitlines():
            line = line.split("#", 1)[0]  # ignore comments
            if re.search(r"\borientation\s*=", line) or re.search(r"[\"']orientation[\"']", line):
                if "MPL" not in line:
                    problems.append(f"cell {i}: {line.strip()}")
            if re.search(r"boxplot\(.*\b(tick_)?labels\s*=", line):
                problems.append(f"cell {i}: {line.strip()}")
    assert not problems, "\n".join(problems)
