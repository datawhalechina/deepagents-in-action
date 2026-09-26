"""Validate, execute in an isolated project kernel, and export course notebooks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

import nbformat
from dotenv import dotenv_values
from jupyter_client import AsyncKernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient
from nbconvert import HTMLExporter, MarkdownExporter

from .model_config import repository_root, selected_mode

LINK = re.compile(r"!?\[[^\]]*\]\(([^\s)]+)\)")


def validate_catalog(root, entries):
    chapters = json.loads((root / "scripts/chapters.json").read_text())
    seen = set()
    for entry in entries:
        if entry["id"] in seen or not re.fullmatch(r"[a-z0-9-]+", entry["id"]):
            raise ValueError(f"Invalid or duplicate notebook id: {entry['id']}")
        seen.add(entry["id"])
        path = (root / "notebooks" / entry["path"]).resolve()
        if not path.is_relative_to((root / "notebooks").resolve()):
            raise ValueError("Notebook path must stay inside notebooks/")
        if entry.get("kind") != "template" and entry["chapter_id"] not in chapters:
            raise ValueError(f"Unknown chapter: {entry['chapter_id']}")
        nb = nbformat.read(path, as_version=4)
        nbformat.validate(nb)
        for cell in nb.cells:
            if cell.cell_type == "markdown":
                for target in LINK.findall(cell.source):
                    url = urlsplit(target)
                    if not url.scheme and url.path and not (path.parent / unquote(url.path)).exists():
                        raise ValueError(f"Missing local link in {entry['id']}: {target}")


def source_hash(nb):
    data = [(c.cell_type, c.source) for c in nb.cells]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()


def git_commit(root):
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else None


def kernel_environment(root, mode):
    env = os.environ.copy()
    if mode == "live":
        for key, value in dotenv_values(root / ".env").items():
            if value is not None:
                env.setdefault(key, value)
    else:
        for key in list(env):
            if key.startswith(("MODEL_", "SILICONFLOW_", "OPENAI_", "LANGSMITH_", "LANGCHAIN_")):
                del env[key]
        env["LANGSMITH_TRACING"] = "false"
        env["LANGCHAIN_TRACING_V2"] = "false"
    env["COURSE_MODE"] = mode
    env["NO_PROXY"] = env.get("NO_PROXY", "") + ",localhost,127.0.0.1"
    env["no_proxy"] = env["NO_PROXY"]
    return env


def stage_chapter(root, path, stage):
    (stage / "scripts").mkdir()
    shutil.copy2(root / "scripts/chapters.json", stage / "scripts/chapters.json")
    destination = stage / path.parent.relative_to(root)
    shutil.copytree(path.parent, destination, ignore=shutil.ignore_patterns(".env", ".venv", "__pycache__", ".ipynb_checkpoints", ".langgraph_api"))
    (stage / "content").mkdir()
    # Chapter source is small; it also supports independent notebook root detection.
    for chapter in (root / "content").glob("*.md"):
        shutil.copy2(chapter, stage / "content" / chapter.name)


def export_reading(nb, path, root, output_dir, notebook_id, commit, *, relative_links=False):
    reading = nbformat.reads(nbformat.writes(nb), as_version=4)
    reading.cells.insert(0, nbformat.v4.new_markdown_cell(
        f"> 本次执行模式：**{nb.metadata.course_run.mode}**。源码指纹：`{nb.metadata.course_run.source_hash[:12]}`。",
        id="course-run-info",
    ))
    # Exported artifacts are outside the source tree: link back to exact source paths.
    for cell in reading.cells:
        if cell.cell_type == "markdown" and not relative_links:
            def resolve(match):
                target = match.group(1)
                url = urlsplit(target)
                if url.scheme or not url.path:
                    return match.group(0)
                resolved = (path.parent / unquote(url.path)).resolve()
                if not resolved.is_relative_to(root):
                    return match.group(0)
                link = f"https://github.com/datawhalechina/deepagents-in-action/blob/{commit or 'main'}/{resolved.relative_to(root).as_posix()}"
                if url.fragment:
                    link += "#" + url.fragment
                start = match.start(1) - match.start(0)
                end = match.end(1) - match.start(0)
                return match.group(0)[:start] + link + match.group(0)[end:]
            cell.source = LINK.sub(resolve, cell.source)
    for extension, exporter in (("html", HTMLExporter()), ("md", MarkdownExporter())):
        body, resources = exporter.from_notebook_node(reading, resources={"unique_key": notebook_id})
        (output_dir / f"{notebook_id}.{extension}").write_text(body)
        for filename, data in resources.get("outputs", {}).items():
            asset = output_dir / filename
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(data)


def validate_reading(root, entries):
    """Check committed reading copies against the saved, successfully executed notebook."""
    for entry in entries:
        path = root / "notebooks" / entry["path"]
        nb = nbformat.read(path, as_version=4)
        run = nb.metadata.get("course_run", {})
        if run.get("status") != "passed" or run.get("source_hash") != source_hash(nb):
            raise ValueError(f"Notebook needs a successful --write-back run: {entry['id']}")
        with tempfile.TemporaryDirectory(prefix="course-reading-check-") as directory:
            expected = Path(directory)
            export_reading(nb, path, root, expected, path.stem, None, relative_links=True)
            for generated in expected.rglob("*"):
                if generated.is_file():
                    saved = path.parent / generated.relative_to(expected)
                    if not saved.is_file() or saved.read_bytes() != generated.read_bytes():
                        raise ValueError(f"Missing or stale reading copy: {saved}; rerun with --write-back")


def execute_one(entry, root, output_dir, *, mode, timeout, write_back=False):
    path = root / "notebooks" / entry["path"]
    nb = nbformat.read(path, as_version=4)
    fingerprint = source_hash(nb)
    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
    nb.metadata["course_run"] = {"mode": mode, "source_hash": fingerprint}
    result = {"id": entry["id"], "status": "not_run", "mode": mode, "source_hash": fingerprint,
              "services": entry.get("services", []), "model_evidence": "scripted" if mode == "offline" else "provider"}
    env = kernel_environment(root, mode)
    try:
        with tempfile.TemporaryDirectory(prefix="course-notebook-") as directory:
            temporary = Path(directory)
            stage = temporary / "repository"
            stage.mkdir()
            stage_chapter(root, path, stage)
            kernels = temporary / "kernels"
            spec = kernels / "course"
            spec.mkdir(parents=True)
            (spec / "kernel.json").write_text(json.dumps({"argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"], "display_name": "Course project Python", "language": "python"}))
            env["COURSE_REPO_ROOT"] = str(stage)
            env["IPYTHONDIR"] = str(temporary / "ipython")
            env["JUPYTER_RUNTIME_DIR"] = str(temporary / "runtime")
            manager = AsyncKernelManager(kernel_name="course", kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernels)]))
            client = NotebookClient(nb, km=manager, timeout=timeout, resources={"metadata": {"path": str(stage)}})
            client.execute(env=env, cleanup_kc=True)
        result["status"] = "passed"
    except Exception as error:
        result.update(status="failed", error=type(error).__name__)
    # Never export credentials accidentally printed by a cell.
    rendered = json.dumps([c.get("outputs", []) for c in nb.cells])
    secrets = [v for k, v in env.items() if (k.endswith("API_KEY") or k.endswith("TOKEN")) and len(v) >= 8]
    if any(value in rendered for value in secrets):
        result.update(status="failed", error="Credential detected in output; artifacts withheld")
        return result
    nb.metadata.course_run["status"] = result["status"]
    nbformat.write(nb, output_dir / f"{entry['id']}.ipynb")
    export_reading(nb, path, root, output_dir, entry["id"], git_commit(root))
    if write_back and result["status"] == "passed":
        export_reading(nb, path, root, path.parent, path.stem, None, relative_links=True)
        nbformat.write(nb, path)
    return result


def run_entries(entries, root, output_dir, *, mode, timeout=180, write_back=False):
    root, output_dir = Path(root).resolve(), Path(output_dir).resolve()
    mode = selected_mode(mode)
    output_dir.mkdir(parents=True, exist_ok=True)
    # A new failure or not_run entry must not leave an earlier success beside its report.
    for entry in entries:
        for extension in ("ipynb", "html", "md"):
            (output_dir / f"{entry['id']}.{extension}").unlink(missing_ok=True)
    report = {"mode": mode, "source_commit": git_commit(root), "python": sys.version.split()[0],
              "executed_at": datetime.now(timezone.utc).isoformat(),
              "lock_hash": hashlib.sha256((root / "notebooks/uv.lock").read_bytes()).hexdigest() if (root / "notebooks/uv.lock").exists() else None,
              "results": [{"id": e["id"], "status": "not_run"} for e in entries]}
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for index, entry in enumerate(entries):
        report["results"][index] = execute_one(entry, root, output_dir, mode=mode, timeout=timeout, write_back=write_back)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        if report["results"][index]["status"] == "failed":
            break
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*", help="Catalog IDs; omit to run all")
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--check-reading", action="store_true", help="Check HTML/Markdown copies against saved notebooks without executing")
    parser.add_argument("--write-back", action="store_true", help="Save successful notebooks and sibling HTML/Markdown reading copies")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    root = repository_root()
    catalog = json.loads((root / "notebooks/catalog.json").read_text())
    entries = catalog["notebooks"]
    try:
        validate_catalog(root, entries)
        if args.ids:
            unknown = set(args.ids) - {e["id"] for e in entries}
            if unknown:
                raise ValueError("Unknown notebook IDs: " + ", ".join(sorted(unknown)))
            entries = [e for e in entries if e["id"] in args.ids]
        if args.check_reading:
            validate_reading(root, entries)
            print(f"Validated HTML/Markdown reading copies for {len(entries)} notebooks.")
            return 0
        if args.check_only:
            print(f"Validated {len(entries)} notebooks and local links.")
            return 0
        report = run_entries(entries, root, args.output_dir or root / "artifacts/notebooks", mode=args.mode, timeout=args.timeout, write_back=args.write_back)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    for result in report["results"]:
        print(f"{result['id']}: {result['status']} ({args.mode})")
    return 0 if all(r["status"] == "passed" for r in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
