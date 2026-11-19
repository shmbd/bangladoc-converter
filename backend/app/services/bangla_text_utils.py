from __future__ import annotations

import re
import unicodedata
from typing import Literal

BANGLA_CONSONANT_RE = re.compile(r"[\u0995-\u09B9\u09DC-\u09DF]")
BANGLA_CHAR_RE = re.compile(r"[\u0980-\u09FF]")
BANGLA_NUMERAL_RE = re.compile(r"[\u09E6-\u09EF]")
ENGLISH_CHAR_RE = re.compile(r"[A-Za-z]")
ASCII_NUMERAL_RE = re.compile(r"[0-9]")

# Juktakkhor: Consonant + Hasanta (U+09CD) + (optional ZWJ) + Consonant
JUKTAKKHOR_RE = re.compile(r"[\u0995-\u09B9\u09DC-\u09DF]\u09CD\u200D?[\u0995-\u09B9\u09DC-\u09DF]")

# Dependent vowel signs (Kar) + Hasanta + Chandrabindu/Anusvara/Visarga
KAR_FOLA_RE = re.compile(r"[\u0981-\u0983\u09BE-\u09CC\u09CD\u09D7]")

# Pre-base Kars in visual order that might accidentally appear at start of word before consonant
ORPHAN_PRE_KAR_RE = re.compile(r"(?:^|(?<=\s))([\u09BF\u09C7\u09C8])([\u0995-\u09B9\u09DC-\u09DF](?:\u09CD[\u0995-\u09B9\u09DC-\u09DF])*)")

# Common Bijoy/SutonnyMJ legacy ANSI artifact characters
LEGACY_BIJOY_ARTIFACTS = set("†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ¡¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿")
LEGACY_BIJOY_FONTS = ("sutonny", "solaimanlipi_ansi", "kalpurush ansi", "nikoshban", "kongsho", "amarbangla")


def normalize_bangla_unicode(text: str) -> str:
    """Clean and normalize Bangla + English text into valid logical Unicode NFC."""
    if not text:
        return ""
    # Replace null bytes and soft hyphens
    cleaned = text.replace("\x00", "").replace("\xad", "")
    # Canonical NFC normalization
    cleaned = unicodedata.normalize("NFC", cleaned)

    # Fix accidental visual-order pre-base vowel signs (ি, ে, ৈ placed before consonant cluster)
    cleaned = ORPHAN_PRE_KAR_RE.sub(r"\2\1", cleaned)

    # Combine split two-part vowel signs if separated
    cleaned = cleaned.replace("\u09C7\u09BE", "\u09CB")  # ে + া -> ো
    cleaned = cleaned.replace("\u09C7\u09D7", "\u09CC")  # ে + ৗ -> ৌ

    # Collapse repeated duplicate identical vowel signs on same consonant (common OCR stutter)
    cleaned = re.sub(r"([\u09BE-\u09CC])\1+", r"\1", cleaned)

    # Normalize horizontal whitespace while keeping single spaces
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return unicodedata.normalize("NFC", cleaned).strip()


def classify_token_language(token: str) -> Literal["bn", "en", "num", "punct", "mixed"]:
    bn = len(BANGLA_CHAR_RE.findall(token))
    en = len(ENGLISH_CHAR_RE.findall(token))
    bn_num = len(BANGLA_NUMERAL_RE.findall(token))
    en_num = len(ASCII_NUMERAL_RE.findall(token))
    if bn_num + en_num > 0 and (bn - bn_num) == 0 and en == 0:
        return "num"
    if bn > 0 and en > 0:
        return "mixed"
    if bn > 0:
        return "bn"
    if en > 0:
        return "en"
    return "punct"


def detect_legacy_ansi_encoding(text: str, font_names: list[str]) -> bool:
    """Detect non-Unicode legacy Bijoy/SutonnyMJ text layers that look garbled when copied."""
    lower_fonts = " ".join(f.lower() for f in font_names)
    if any(tag in lower_fonts for tag in LEGACY_BIJOY_FONTS):
        return True
    if not text or len(text.strip()) < 10:
        return False
    suspect_chars = sum(1 for ch in text if ch in LEGACY_BIJOY_ARTIFACTS)
    replacement_chars = text.count("\ufffd")
    pua_chars = sum(1 for ch in text if 0xE000 <= ord(ch) <= 0xF8FF)
    total = max(len(text), 1)
    if (suspect_chars / total) > 0.06 or (replacement_chars + pua_chars) / total > 0.04:
        return True
    return False


def analyze_bangla_metrics(text: str) -> dict[str, int | bool]:
    norm = unicodedata.normalize("NFC", text)
    bangla_numerals = len(BANGLA_NUMERAL_RE.findall(norm))
    bangla_chars = len(BANGLA_CHAR_RE.findall(norm))
    english_chars = len(ENGLISH_CHAR_RE.findall(norm))
    juktakkhors = len(JUKTAKKHOR_RE.findall(norm))
    kar_folas = len(KAR_FOLA_RE.findall(norm))

    # Check Unicode integrity: no U+FFFD replacement chars, no PUA glyphs, no orphan starting Kar
    has_replacement = "\ufffd" in norm
    has_pua = any(0xE000 <= ord(c) <= 0xF8FF for c in norm)
    orphan_kars = len(re.findall(r"(?:^|\s)[\u09BE-\u09CD]", norm))

    return {
        "bangla_char_count": bangla_chars,
        "english_char_count": english_chars,
        "bangla_numeral_count": bangla_numerals,
        "juktakkhor_count": juktakkhors,
        "kar_fola_count": kar_folas,
        "unicode_integrity_passed": (not has_replacement) and (not has_pua),
        "character_order_valid": orphan_kars <= max(2, int(0.01 * max(bangla_chars, 1))),
    }


def parse_page_range(page_range: str, total_pages: int) -> list[int]:
    """Parse '1-3, 5, 8-10' into sorted 1-indexed page numbers within [1, total_pages]."""
    if not page_range or not page_range.strip():
        return list(range(1, total_pages + 1))

    # Also convert Bangla numerals in page range input (e.g. "১-৩, ৫" -> "1-3, 5")!
    bn_to_ascii = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    cleaned = page_range.translate(bn_to_ascii)

    selected: set[int] = set()
    for part in cleaned.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-", 1)
            if bounds[0].strip().isdigit() and bounds[1].strip().isdigit():
                start = max(1, int(bounds[0].strip()))
                end = min(total_pages, int(bounds[1].strip()))
                if start <= end:
                    selected.update(range(start, end + 1))
        elif part.isdigit():
            p = int(part)
            if 1 <= p <= total_pages:
                selected.add(p)

    return sorted(selected) if selected else list(range(1, total_pages + 1))
