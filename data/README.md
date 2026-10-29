# Input data

The inputs provided with the assignment, read through the paths in `configs/default.toml`:

| File | Content | Read by |
|---|---|---|
| `tkh_collection10.json` | The TKH temporal export: `meta`, `nodes` and `hyperedges` (required) | `tkh/io.py` |
| `collection10_articles.csv` | Per-article id, year, arXiv id, status and title (optional; otherwise derived from the graph) | `tkh/io.py` |
| `questions.csv`, `ground_truth.json` | T6 retrieval questions and their gold answers (format: `notebooks/05_retrieval_design.ipynb`) | `eval/retrieval.py` |
| `llm_cache.json` | Committed LLM response cache for labels and the faithfulness judge; offline runs replay from it | `tkh/llm.py` |

Snapshots are cut from the export by publication year (`tkh/io.py`: snapshot ≤t holds the nodes and hyper-edges of
papers published up to t).
