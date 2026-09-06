#!/usr/bin/env python3
from __future__ import annotations
import argparse, gzip, hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path
from huggingface_hub import HfApi

TYPE_SPECS = (
    ("model", "m", "list_models"),
    ("dataset", "d", "list_datasets"),
    ("space", "s", "list_spaces"),
)

def write_chunk(output_dir: Path, chunk_index: int, rows: list[str]) -> dict:
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    name = f"{chunk_index:06d}.txt.gz"
    path = data_dir / name
    raw = ("\n".join(rows) + "\n").encode("utf-8")
    with gzip.GzipFile(filename=str(path), mode="wb", compresslevel=9, mtime=0) as f:
        f.write(raw)
    return {
        "file": f"data/{name}",
        "count": len(rows),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "compressed_bytes": path.stat().st_size,
    }

def build(output_dir: Path, web_html: Path, chunk_size: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    (output_dir / "manifest.json").unlink(missing_ok=True)
    shutil.copy2(web_html, output_dir / "index.html")

    api = HfApi(token=False)
    chunks, current = [], []
    counts = {"model": 0, "dataset": 0, "space": 0}
    total = 0

    for kind, prefix, method_name in TYPE_SPECS:
        print(f"Enumerating {kind}s...")
        for info in getattr(api, method_name)(limit=None):
            current.append(f"{prefix}\t{info.id}")
            counts[kind] += 1
            total += 1
            if len(current) == chunk_size:
                chunks.append(write_chunk(output_dir, len(chunks), current))
                current = []
                if len(chunks) % 10 == 0:
                    print(f"Indexed {total:,} repos...")

    if current:
        chunks.append(write_chunk(output_dir, len(chunks), current))

    manifest = {
        "format": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_repos": total,
        "counts": counts,
        "chunk_size": chunk_size,
        "chunks": chunks,
        "randomness": "Web Crypto getRandomValues with rejection sampling",
        "scope": "All repositories anonymously visible via Hugging Face Hub during this build."
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Done: {total:,} repositories")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=Path("site"))
    p.add_argument("--web-html", type=Path, default=Path("web/index.html"))
    p.add_argument("--chunk-size", type=int, default=25000)
    a = p.parse_args()
    build(a.output, a.web_html, a.chunk_size)

if __name__ == "__main__":
    main()
