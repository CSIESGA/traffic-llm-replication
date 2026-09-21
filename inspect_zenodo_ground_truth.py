"""Statically inspect installed Zenodo Python code without importing/executing it."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

KEYWORDS = (
    "conflict", "vehicle", "priority", "waiting", "scenario", "intersection",
    "time_to_intersection", "yield", "trajectory", "collision",
)


def inspect_python(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return {"path": str(path), "syntax_error": str(exc)}

    functions = []
    classes = []
    imports = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({"name": node.name, "line": node.lineno, "args": [a.arg for a in node.args.args]})
        elif isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes.append({"name": node.name, "line": node.lineno, "methods": methods})
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.get_source_segment(text, node) or "")

    keyword_hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        lower = line.lower()
        if any(k in lower for k in KEYWORDS):
            keyword_hits.append({"line": lineno, "text": line.strip()[:300]})
            if len(keyword_hits) >= 80:
                break
    return {
        "path": str(path),
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "keyword_hits": keyword_hits,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect the installed Zenodo record without executing its code.")
    ap.add_argument("--root", default="vendor/zenodo_14171745")
    ap.add_argument("--output", default="vendor/zenodo_14171745/inspection.json")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(
            f"Zenodo material is not installed at {root}. Run: python install_zenodo_ground_truth.py"
        )

    files = sorted(root.rglob("*.py"))
    notebooks = sorted(root.rglob("*.ipynb"))
    data_files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".csv", ".xlsx", ".txt"}
    )
    report = {
        "python_files": [inspect_python(p) for p in files],
        "notebooks": [str(p) for p in notebooks],
        "data_files": [str(p) for p in data_files],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Python files: {len(files)}")
    print(f"Notebooks: {len(notebooks)}")
    print(f"Data/text files: {len(data_files)}")
    print(f"Inspection report: {out}")
    if files:
        print("\nCandidate top-level functions:")
        for item in report["python_files"]:
            for f in item.get("functions", []):
                score = sum(k in f["name"].lower() for k in KEYWORDS)
                if score:
                    print(f"  {item['path']}:{f['line']}  {f['name']}({', '.join(f['args'])})")


if __name__ == "__main__":
    main()
