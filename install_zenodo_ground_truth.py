"""Download and safely unpack the authors' Zenodo record 14171745.

This installer uses Zenodo's public Records API. It downloads files but NEVER
executes code from the record. After installation, run
``python inspect_zenodo_ground_truth.py`` and map the actual author entry point
in ``official_adapter_config.json``.

The downloader is intentionally robust to both legacy and current Zenodo record
JSON shapes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

import requests

RECORD_ID = "14171745"
EXPECTED_DOI = "10.5281/zenodo.14171745"
API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
DEFAULT_VENDOR = Path("vendor") / f"zenodo_{RECORD_ID}"


class InstallError(RuntimeError):
    pass


def _safe_target(root: Path, name: str) -> Path:
    root = root.resolve()
    target = (root / name).resolve()
    if root != target and root not in target.parents:
        raise InstallError(f"Unsafe archive path rejected: {name}")
    return target


def _extract_archive(path: Path, destination: Path) -> list[str]:
    extracted: list[str] = []
    destination.mkdir(parents=True, exist_ok=True)

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                _safe_target(destination, info.filename)
            zf.extractall(destination)
            extracted.extend(i.filename for i in zf.infolist() if not i.is_dir())
        return extracted

    try:
        is_tar = tarfile.is_tarfile(path)
    except OSError:
        is_tar = False
    if is_tar:
        with tarfile.open(path) as tf:
            for member in tf.getmembers():
                _safe_target(destination, member.name)
            tf.extractall(destination, filter="data")
            extracted.extend(m.name for m in tf.getmembers() if m.isfile())
    return extracted


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _md5(path: Path) -> str:
    h = hashlib.md5()  # nosec - checksum verification only, not security use
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_file_entries(record: dict[str, Any]) -> Iterable[dict[str, Any]]:
    files = record.get("files", [])
    # Newer InvenioRDM representation: files.entries is a mapping.
    if isinstance(files, dict):
        entries = files.get("entries", {})
        if isinstance(entries, dict):
            for key, value in entries.items():
                e = dict(value or {})
                e.setdefault("key", key)
                yield e
            return
        if isinstance(entries, list):
            yield from entries
            return
    # Legacy Zenodo representation: files is a list.
    if isinstance(files, list):
        yield from files


def _filename(entry: dict[str, Any]) -> str:
    raw = entry.get("key") or entry.get("filename") or entry.get("name")
    if not raw:
        raise InstallError(f"Zenodo file entry has no filename: {entry}")
    return Path(str(raw)).name


def _download_url(entry: dict[str, Any]) -> str:
    links = entry.get("links") or {}
    for key in ("content", "download", "self"):
        value = links.get(key)
        if value:
            return str(value)
    # Some metadata exports expose a direct URL under ``url``.
    if entry.get("url"):
        return str(entry["url"])
    raise InstallError(f"No downloadable URL in Zenodo file entry: {entry}")


def _record_dois(record: dict[str, Any]) -> set[str]:
    candidates = {
        str(record.get("doi") or ""),
        str((record.get("metadata") or {}).get("doi") or ""),
        str((record.get("pids") or {}).get("doi", {}).get("identifier") or ""),
    }
    return {x.lower().replace("https://doi.org/", "") for x in candidates if x}


def fetch_record(session: requests.Session) -> dict[str, Any]:
    response = session.get(API_URL, timeout=60)
    response.raise_for_status()
    record = response.json()
    dois = _record_dois(record)
    if dois and EXPECTED_DOI.lower() not in dois:
        raise InstallError(
            "Zenodo record DOI verification failed. "
            f"Expected {EXPECTED_DOI}, got {sorted(dois)}"
        )
    return record


def download_record(record: dict[str, Any], vendor: Path, session: requests.Session) -> dict[str, Any]:
    raw_dir = vendor / "raw"
    extracted_dir = vendor / "extracted"
    raw_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "record_id": RECORD_ID,
        "expected_doi": EXPECTED_DOI,
        "record_title": (record.get("metadata") or {}).get("title") or record.get("title"),
        "record_created": record.get("created"),
        "record_modified": record.get("modified") or record.get("updated"),
        "files": [],
    }

    entries = list(_normalize_file_entries(record))
    if not entries:
        raise InstallError("Zenodo record metadata contains no downloadable files.")

    for entry in entries:
        name = _filename(entry)
        url = _download_url(entry)
        target = raw_dir / name
        print(f"Downloading {name} ...")
        with session.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            with target.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)

        checksum = str(entry.get("checksum") or "")
        if checksum.lower().startswith("md5:"):
            expected = checksum.split(":", 1)[1].lower()
            actual = _md5(target)
            if actual != expected:
                raise InstallError(f"Checksum mismatch for {name}: expected md5:{expected}, got md5:{actual}")

        extracted = _extract_archive(target, extracted_dir / target.stem)
        manifest["files"].append(
            {
                "name": name,
                "size": target.stat().st_size,
                "zenodo_checksum": checksum or None,
                "sha256": _sha256(target),
                "download_url": url,
                "extracted_files": extracted,
            }
        )

    (vendor / "record_metadata.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (vendor / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def install_local_archive(archive: Path, vendor: Path) -> dict[str, Any]:
    if not archive.exists():
        raise InstallError(f"Archive not found: {archive}")
    raw_dir = vendor / "raw"
    extracted_dir = vendor / "extracted" / archive.stem
    raw_dir.mkdir(parents=True, exist_ok=True)
    copied = raw_dir / archive.name
    if archive.resolve() != copied.resolve():
        shutil.copy2(archive, copied)
    extracted = _extract_archive(copied, extracted_dir)
    manifest = {
        "record_id": RECORD_ID,
        "expected_doi": EXPECTED_DOI,
        "source": "user_supplied_archive",
        "files": [{
            "name": copied.name,
            "size": copied.stat().st_size,
            "sha256": _sha256(copied),
            "extracted_files": extracted,
        }],
    }
    (vendor / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Install authors' Zenodo record 14171745 without executing it.")
    ap.add_argument("--vendor-dir", default=str(DEFAULT_VENDOR))
    ap.add_argument(
        "--archive",
        help="Optional manually downloaded Zenodo archive/file. Useful if API access is blocked.",
    )
    ap.add_argument("--force", action="store_true", help="Replace an existing vendor directory.")
    args = ap.parse_args()

    vendor = Path(args.vendor_dir)
    if vendor.exists() and args.force:
        shutil.rmtree(vendor)
    vendor.mkdir(parents=True, exist_ok=True)

    try:
        if args.archive:
            manifest = install_local_archive(Path(args.archive), vendor)
        else:
            session = requests.Session()
            session.headers.update({"User-Agent": "traffic-llm-replication/zenodo-installer"})
            record = fetch_record(session)
            manifest = download_record(record, vendor, session)
    except (requests.RequestException, InstallError) as exc:
        raise SystemExit(
            "Zenodo installation failed:\n"
            f"  {exc}\n\n"
            "Open https://doi.org/10.5281/zenodo.14171745 in your browser, download the record, "
            "then retry with:\n"
            "  python install_zenodo_ground_truth.py --archive <downloaded-file> --force"
        ) from exc

    print(f"\nInstalled Zenodo material under: {vendor}")
    print(f"Files recorded in manifest: {len(manifest.get('files', []))}")
    print("Next: python inspect_zenodo_ground_truth.py")
    print("Then map the authors' actual entry point in official_adapter_config.json.")


if __name__ == "__main__":
    main()
