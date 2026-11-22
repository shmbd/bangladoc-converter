from __future__ import annotations

import gc
import json
import os
import shutil
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fitz

from app.config import (
    DB_PATH,
    DEFAULT_RETENTION_HOURS,
    JOBS_DIR,
    SETTINGS_PATH,
    UPLOADS_DIR,
)
from app.models import (
    ConversionSettings,
    JobStatusResponse,
    LineEditItem,
    PageOCRResult,
    QAReport,
    SystemSettingsModel,
)
from app.services.bangla_text_utils import normalize_bangla_unicode, parse_page_range
from app.services.epub_generator import generate_epub3
from app.services.exporters import (
    create_all_formats_zip,
    generate_docx_export,
    generate_txt_export,
)
from app.services.ocr_pipeline import process_pdf_page
from app.services.pdf_reconstructor import (
    generate_editable_pdf,
    generate_layout_preserved_pdf,
    generate_searchable_pdf,
)
from app.services.qa_evaluator import evaluate_conversion_quality

_DB_LOCK = threading.Lock()
_WORKERS = 1 if os.environ.get("BANGLADOC_LOW_MEMORY") == "1" else 2
_EXECUTOR = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix="bangladoc_worker")
_CANCELLED_JOBS: set[str] = set()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_system_settings() -> SystemSettingsModel:
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return SystemSettingsModel(**data)
        except Exception:
            pass
    default = SystemSettingsModel(retention_hours=DEFAULT_RETENTION_HOURS)
    save_system_settings(default)
    return default


def save_system_settings(settings: SystemSettingsModel) -> SystemSettingsModel:
    SETTINGS_PATH.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    return settings


def init_db():
    with _DB_LOCK, sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                upload_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                page_count INTEGER NOT NULL,
                inspect_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                upload_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                stage_bn TEXT NOT NULL,
                progress_pct REAL NOT NULL,
                current_page INTEGER NOT NULL,
                total_pages INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                expires_at TEXT,
                error_message TEXT,
                settings_json TEXT NOT NULL,
                downloads_json TEXT NOT NULL,
                qa_json TEXT
            )
            """
        )
        conn.commit()


def save_upload_record(upload_id: str, filename: str, file_path: Path, size_bytes: int, page_count: int, inspect_json: str):
    with _DB_LOCK, sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO uploads
            (upload_id, filename, file_path, file_size_bytes, page_count, inspect_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (upload_id, filename, str(file_path), size_bytes, page_count, inspect_json, _utc_now_iso()),
        )
        conn.commit()


def get_upload_record(upload_id: str) -> dict | None:
    with _DB_LOCK, sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM uploads WHERE upload_id = ?", (upload_id,)).fetchone()
        return dict(row) if row else None


def _update_job_row(job_id: str, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields.keys())
    vals = list(fields.values()) + [job_id]
    with _DB_LOCK, sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(f"UPDATE jobs SET {cols} WHERE job_id = ?", vals)
        conn.commit()


def _row_to_job_response(row: dict) -> JobStatusResponse:
    settings = ConversionSettings(**json.loads(row["settings_json"]))
    downloads = json.loads(row["downloads_json"]) if row["downloads_json"] else {}
    qa = QAReport(**json.loads(row["qa_json"])) if row.get("qa_json") else None
    return JobStatusResponse(
        job_id=row["job_id"],
        upload_id=row["upload_id"],
        filename=row["filename"],
        status=row["status"],
        stage=row["stage"],
        stage_bn=row["stage_bn"],
        progress_pct=float(row["progress_pct"]),
        current_page=int(row["current_page"]),
        total_pages=int(row["total_pages"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        expires_at=row["expires_at"],
        error_message=row["error_message"],
        settings=settings,
        available_downloads=downloads,
        qa_report=qa,
    )


def get_job_status(job_id: str) -> JobStatusResponse | None:
    with _DB_LOCK, sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_job_response(dict(row)) if row else None


def list_jobs_history(limit: int = 50) -> list[JobStatusResponse]:
    with _DB_LOCK, sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_job_response(dict(r)) for r in rows]


def cancel_job(job_id: str) -> bool:
    _CANCELLED_JOBS.add(job_id)
    job = get_job_status(job_id)
    if not job:
        return False
    if job.status in ("queued", "processing"):
        _update_job_row(
            job_id,
            status="cancelled",
            stage="Cancelled by user",
            stage_bn="ব্যবহারকারী কর্তৃক বাতিল করা হয়েছে",
        )
    return True


def delete_job_and_files(job_id: str) -> bool:
    job = get_job_status(job_id)
    if not job:
        return False
    job_dir = JOBS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    with _DB_LOCK, sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        conn.commit()
    return True


def cleanup_expired_files() -> int:
    """Purge expired job directories and orphaned upload folders per retention setting."""
    sys_cfg = load_system_settings()
    if not sys_cfg.auto_cleanup_enabled:
        return 0
    now = datetime.now(timezone.utc)
    removed = 0
    with _DB_LOCK, sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT job_id, expires_at FROM jobs WHERE expires_at IS NOT NULL").fetchall()
        for r in rows:
            try:
                exp = datetime.fromisoformat(r["expires_at"])
                if now >= exp:
                    shutil.rmtree(JOBS_DIR / r["job_id"], ignore_errors=True)
                    conn.execute("DELETE FROM jobs WHERE job_id = ?", (r["job_id"],))
                    removed += 1
            except Exception:
                pass

        # Clean uploads older than retention_hours
        cutoff = now - timedelta(hours=max(1, sys_cfg.retention_hours))
        u_rows = conn.execute("SELECT upload_id, created_at FROM uploads").fetchall()
        for ur in u_rows:
            try:
                created = datetime.fromisoformat(ur["created_at"])
                if created <= cutoff:
                    shutil.rmtree(UPLOADS_DIR / ur["upload_id"], ignore_errors=True)
                    conn.execute("DELETE FROM uploads WHERE upload_id = ?", (ur["upload_id"],))
            except Exception:
                pass
        conn.commit()
    return removed


def _synthesize_all_outputs(
    job_id: str,
    source_pdf: Path,
    source_filename: str,
    ocr_pages: list[PageOCRResult],
    settings: ConversionSettings,
    job_dir: Path,
) -> tuple[dict[str, str], QAReport]:
    """Generate requested PDF modes, EPUB 3, TXT, DOCX, ZIP bundle, and QA evaluation."""
    out_dir = job_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(source_filename).stem

    fmt = settings.output_format
    build_all = fmt == "all"

    searchable_path: Path | None = None
    editable_path: Path | None = None
    layout_path: Path | None = None
    epub_path: Path | None = None

    # Always generate Searchable PDF if 'all' or 'searchable_pdf' (and also for Preview comparison!)
    searchable_path = out_dir / f"{stem}_searchable.pdf"
    generate_searchable_pdf(source_pdf, ocr_pages, settings, searchable_path)

    if build_all or fmt == "editable_pdf":
        editable_path = out_dir / f"{stem}_editable.pdf"
        generate_editable_pdf(ocr_pages, settings, job_dir, editable_path)

    if build_all or fmt == "layout_pdf":
        layout_path = out_dir / f"{stem}_layout_preserved.pdf"
        generate_layout_preserved_pdf(source_pdf, ocr_pages, settings, job_dir, layout_path)

    if build_all or fmt == "epub":
        epub_path = out_dir / f"{stem}.epub"
        generate_epub3(ocr_pages, settings, job_dir, source_filename, epub_path)

    txt_path = out_dir / f"{stem}_bangla_unicode.txt"
    generate_txt_export(ocr_pages, txt_path)

    docx_path = out_dir / f"{stem}_editable.docx"
    generate_docx_export(ocr_pages, settings, job_dir, docx_path)

    qa_report = evaluate_conversion_quality(
        source_pdf_path=source_pdf,
        ocr_pages=ocr_pages,
        searchable_pdf_path=searchable_path,
        layout_pdf_path=layout_path,
        editable_pdf_path=editable_path,
        job_dir=job_dir,
    )

    # Persist updated OCR JSON (with QA similarity scores) and QA report JSON
    (job_dir / "ocr_pages.json").write_text(
        json.dumps([p.model_dump() for p in ocr_pages], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    qa_json_path = out_dir / f"{stem}_qa_report.json"
    qa_json_path.write_text(qa_report.model_dump_json(indent=2), encoding="utf-8")

    # Build ZIP bundle of all generated artifacts
    pack_map: dict[str, Path] = {}
    downloads: dict[str, str] = {}

    if searchable_path and searchable_path.exists():
        pack_map[searchable_path.name] = searchable_path
        downloads["searchable_pdf"] = f"/api/jobs/{job_id}/download/searchable_pdf"
    if editable_path and editable_path.exists():
        pack_map[editable_path.name] = editable_path
        downloads["editable_pdf"] = f"/api/jobs/{job_id}/download/editable_pdf"
    if layout_path and layout_path.exists():
        pack_map[layout_path.name] = layout_path
        downloads["layout_pdf"] = f"/api/jobs/{job_id}/download/layout_pdf"
    if epub_path and epub_path.exists():
        pack_map[epub_path.name] = epub_path
        downloads["epub"] = f"/api/jobs/{job_id}/download/epub"
    if txt_path.exists():
        pack_map[txt_path.name] = txt_path
        downloads["txt"] = f"/api/jobs/{job_id}/download/txt"
    if docx_path.exists():
        pack_map[docx_path.name] = docx_path
        downloads["docx"] = f"/api/jobs/{job_id}/download/docx"
    pack_map[qa_json_path.name] = qa_json_path

    zip_path = out_dir / f"{stem}_all_formats.zip"
    create_all_formats_zip(pack_map, zip_path)
    downloads["zip"] = f"/api/jobs/{job_id}/download/zip"

    return downloads, qa_report


def _run_conversion_job(job_id: str, upload_rec: dict, settings: ConversionSettings):
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    source_pdf = Path(upload_rec["file_path"])
    filename = upload_rec["filename"]

    try:
        doc = fitz.open(str(source_pdf))
        selected_pages = parse_page_range(settings.page_range, doc.page_count)
        total_sel = len(selected_pages)

        _update_job_row(
            job_id,
            status="processing",
            stage=f"Analyzing document structure ({total_sel} page(s))...",
            stage_bn=f"নথির গঠন বিশ্লেষণ করা হচ্ছে ({total_sel} পৃষ্ঠা)...",
            progress_pct=5.0,
            total_pages=total_sel,
        )

        ocr_pages: list[PageOCRResult] = []
        for idx, page_num in enumerate(selected_pages, start=1):
            if job_id in _CANCELLED_JOBS:
                doc.close()
                return

            pct_start = 8.0 + ((idx - 1) / max(total_sel, 1)) * 64.0
            _update_job_row(
                job_id,
                stage=f"Performing Bangla+English OCR & layout detection on page {idx} of {total_sel} (Source p.{page_num})...",
                stage_bn=f"পৃষ্ঠা {idx}/{total_sel} (মূল পৃষ্ঠা {page_num})-এ বাংলা ও ইংরেজি ওসিআর এবং লেআউট শনাক্তকরণ চলছে...",
                progress_pct=round(pct_start, 1),
                current_page=idx,
            )

            page_res = process_pdf_page(
                doc=doc,
                page_number=page_num,
                output_page_index=idx,
                settings=settings,
                job_dir=job_dir,
            )
            ocr_pages.append(page_res)
            gc.collect()

        doc.close()

        if job_id in _CANCELLED_JOBS:
            return

        _update_job_row(
            job_id,
            stage="Reconstructing Searchable PDF, Vector Editable PDF, EPUB 3 & DOCX...",
            stage_bn="সার্চযোগ্য পিডিএফ, সম্পাদনাযোগ্য ভেক্টর পিডিএফ, ইপাব ৩ এবং ডকএক্স তৈরি হচ্ছে...",
            progress_pct=78.0,
        )

        # Save source subset PDF for exact side-by-side page comparison in Preview UI
        src_full = fitz.open(str(source_pdf))
        src_subset = fitz.open()
        for p_num in selected_pages:
            src_subset.insert_pdf(src_full, from_page=p_num - 1, to_page=p_num - 1)
        src_subset.save(str(job_dir / "source_selected.pdf"), garbage=2, deflate=True)
        src_subset.close()
        src_full.close()

        _update_job_row(
            job_id,
            stage="Evaluating Bangla Unicode integrity & visual layout similarity...",
            stage_bn="বাংলা ইউনিকোড অখণ্ডতা এবং মূল লেআউট সাদৃশ্য যাচাই করা হচ্ছে...",
            progress_pct=90.0,
        )

        downloads, qa_report = _synthesize_all_outputs(
            job_id=job_id,
            source_pdf=source_pdf,
            source_filename=filename,
            ocr_pages=ocr_pages,
            settings=settings,
            job_dir=job_dir,
        )

        sys_cfg = load_system_settings()
        exp_iso = (datetime.now(timezone.utc) + timedelta(hours=max(1, sys_cfg.retention_hours))).isoformat()

        _update_job_row(
            job_id,
            status="completed",
            stage="Conversion & QA verification complete",
            stage_bn="রূপান্তর এবং মান যাচাই সফলভাবে সম্পন্ন হয়েছে",
            progress_pct=100.0,
            current_page=total_sel,
            completed_at=_utc_now_iso(),
            expires_at=exp_iso,
            downloads_json=json.dumps(downloads),
            qa_json=qa_report.model_dump_json(),
        )
    except Exception as exc:
        _update_job_row(
            job_id,
            status="failed",
            stage="Conversion failed",
            stage_bn="রূপান্তর ব্যর্থ হয়েছে",
            error_message=str(exc),
        )


def enqueue_conversion_job(job_id: str, upload_rec: dict, settings: ConversionSettings) -> JobStatusResponse:
    total_est = len(parse_page_range(settings.page_range, int(upload_rec["page_count"])))
    now_iso = _utc_now_iso()
    with _DB_LOCK, sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            """
            INSERT INTO jobs
            (job_id, upload_id, filename, status, stage, stage_bn, progress_pct, current_page, total_pages,
             created_at, completed_at, expires_at, error_message, settings_json, downloads_json, qa_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, '{}', NULL)
            """,
            (
                job_id,
                upload_rec["upload_id"],
                upload_rec["filename"],
                "queued",
                "Queued for processing...",
                "প্রক্রিয়াকরণের সারিতে যুক্ত হয়েছে...",
                1.0,
                0,
                total_est,
                now_iso,
                settings.model_dump_json(),
            ),
        )
        conn.commit()

    _EXECUTOR.submit(_run_conversion_job, job_id, upload_rec, settings)
    return get_job_status(job_id)  # type: ignore[return-value]


def load_job_ocr_pages(job_id: str) -> list[PageOCRResult]:
    ocr_file = JOBS_DIR / job_id / "ocr_pages.json"
    if not ocr_file.exists():
        return []
    raw = json.loads(ocr_file.read_text(encoding="utf-8"))
    return [PageOCRResult(**item) for item in raw]


def apply_manual_edits_and_rebuild(job_id: str, edits: list[LineEditItem]) -> JobStatusResponse:
    """Apply user's manual Bangla/English OCR corrections and rebuild all output formats cleanly."""
    job = get_job_status(job_id)
    if not job:
        raise ValueError("Job not found.")
    upload_rec = get_upload_record(job.upload_id)
    if not upload_rec:
        raise ValueError("Original uploaded PDF no longer available.")

    ocr_pages = load_job_ocr_pages(job_id)
    if not ocr_pages:
        raise ValueError("OCR structure not found for this job.")

    edit_lookup: dict[tuple[int, str], str] = {
        (e.page_number, e.line_id): normalize_bangla_unicode(e.new_text) for e in edits
    }

    updated_any = False
    for p_res in ocr_pages:
        for blk in p_res.blocks:
            for ln in blk.lines:
                key = (p_res.page_number, ln.id)
                if key in edit_lookup:
                    ln.text = edit_lookup[key]
                    ln.confidence = 100.0
                    # Clear stale word boxes if token count changed so reconstructor distributes cleanly across line.bbox
                    toks = [t for t in ln.text.split(" ") if t]
                    if len(toks) != len(ln.words):
                        ln.words = []
                    else:
                        for w_obj, tok in zip(ln.words, toks):
                            w_obj.text = tok
                            w_obj.confidence = 100.0
                    updated_any = True

        # Also support editing table cells via id = "{table_id}_r{row}_c{col}"
        for tbl in p_res.tables:
            for cell in tbl.cells:
                ckey = (p_res.page_number, f"{tbl.id}_r{cell.row}_c{cell.col}")
                if ckey in edit_lookup:
                    cell.text = edit_lookup[ckey]
                    cell.confidence = 100.0
                    updated_any = True

        # Recompute page low-confidence count
        low_cnt = 0
        confs: list[float] = []
        for blk in p_res.blocks:
            for ln in blk.lines:
                if ln.words:
                    for w in ln.words:
                        confs.append(w.confidence)
                        if w.confidence < 70.0:
                            low_cnt += 1
                else:
                    confs.append(ln.confidence)
        p_res.low_confidence_word_count = low_cnt
        if confs:
            p_res.mean_confidence = round(sum(confs) / len(confs), 1)

    if updated_any:
        # Ensure all 3 PDF modes + EPUB + DOCX + TXT are rebuilt when user saves edits
        rebuild_settings = job.settings.model_copy()
        downloads, qa_report = _synthesize_all_outputs(
            job_id=job_id,
            source_pdf=Path(upload_rec["file_path"]),
            source_filename=job.filename,
            ocr_pages=ocr_pages,
            settings=rebuild_settings,
            job_dir=JOBS_DIR / job_id,
        )
        _update_job_row(
            job_id,
            stage="Manual corrections applied & documents rebuilt",
            stage_bn="ম্যানুয়াল সংশোধন প্রয়োগ এবং নথি পুনর্গঠিত হয়েছে",
            downloads_json=json.dumps(downloads),
            qa_json=qa_report.model_dump_json(),
        )

    return get_job_status(job_id)  # type: ignore[return-value]
