# BanglaDoc Converter (`বাংলাডক কনভার্টার`)

A full-stack, Bangla-first PDF OCR, layout-preserving PDF reconstruction, and EPUB 3 digitization platform built with **Next.js + TypeScript + Tailwind CSS** and **Python FastAPI + PyMuPDF + OpenCV + Tesseract 5.5.3 LSTM + HarfBuzz (`uharfbuzz`) + EbookLib**.

---

## Key Capabilities

1. **Bangla & Mixed English OCR (`ben+eng`)**
   - Powered by **Tesseract 5.5.3 LSTM** with both `tessdata_best` (High Accuracy 300 DPI + adaptive contrast/deskew) and `tessdata_fast` (Standard Fast 210 DPI).
   - Recognizes Bangla vowels, consonants, Kar (`া, ি, ী, ু, ূ, ৃ, ে, ৈ, ো, ৌ`), Fola (`্য, র-ফলা, রেফ`), Hasanta (`্`), complex Juktakkhor (`ক্ষ, জ্ঞ, শ্র, স্ত্র, ন্দ, প্র, কেন্দ্র, শিক্ষার্থী`), Bangla numerals (`০১২৩৪৫৬৭৮৯`), and mixed English text & numerals (`0-9`).
   - Automatically detects native reliable Unicode PDF pages vs. scanned raster pages vs. broken legacy Bijoy/ANSI pages.

2. **Three Distinct PDF Reconstruction Modes**
   - **Searchable PDF (Highest Visual Fidelity)**: Preserves 100% of the original scanned page appearance and overlays a coordinate-locked invisible NFC Unicode text layer (`PDF Tr=3`) for exact `Ctrl+F` search and copy-paste into MS Word, Google Docs, and Notepad.
   - **Editable PDF (Vector Bangla Reconstruction)**: Reconstructs clean pages with HarfBuzz-shaped (`uharfbuzz` + `fontTools`) cubic Bézier Bangla typography, sampled foreground ink colors, vector table grids, cropped illustrations, and aligned NFC Unicode text.
   - **Layout-Preserved PDF (Hybrid Surgical Reconstruction)**: Retains original page borders, stamps, decorative headers, and table rules while surgically replacing scanned text regions with crisp vector Bangla glyphs.

3. **EPUB 3, DOCX & Plain Text Export**
   - **EPUB 3**: Supports both **Reflowable EPUB 3** and **Original-Layout Fixed EPUB 3** (`rendition:layout = pre-paginated`), complete with clickable Table of Contents (`nav.xhtml` + `toc.ncx`), HTML tables, illustrations, and embedded open-license Bangla TrueType fonts (`Hind Siliguri`, `Noto Sans Bengali`, `Noto Serif Bengali`, `Kalpurush`).
   - **DOCX**: Editable Microsoft Word export with Complex-Script (`w:cs`) Bangla font styling, headings, tables, and embedded figures.
   - **TXT & ZIP**: Clean UTF-8 NFC Unicode plain text and 1-click All-Formats ZIP bundle.

4. **Side-by-Side Comparison, Low-Confidence Highlighting & Manual OCR Correction**
   - Compare Original vs. Converted pages with synchronized zoom and page navigation.
   - Inspect low-confidence OCR regions (`< 75%`), edit any Bangla/English line or table cell inline, and click **Apply Corrections & Rebuild Outputs** to regenerate all formats without losing original layout coordinates.

---

## Quick Start

### Option A: One-Click Launcher (Windows)
Double-click `start-bangladoc.bat` in `d:\Ebooks`.

### Option B: Manual Terminal Startup

1. **Start Backend API (`http://127.0.0.1:8000`)**
   ```powershell
   cd d:\Ebooks\backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. **Start Frontend Web App (`http://localhost:3000`)**
   ```powershell
   cd d:\Ebooks\frontend
   npm.cmd run dev
   ```

Open **http://localhost:3000** in your browser. Click **"Try Sample Scanned Bangla PDF"** or drag-and-drop any scanned Bangla/English PDF to begin.
