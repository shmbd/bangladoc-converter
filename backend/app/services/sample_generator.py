from __future__ import annotations

from pathlib import Path

import cv2
import fitz
import numpy as np

from app.config import SAMPLES_DIR
from app.services.harfbuzz_renderer import PageVectorAccumulator


def ensure_sample_scanned_bangla_pdf() -> Path:
    """Create a realistic 2-page pure image-based (non-selectable) scanned Bangla + English PDF with table & diagram."""
    sample_pdf = SAMPLES_DIR / "Bangla_Research_Report_Scanned_Sample.pdf"
    if sample_pdf.exists() and sample_pdf.stat().st_size > 10_000:
        return sample_pdf

    # Step 1: Compose crisp vector master document using HarfBuzz shaper, then rasterize to pure scanned images (ZERO text layer!)
    master = fitz.open()

    # --- PAGE 1: Title, Emblem Diagram, Mixed Bangla+English Paragraphs, Complex Juktakkhor ---
    p1 = master.new_page(width=595.0, height=842.0)
    sh1 = p1.new_shape()
    # Decorative institutional emblem/diagram in top-right (non-text illustration to test image preservation!)
    emblem_rect = fitz.Rect(455, 42, 545, 132)
    sh1.draw_rect(emblem_rect)
    sh1.finish(color=(0.10, 0.32, 0.24), fill=(0.91, 0.97, 0.94), width=1.8)
    sh1.draw_circle((500, 87), 31)
    sh1.finish(color=(0.06, 0.42, 0.28), fill=(0.12, 0.55, 0.38), width=1.5)
    sh1.draw_circle((500, 87), 16)
    sh1.finish(color=(0.85, 0.18, 0.20), fill=(0.86, 0.20, 0.22), width=1.0)
    # Horizontal header divider
    sh1.draw_line((48, 148), (547, 148))
    sh1.finish(color=(0.15, 0.25, 0.45), width=1.2)
    sh1.commit()

    acc1 = PageVectorAccumulator(p1, font_key="hind_siliguri")
    acc1.add_visible_shaped_line(
        "জাতীয় ডিজিটাল বাংলা আর্কাইভ ও গবেষণা প্রতিবেদন ২০২৬",
        [48, 52, 435, 80],
        fontsize=18.5,
        bold=True,
        ink_rgb=[14, 42, 92],
        fit_to_box=True,
    )
    acc1.add_visible_shaped_line(
        "National Bangla Document Digitization Initiative (Report ID: BD-2026-09)",
        [48, 88, 435, 108],
        fontsize=10.5,
        bold=False,
        ink_rgb=[65, 75, 95],
        fit_to_box=True,
    )
    acc1.add_visible_shaped_line(
        "প্রকাশকাল: ১৯ নভেম্বর ২০২৬ খ্রিস্টাব্দ | সংস্করণ: ১.০",
        [48, 114, 420, 134],
        fontsize=11.0,
        bold=False,
        ink_rgb=[35, 90, 65],
        fit_to_box=True,
    )

    acc1.add_visible_shaped_line(
        "১. ভূমিকা ও প্রকল্পের মূল উদ্দেশ্য",
        [48, 172, 420, 196],
        fontsize=15.0,
        bold=True,
        ink_rgb=[18, 32, 68],
        fit_to_box=False,
    )

    p1_para1 = [
        "বাংলাদেশের প্রাচীন গ্রন্থ, সরকারি গেজেট, বিশ্ববিদ্যালয় গবেষণা প্রবন্ধ এবং ঐতিহাসিক সংবাদপত্র",
        "সংরক্ষণের জন্য উন্নত অপটিক্যাল ক্যারেক্টার রিকগনিশন (OCR) প্রযুক্তি অত্যন্ত গুরুত্বপূর্ণ।",
        "স্ক্যান করা পিডিএফ নথির মূল পৃষ্ঠার গঠন, মার্জিন, অনুচ্ছেদ, ছবি এবং সারণি অক্ষুণ্ণ রেখে",
        "সেগুলোকে সম্পূর্ণ অনুসন্ধানযোগ্য ও সম্পাদনাযোগ্য ইউনিকোড বাংলায় রূপান্তর করাই এর লক্ষ্য।",
    ]
    y_cur = 210.0
    for ln in p1_para1:
        acc1.add_visible_shaped_line(ln, [48, y_cur, 545, y_cur + 20], fontsize=12.0, ink_rgb=[22, 22, 26], fit_to_box=False)
        y_cur += 24.0

    acc1.add_visible_shaped_line(
        "২. জটিল যুক্তাক্ষর ও ভাষাগত বৈশিষ্ট্য যাচাই",
        [48, 328, 440, 352],
        fontsize=15.0,
        bold=True,
        ink_rgb=[18, 32, 68],
        fit_to_box=False,
    )

    p1_para2 = [
        "বাংলা লিপিতে স্বরবর্ণ, ব্যঞ্জনবর্ণ, কার-চিহ্ন, ফলা এবং জটিল যুক্তাক্ষর যেমন ক্ষ, জ্ঞ, শ্র, স্ত্র,",
        "ন্দ, প্র, ত্ত, ক্ত, এবং রেফ-যুক্ত শব্দ (যেমন: শিক্ষার্থী, স্বাধীনতা, বিজ্ঞান-প্রযুক্তি, কেন্দ্র, রাষ্ট্র)",
        "সঠিকভাবে শনাক্ত করা আবশ্যক। এছাড়া বাংলা সংখ্যা (০১২৩৪৫৬৭৮৯) এবং English Numerals",
        "(0123456789) একই নথিতে নিখুঁতভাবে ইউনিকোড মানে সংরক্ষিত হওয়া প্রয়োজন।",
    ]
    y_cur = 366.0
    for ln in p1_para2:
        acc1.add_visible_shaped_line(ln, [48, y_cur, 545, y_cur + 20], fontsize=12.0, ink_rgb=[22, 22, 26], fit_to_box=False)
        y_cur += 24.0

    # Add a bordered 4x3 table on Page 1!
    acc1.add_visible_shaped_line(
        "৩. বিভাগওয়ারী ডিজিটাইজেশন পরিসংখ্যান সারণি",
        [48, 488, 450, 512],
        fontsize=14.5,
        bold=True,
        ink_rgb=[18, 32, 68],
        fit_to_box=False,
    )

    sh_tbl = p1.new_shape()
    col_x = [48.0, 215.0, 385.0, 545.0]
    row_y = [528.0, 562.0, 596.0, 630.0, 664.0]
    for r in range(4):
        for c in range(3):
            rect = fitz.Rect(col_x[c], row_y[r], col_x[c + 1], row_y[r + 1])
            sh_tbl.draw_rect(rect)
            sh_tbl.finish(
                color=(0.20, 0.25, 0.32),
                fill=(0.92, 0.95, 0.98) if r == 0 else None,
                width=1.0,
            )
    sh_tbl.commit()

    table_data = [
        ["নথির ধরন (Category)", "মোট পৃষ্ঠা (Pages)", "নির্ভুলতা (Accuracy)"],
        ["সাহিত্য ও উপন্যাস", "১২,৪৫০", "৯৮.৬%"],
        ["সরকারি প্রজ্ঞাপন", "৮,৩২০", "৯৭.৪%"],
        ["বিজ্ঞান ও গবেষণা", "৫,১৮০", "৯৮.১%"],
    ]
    for r_i, row in enumerate(table_data):
        for c_i, val in enumerate(row):
            acc1.add_visible_shaped_line(
                val,
                [col_x[c_i] + 8, row_y[r_i] + 7, col_x[c_i + 1] - 8, row_y[r_i + 1] - 5],
                fontsize=11.5,
                bold=(r_i == 0),
                ink_rgb=[15, 23, 42],
                fit_to_box=True,
            )

    acc1.add_visible_shaped_line("পৃষ্ঠা ১", [272, 790, 325, 810], fontsize=10.5, ink_rgb=[90, 95, 105], alignment="center", fit_to_box=False)
    acc1.commit()

    # --- PAGE 2: Bilingual Technical Guidelines & Key Takeaways ---
    p2 = master.new_page(width=595.0, height=842.0)
    acc2 = PageVectorAccumulator(p2, font_key="hind_siliguri")
    acc2.add_visible_shaped_line(
        "৪. ইপাব ৩ (EPUB 3) এবং সম্পাদনাযোগ্য পিডিএফ রূপান্তর নির্দেশিকা",
        [48, 56, 545, 82],
        fontsize=15.5,
        bold=True,
        ink_rgb=[14, 42, 92],
        fit_to_box=True,
    )
    p2_lines = [
        "আধুনিক ই-বুক পাঠকদের জন্য ইউনিকোড বাংলা ফন্ট সংযুক্ত করে ইপাব ৩ (EPUB 3) ফরম্যাট তৈরি",
        "করা হলে মোবাইল, ট্যাবলেট এবং কম্পিউটারে পর্দার মাপ অনুযায়ী লেখা স্বয়ংক্রিয়ভাবে বিন্যস্ত হয়।",
        "অন্যদিকে Searchable PDF মোডে মূল স্ক্যান করা পৃষ্ঠার দৃশ্যমান রূপ শতভাগ অপরিবর্তিত থাকে,",
        "ফলে স্বাক্ষর, সিলমোহর, সারণি এবং প্রচ্ছদ অবিকল মূল নথির মতোই দেখায়।",
    ]
    y_cur = 100.0
    for ln in p2_lines:
        acc2.add_visible_shaped_line(ln, [48, y_cur, 545, y_cur + 20], fontsize=12.0, ink_rgb=[22, 22, 26], fit_to_box=False)
        y_cur += 25.0

    acc2.add_visible_shaped_line(
        "5. Bilingual Interoperability & Copy-Paste Verification",
        [48, 225, 520, 248],
        fontsize=14.5,
        bold=True,
        ink_rgb=[18, 32, 68],
        fit_to_box=False,
    )
    p2_eng = [
        "Every converted document preserves clean UTF-8 NFC Unicode sequences so users can press",
        "Ctrl+F to search Bangla or English keywords and copy text directly into Microsoft Word,",
        "Google Docs, LibreOffice Writer, or plain-text editors without broken ligatures.",
    ]
    y_cur = 262.0
    for ln in p2_eng:
        acc2.add_visible_shaped_line(ln, [48, y_cur, 545, y_cur + 20], fontsize=11.5, ink_rgb=[30, 35, 45], fit_to_box=False)
        y_cur += 23.0

    acc2.add_visible_shaped_line("পৃষ্ঠা ২", [272, 790, 325, 810], fontsize=10.5, ink_rgb=[90, 95, 105], alignment="center", fit_to_box=False)
    acc2.commit()

    # Step 2: Rasterize both pages to pure scanned images (with subtle realistic paper tone) -> ZERO text layer!
    scanned_doc = fitz.open()
    rng = np.random.default_rng(2026)
    for idx in range(master.page_count):
        pix = master[idx].get_pixmap(dpi=220, alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
        # Add subtle warm off-white paper tint + tiny sensor grain to mimic real flatbed scanner
        noise = rng.integers(-3, 4, size=arr.shape[:2], dtype=np.int16)
        paper = arr.astype(np.int16)
        paper[:, :, 0] = np.clip(paper[:, :, 0] - 2 + noise, 0, 255)
        paper[:, :, 1] = np.clip(paper[:, :, 1] - 3 + noise, 0, 255)
        paper[:, :, 2] = np.clip(paper[:, :, 2] - 6 + noise, 0, 255)
        scan_bgr = cv2.cvtColor(paper.astype(np.uint8), cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(".jpg", scan_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

        sp = scanned_doc.new_page(width=595.0, height=842.0)
        if ok:
            sp.insert_image(sp.rect, stream=buf.tobytes())

    scanned_doc.set_metadata(
        {
            "title": "জাতীয় ডিজিটাল বাংলা আর্কাইভ প্রতিবেদন (Scanned Sample)",
            "author": "BanglaDoc Sample Archive",
        }
    )
    scanned_doc.save(str(sample_pdf), garbage=3, deflate=True)
    scanned_doc.close()
    master.close()
    return sample_pdf
