"""Install the pinned author release, without executing downloaded code."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent
CONCEPT_DOI = "10.5281/zenodo.14171745"
VERSION_DOI = "10.5281/zenodo.14171746"
RECORD_ID = "14171746"
API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
DEFAULT_VENDOR = PROJECT_ROOT / "vendor" / "zenodo_14171745"
ARCHIVE_NAME = "Intersection-Conflict-Detection-v1.0.0.zip"
EXPECTED_MD5 = "c51e921f9273d26fc9f9f08a0b4ef541"


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "traffic-llm-replication/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def install(vendor: Path = DEFAULT_VENDOR, archive: Path | None = None) -> dict:
    vendor = vendor.resolve()
    if (vendor / "manifest.json").exists():
        raise RuntimeError("A release is already installed. Use a separate --vendor-dir to preserve it.")
    record = json.loads(_download(API_URL))
    if record.get("doi") != VERSION_DOI or record.get("conceptdoi") != CONCEPT_DOI:
        raise ValueError("Zenodo version/concept DOI does not match the pinned author release.")
    entry, = record["files"]
    url = entry["links"].get("content") or entry["links"]["self"]
    content = archive.read_bytes() if archive else _download(url)
    checksum = hashlib.md5(content).hexdigest()
    if checksum != EXPECTED_MD5 or entry.get("checksum") != "md5:" + checksum:
        raise ValueError("Archive checksum differs from the pinned author release.")
    extracted = vendor / "extracted"
    with zipfile.ZipFile(io.BytesIO(content)) as bundle:
        for member in bundle.infolist():
            target = (extracted / member.filename).resolve()
            if not target.is_relative_to(extracted.resolve()):
                raise ValueError(f"Archive path escapes destination: {member.filename}")
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archive symbolic links are not supported.")
        if extracted.exists() and any(extracted.iterdir()):
            raise RuntimeError("Extraction directory is not empty; refusing to mix source versions.")
        extracted.mkdir(parents=True, exist_ok=True)
        bundle.extractall(extracted)
    raw = vendor / "raw"
    raw.mkdir(exist_ok=True)
    (raw / ARCHIVE_NAME).write_bytes(content)
    hashes = {
        path.relative_to(extracted).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(extracted.rglob("*")) if path.is_file()
    }
    manifest = {
        "concept_doi": CONCEPT_DOI, "version_doi": VERSION_DOI,
        "record_id": RECORD_ID, "version": "v1.0.0", "api_url": API_URL,
        "source_repository": "https://github.com/sarimasri3/Intersection-Conflict-Detection/tree/v1.0.0",
        "installed_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive": {"name": ARCHIVE_NAME, "download_url": url, "size": len(content),
                    "md5": checksum, "sha256": hashlib.sha256(content).hexdigest()},
        "extracted_sha256": hashes,
        "author_files_modified": False,
    }
    (vendor / "record_metadata.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    (vendor / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vendor-dir", type=Path, default=DEFAULT_VENDOR)
    ap.add_argument("--archive", type=Path, help="Optional local copy; checked against the pinned checksum.")
    args = ap.parse_args()
    manifest = install(args.vendor_dir, args.archive)
    print(f"Installed {manifest['version_doi']}: {len(manifest['extracted_sha256'])} verified files.")


if __name__ == "__main__":
    main()
