from __future__ import annotations

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = Path(os.environ.get("BANGLADOC_STORAGE_DIR", str(BASE_DIR / "storage")))
UPLOADS_DIR = STORAGE_DIR / "uploads"
JOBS_DIR = STORAGE_DIR / "jobs"
SAMPLES_DIR = STORAGE_DIR / "samples"
DB_PATH = STORAGE_DIR / "bangladoc.sqlite3"
SETTINGS_PATH = STORAGE_DIR / "system_settings.json"

FONTS_DIR = BASE_DIR / "assets" / "fonts"
VENDOR_DIR = BASE_DIR / "vendor"

for _d in (STORAGE_DIR, UPLOADS_DIR, JOBS_DIR, SAMPLES_DIR, FONTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def resolve_tesseract_cmd() -> str:
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and Path(env_cmd).exists():
        return env_cmd
    vendor_exe = VENDOR_DIR / "tesseract" / "tesseract.exe"
    if vendor_exe.exists():
        return str(vendor_exe)
    sys_cmd = shutil.which("tesseract")
    if sys_cmd:
        return sys_cmd
    win_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if win_default.exists():
        return str(win_default)
    return "tesseract"


TESSERACT_CMD = resolve_tesseract_cmd()
TESSDATA_BEST_DIR = VENDOR_DIR / "tessdata_best"
TESSDATA_FAST_DIR = VENDOR_DIR / "tessdata_fast"

AVAILABLE_FONTS: dict[str, dict[str, str]] = {
    "hind_siliguri": {
        "id": "hind_siliguri",
        "label": "Hind Siliguri (Modern Sans)",
        "regular": str(FONTS_DIR / "HindSiliguri-Regular.ttf"),
        "bold": str(FONTS_DIR / "HindSiliguri-Bold.ttf"),
        "license": "SIL Open Font License 1.1",
    },
    "noto_sans_bengali": {
        "id": "noto_sans_bengali",
        "label": "Noto Sans Bengali (Clean UI & Print)",
        "regular": str(FONTS_DIR / "NotoSansBengali-Regular.ttf"),
        "bold": str(FONTS_DIR / "HindSiliguri-Bold.ttf"),
        "license": "SIL Open Font License 1.1",
    },
    "noto_serif_bengali": {
        "id": "noto_serif_bengali",
        "label": "Noto Serif Bengali (Book & Literary)",
        "regular": str(FONTS_DIR / "NotoSerifBengali-Regular.ttf"),
        "bold": str(FONTS_DIR / "NotoSerifBengali-Regular.ttf"),
        "license": "SIL Open Font License 1.1",
    },
    "kalpurush": {
        "id": "kalpurush",
        "label": "Kalpurush (Classic Bangla Typography)",
        "regular": str(
            FONTS_DIR / "Kalpurush-Regular.ttf"
            if (FONTS_DIR / "Kalpurush-Regular.ttf").exists()
            else FONTS_DIR / "HindSiliguri-Regular.ttf"
        ),
        "bold": str(FONTS_DIR / "HindSiliguri-Bold.ttf"),
        "license": "Free Open Bangla Font (OmicronLab)",
    },
}

MAX_UPLOAD_SIZE_MB = 150
DEFAULT_RETENTION_HOURS = 24
