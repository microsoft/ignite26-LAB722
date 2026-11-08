"""Export only lab-owned reactor source, focused tests and pinned public data."""
import argparse
from pathlib import Path
import shutil


def export(destination):
    root = Path(__file__).resolve().parents[1]
    destination = Path(destination).resolve()
    if destination.exists() or root not in destination.parents:
        raise ValueError("Choose a new, named build-context directory inside this repository.")
    files = [
        path for path in (root / "src" / "reactor").rglob("*")
        if path.is_file() and path.suffix in {".py", ".json", ".txt", ".html", ".css", ".svg"}
    ]
    files += [root / "src" / "reactor" / name for name in ("Containerfile", "HostedContainerfile", "AgentContainerfile")]
    files += [root / "src" / "runtime" / name for name in ("remote_runner.py", "frozen.py")]
    files += [root / "src" / "sandbox_process.py", root / "tests" / "test_hosted_workflow.py"]
    files += list((root / "tests").glob("test_reactor_*.py"))
    files += [
        root / "data" / "lab-datasets" / "caldova-public-lab-use-v2" / name
        for name in ("source-records.json", "data-manifest.json", "caldova-research.duckdb")
    ]
    for path in files:
        if path.is_symlink() or root not in path.resolve().parents:
            raise ValueError("Build context contains an unexpected linked source.")
    destination.mkdir(parents=True)
    for path in sorted(set(files)):
        target = destination / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    print(export(args.destination))
