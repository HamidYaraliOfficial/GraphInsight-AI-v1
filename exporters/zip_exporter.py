"""ZIP bundling of exported files."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path


def make_zip(files: dict[str, str], zip_path: Path, extra_text: dict[str, str] | None = None) -> str:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = dict(created=datetime.now().isoformat(timespec="seconds"), generator="GraphInsight AI",
                    files=sorted(Path(p).name for p in files.values()))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for label, p in files.items():
            pp = Path(p)
            if pp.exists():
                z.write(pp, arcname=pp.name)
        for name, txt in (extra_text or {}).items():
            z.writestr(name, txt)
        z.writestr("manifest.json", json.dumps(manifest, indent=1))
    return str(zip_path)
