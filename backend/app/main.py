from __future__ import annotations

import asyncio
import shutil
import subprocess
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import fitz
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from app.config import (
    AVAILABLE_FONTS,
    JOBS_DIR,
    MAX_UPLOAD_SIZE_MB,
    TESSDATA_BEST_DIR,
    TESSDATA_FAST_DIR,
    TESSERACT_CMD,
    UPLOADS_DIR,
)
from app.models import (
    JobStatusResponse,
    ManualCorrectionRequest,
    PageOCRResult,
    StartConversionRequest,
    SystemSettingsModel,
    UploadInspectResponse,
)
from app.services.job_manager import (
    apply_manual_edits_and_rebuild,
    cancel_job,
    cleanup_expired_files,
    delete_job_and_files,
    enqueue_conversion_job,
    get_job_status,
    get_upload_record,
    init_db,
    list_jobs_history,
    load_job_ocr_pages,
    load_system_settings,
    save_system_settings,
    save_upload_record,
)
from app.services.pdf_analyzer import PDFValidationError, inspect_uploaded_pdf
from app.services.sample_generator import ensure_sample_scanned_bangla_pdf


async def _periodic_cleanup_loop():
    while True:
        try:
            cleanup_expired_files()
        except Exception:
            pass
        await asyncio.sleep(600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    cleanup_task = asyncio.create_task(_periodic_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()


app = FastAPI(
    title="BanglaDoc Converter API",
    description="Bangla-first PDF OCR, Hybrid Layout Reconstruction & EPUB 3 Digitization Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/")
def root_status():
    return {
        "service": "BanglaDoc Converter API",
        "status": "running",
        "docs_url": "/docs",
        "health_url": "/api/health",
    }


def _safe_download_headers(filename: str, inline: bool = False) -> dict[str, str]:
    ascii_fallback = "".join(ch if ord(ch) < 128 and ch not in '"\\/' else "_" for ch in filename)
    encoded = quote(filename)
    disp_type = "inline" if inline else "attachment"
    return {
        "Content-Disposition": f"{disp_type}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}",
        "Cache-Control": "no-store",
    }


@app.get("/api/health")
def health_check():
    tess_ok = Path(TESSERACT_CMD).exists() or bool(shutil.which(TESSERACT_CMD))
    tess_ver = "unavailable"
    if tess_ok:
        try:
            out = subprocess.check_output([TESSERACT_CMD, "--version"], stderr=subprocess.STDOUT, timeout=5)
            tess_ver = out.decode("utf-8", errors="replace").splitlines()[0].strip()
        except Exception:
            pass

    return {
        "status": "healthy",
        "tesseract_available": tess_ok,
        "tesseract_version": tess_ver,
        "bangla_best_model": (TESSDATA_BEST_DIR / "ben.traineddata").exists(),
        "bangla_fast_model": (TESSDATA_FAST_DIR / "ben.traineddata").exists(),
        "fonts": [
            {"id": k, "label": v["label"], "license": v["license"]}
            for k, v in AVAILABLE_FONTS.items()
        ],
        "privacy": {
            "ai_training": False,
            "public_exposure": False,
            "retention_hours": load_system_settings().retention_hours,
        },
    }


@app.post("/api/uploads", response_model=UploadInspectResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF (.pdf) documents are supported.")

    upload_id = uuid.uuid4().hex[:12]
    up_dir = UPLOADS_DIR / upload_id
    up_dir.mkdir(parents=True, exist_ok=True)
    dest_pdf = up_dir / "source.pdf"

    size_bytes = 0
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    try:
        with dest_pdf.open("wb") as out_f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed upload size of {MAX_UPLOAD_SIZE_MB} MB.",
                    )
                out_f.write(chunk)

        inspect_res = inspect_uploaded_pdf(
            pdf_path=dest_pdf,
            upload_id=upload_id,
            original_filename=file.filename,
            thumbs_dir=up_dir / "thumbs",
        )
        save_upload_record(
            upload_id=upload_id,
            filename=file.filename,
            file_path=dest_pdf,
            size_bytes=size_bytes,
            page_count=inspect_res.page_count,
            inspect_json=inspect_res.model_dump_json(),
        )
        return inspect_res
    except PDFValidationError as pve:
        shutil.rmtree(up_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=pve.message) from pve
    except HTTPException:
        shutil.rmtree(up_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(up_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {exc}") from exc


@app.post("/api/samples/load", response_model=UploadInspectResponse)
def load_builtin_sample():
    sample_path = ensure_sample_scanned_bangla_pdf()
    upload_id = f"sample_{uuid.uuid4().hex[:8]}"
    up_dir = UPLOADS_DIR / upload_id
    up_dir.mkdir(parents=True, exist_ok=True)
    dest_pdf = up_dir / "source.pdf"
    shutil.copy2(sample_path, dest_pdf)

    filename = "জাতীয়_বাংলা_গবেষণা_প্রতিবেদন_Scanned.pdf"
    inspect_res = inspect_uploaded_pdf(
        pdf_path=dest_pdf,
        upload_id=upload_id,
        original_filename=filename,
        thumbs_dir=up_dir / "thumbs",
    )
    save_upload_record(
        upload_id=upload_id,
        filename=filename,
        file_path=dest_pdf,
        size_bytes=dest_pdf.stat().st_size,
        page_count=inspect_res.page_count,
        inspect_json=inspect_res.model_dump_json(),
    )
    return inspect_res


@app.get("/api/uploads/{upload_id}/pages/{page_number}/thumbnail")
def get_upload_page_thumbnail(upload_id: str, page_number: int):
    rec = get_upload_record(upload_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Upload not found.")
    up_dir = UPLOADS_DIR / upload_id
    thumb_path = up_dir / "thumbs" / f"thumb_{page_number}.png"
    if not thumb_path.exists():
        pdf_path = Path(rec["file_path"])
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="Source PDF missing.")
        doc = fitz.open(str(pdf_path))
        try:
            if page_number < 1 or page_number > doc.page_count:
                raise HTTPException(status_code=404, detail="Page out of range.")
            page = doc[page_number - 1]
            scale = min(1.0, 260.0 / max(page.rect.width, 1.0))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            pix.save(str(thumb_path))
        finally:
            doc.close()
    return FileResponse(str(thumb_path), media_type="image/png")


@app.get("/api/uploads/{upload_id}/pdf")
def get_uploaded_source_pdf(upload_id: str):
    rec = get_upload_record(upload_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Upload not found.")
    pdf_path = Path(rec["file_path"])
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Source PDF missing.")
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        headers=_safe_download_headers(rec["filename"], inline=True),
    )


@app.post("/api/jobs", response_model=JobStatusResponse)
def start_conversion(req: StartConversionRequest):
    rec = get_upload_record(req.upload_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Upload session not found or expired.")
    job_id = uuid.uuid4().hex[:12]
    return enqueue_conversion_job(job_id=job_id, upload_rec=rec, settings=req.settings)


@app.get("/api/jobs", response_model=list[JobStatusResponse])
def get_jobs_list(limit: int = Query(default=40, ge=1, le=100)):
    return list_jobs_history(limit=limit)


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_single_job(job_id: str):
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Conversion job not found.")
    return job


@app.get("/api/jobs/{job_id}/ocr", response_model=list[PageOCRResult])
def get_job_ocr_structure(job_id: str):
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return load_job_ocr_pages(job_id)


@app.post("/api/jobs/{job_id}/edits", response_model=JobStatusResponse)
def save_manual_ocr_edits(job_id: str, payload: ManualCorrectionRequest):
    try:
        return apply_manual_edits_and_rebuild(job_id=job_id, edits=payload.edits)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve)) from ve
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to rebuild outputs: {exc}") from exc


@app.post("/api/jobs/{job_id}/cancel")
def cancel_running_job(job_id: str):
    if not cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"cancelled": True}


@app.delete("/api/jobs/{job_id}")
def delete_job_endpoint(job_id: str):
    if not delete_job_and_files(job_id):
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"deleted": True}


def _resolve_job_pdf_variant(job_id: str, variant: str) -> Path:
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job_dir = JOBS_DIR / job_id
    stem = Path(job.filename).stem
    out_dir = job_dir / "outputs"

    if variant == "source":
        sel = job_dir / "source_selected.pdf"
        if sel.exists():
            return sel
        rec = get_upload_record(job.upload_id)
        if rec and Path(rec["file_path"]).exists():
            return Path(rec["file_path"])
        raise HTTPException(status_code=404, detail="Source PDF not found.")

    mapping = {
        "searchable_pdf": out_dir / f"{stem}_searchable.pdf",
        "editable_pdf": out_dir / f"{stem}_editable.pdf",
        "layout_pdf": out_dir / f"{stem}_layout_preserved.pdf",
    }
    target = mapping.get(variant)
    if not target or not target.exists():
        # Fallback to searchable_pdf if requested variant wasn't generated yet
        fallback = out_dir / f"{stem}_searchable.pdf"
        if fallback.exists():
            return fallback
        raise HTTPException(status_code=404, detail=f"PDF variant '{variant}' is not available for this job.")
    return target


@app.get("/api/jobs/{job_id}/preview/{variant}")
def preview_job_pdf(job_id: str, variant: str):
    pdf_path = _resolve_job_pdf_variant(job_id, variant)
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        headers=_safe_download_headers(pdf_path.name, inline=True),
    )


@app.get("/api/jobs/{job_id}/pages/{output_index}/render/{variant}")
def render_job_page_image(
    job_id: str,
    output_index: int,
    variant: str,
    dpi: int = Query(default=150, ge=72, le=300),
):
    """Render 1-indexed converted/source page to crisp PNG (or serve QA visual diff heatmap)."""
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    if variant == "diff":
        ocr_pages = load_job_ocr_pages(job_id)
        if 1 <= output_index <= len(ocr_pages):
            src_pnum = ocr_pages[output_index - 1].page_number
            diff_img = JOBS_DIR / job_id / "qa_diffs" / f"diff_p{src_pnum}.png"
            if diff_img.exists():
                return FileResponse(str(diff_img), media_type="image/png", headers={"Cache-Control": "no-store"})

    pdf_path = _resolve_job_pdf_variant(job_id, variant if variant != "diff" else "searchable_pdf")
    doc = fitz.open(str(pdf_path))
    try:
        if output_index < 1 or output_index > doc.page_count:
            raise HTTPException(status_code=404, detail="Page index out of range.")
        pix = doc[output_index - 1].get_pixmap(dpi=dpi, alpha=False)
        png_bytes = pix.tobytes("png")
        return Response(content=png_bytes, media_type="image/png", headers={"Cache-Control": "no-store"})
    finally:
        doc.close()


@app.get("/api/jobs/{job_id}/download/{fmt}")
def download_converted_file(job_id: str, fmt: str):
    job = get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    stem = Path(job.filename).stem
    out_dir = JOBS_DIR / job_id / "outputs"

    file_specs: dict[str, tuple[Path, str]] = {
        "searchable_pdf": (out_dir / f"{stem}_searchable.pdf", "application/pdf"),
        "editable_pdf": (out_dir / f"{stem}_editable.pdf", "application/pdf"),
        "layout_pdf": (out_dir / f"{stem}_layout_preserved.pdf", "application/pdf"),
        "epub": (out_dir / f"{stem}.epub", "application/epub+zip"),
        "txt": (out_dir / f"{stem}_bangla_unicode.txt", "text/plain; charset=utf-8"),
        "docx": (
            out_dir / f"{stem}_editable.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        "zip": (out_dir / f"{stem}_all_formats.zip", "application/zip"),
    }

    if fmt not in file_specs:
        raise HTTPException(status_code=400, detail=f"Unsupported download format: {fmt}")

    target_path, media_type = file_specs[fmt]
    if not target_path.exists():
        # Lazy on-demand synthesis if user initially converted single format and now requests another!
        rec = get_upload_record(job.upload_id)
        ocr_pages = load_job_ocr_pages(job_id)
        if rec and ocr_pages and Path(rec["file_path"]).exists():
            from app.services.job_manager import _synthesize_all_outputs

            all_cfg = job.settings.model_copy(update={"output_format": "all"})
            _synthesize_all_outputs(
                job_id=job_id,
                source_pdf=Path(rec["file_path"]),
                source_filename=job.filename,
                ocr_pages=ocr_pages,
                settings=all_cfg,
                job_dir=JOBS_DIR / job_id,
            )

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Requested output file not found.")

    return FileResponse(
        str(target_path),
        media_type=media_type,
        headers=_safe_download_headers(target_path.name, inline=False),
    )


@app.get("/api/settings", response_model=SystemSettingsModel)
def get_settings():
    return load_system_settings()


@app.put("/api/settings", response_model=SystemSettingsModel)
def update_settings(payload: SystemSettingsModel):
    return save_system_settings(payload)


@app.post("/api/settings/cleanup")
def run_manual_cleanup():
    removed = cleanup_expired_files()
    return {"removed_jobs": removed}
