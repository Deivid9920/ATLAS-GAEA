"""Canonical JSON helpers shared by every hash in the repo.

One rule (m-02 of the master spec): ensure_ascii=False + sort_keys=True
+ compact separators on ALL canonicalizations (audit chain, config
sha256, suite digest, prereg hashes, fingerprints). Two hash sites that
disagree on serialization produce two truths that diverge in silence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256_canonical(obj) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def config_sha256(path: str | Path) -> str:
    """Hash of config.yaml canonicalized through yaml->json round trip.

    The runner recomputes this on every start and refuses to run when it
    differs from the value chained in the audit log without a registered
    amendment.
    """
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return sha256_canonical(data)
