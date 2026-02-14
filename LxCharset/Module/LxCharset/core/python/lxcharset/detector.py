from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class DetectionResult:
    encoding: str
    confidence: float
    used_fallback: bool
    detected_by_bom: bool


_POLISH_DIACRITICS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
_POLISH_BIGRAMS = ("sz", "cz", "rz", "dz", "ch", "ie", "ow", "ni")
_POLISH_TRIGRAMS = ("prz", "str", "nie", "dzi", "rze", "szc", "czn")
_CP1250_BYTE_WEIGHTS = {
    0xA5: 2.00,
    0xB9: 2.00,
    0x8C: 1.70,
    0x9C: 1.70,
    0x8F: 1.70,
    0x9F: 1.70,
    0xC6: 0.80,
    0xE6: 0.80,
    0xCA: 0.80,
    0xEA: 0.80,
    0xA3: 0.70,
    0xB3: 0.70,
    0xD1: 0.70,
    0xF1: 0.70,
    0xD3: 0.70,
    0xF3: 0.70,
}
_ISO88592_BYTE_WEIGHTS = {
    0xA1: 2.00,
    0xB1: 2.00,
    0xA6: 1.70,
    0xB6: 1.70,
    0xAC: 1.70,
    0xBC: 1.70,
    0xC6: 0.80,
    0xE6: 0.80,
    0xCA: 0.80,
    0xEA: 0.80,
    0xA3: 0.70,
    0xB3: 0.70,
    0xD1: 0.70,
    0xF1: 0.70,
    0xD3: 0.70,
    0xF3: 0.70,
}
_EARLY_EXIT_BYTES = 4096
_EARLY_EXIT_CONFIDENCE = 0.98
_AMBIGUITY_DELTA = 0.03
_LANGUAGE_FALLBACK_ORDER = (
    "utf-8",
    "utf-8-sig",
    "utf-16-le",
    "utf-16-be",
    "utf-32-le",
    "utf-32-be",
    "iso-2022-jp",
    "shift_jis",
    "euc_jp",
    "big5",
    "windows-1250",
    "iso-8859-2",
    "latin-1",
)
_LANGUAGE_FALLBACK_RANK = {enc: i for i, enc in enumerate(_LANGUAGE_FALLBACK_ORDER)}
_feedback_hook: Callable[..., None] | None = None
_DISTRIBUTION_PATTERNS = {
    "windows-1250": {
        0xA5: (0.0030, 1.2),
        0xB9: (0.0032, 1.2),
        0x8C: (0.0012, 1.0),
        0x9C: (0.0015, 1.0),
        0x8F: (0.0010, 1.0),
        0x9F: (0.0012, 1.0),
        0xC6: (0.0025, 0.8),
        0xE6: (0.0028, 0.8),
        0xCA: (0.0020, 0.8),
        0xEA: (0.0021, 0.8),
        0xD1: (0.0018, 0.7),
        0xF1: (0.0020, 0.7),
        0xD3: (0.0040, 0.7),
        0xF3: (0.0042, 0.7),
    },
    "iso-8859-2": {
        0xA1: (0.0030, 1.2),
        0xB1: (0.0032, 1.2),
        0xA6: (0.0012, 1.0),
        0xB6: (0.0015, 1.0),
        0xAC: (0.0010, 1.0),
        0xBC: (0.0012, 1.0),
        0xC6: (0.0025, 0.8),
        0xE6: (0.0028, 0.8),
        0xCA: (0.0020, 0.8),
        0xEA: (0.0021, 0.8),
        0xD1: (0.0018, 0.7),
        0xF1: (0.0020, 0.7),
        0xD3: (0.0040, 0.7),
        0xF3: (0.0042, 0.7),
    },
}


def set_feedback_hook(hook: Callable[..., None] | None) -> None:
    """Set optional feedback callback(level, code, message, **context)."""
    global _feedback_hook
    _feedback_hook = hook


def _emit_feedback(level: str, code: str, message: str, **context: Any) -> None:
    if _feedback_hook is None:
        return
    try:
        _feedback_hook(level, code, message, **context)
    except Exception:
        # Feedback must never break detection flow.
        pass


def emit_feedback(level: str, code: str, message: str, **context: Any) -> None:
    _emit_feedback(level, code, message, **context)


def _detect_bom_encoding(data: bytes) -> str | None:
    if data.startswith(b"\x00\x00\xFE\xFF"):
        return "utf-32-be"
    if data.startswith(b"\xFF\xFE\x00\x00"):
        return "utf-32-le"
    if data.startswith(b"\xEF\xBB\xBF"):
        return "utf-8-sig"
    if data.startswith(b"\xFE\xFF"):
        return "utf-16-be"
    if data.startswith(b"\xFF\xFE"):
        return "utf-16-le"
    return None


def build_byte_frequency_table(data: bytes) -> list[int]:
    """Return frequency table (256 bins) for raw byte stream."""
    table = [0] * 256
    for b in data:
        table[b] += 1
    return table


def byte_frequency_ratio(data: bytes, byte_value: int) -> float:
    """Return relative frequency for a specific byte value (0..255)."""
    if not (0 <= byte_value <= 255):
        raise ValueError("byte_value must be in range 0..255")
    if not data:
        return 0.0
    table = build_byte_frequency_table(data)
    return table[byte_value] / len(data)


def build_ngram_frequency_table(text: str, n: int) -> dict[str, int]:
    """Return frequency table for character n-grams."""
    if n <= 0:
        raise ValueError("n must be > 0")
    if len(text) < n:
        return {}

    table: dict[str, int] = {}
    for i in range(0, len(text) - n + 1):
        gram = text[i : i + n]
        table[gram] = table.get(gram, 0) + 1
    return table


def ngram_frequency_ratio(text: str, token: str) -> float:
    """Return relative frequency for specific n-gram token."""
    n = len(token)
    if n == 0 or len(text) < n:
        return 0.0
    table = build_ngram_frequency_table(text, n)
    total = len(text) - n + 1
    return table.get(token, 0) / max(total, 1)


def analyze_polish_ngrams(text: str) -> float:
    """Score Polish-like language patterns using bi-grams and tri-grams."""
    lowered = text.lower()
    if len(lowered) < 2:
        return 0.0

    bigram_table = build_ngram_frequency_table(lowered, 2)
    trigram_table = build_ngram_frequency_table(lowered, 3)
    total_bigrams = max(len(lowered) - 1, 1)
    total_trigrams = max(len(lowered) - 2, 1)

    bigram_hits = sum(bigram_table.get(bg, 0) for bg in _POLISH_BIGRAMS)
    trigram_hits = sum(trigram_table.get(tg, 0) for tg in _POLISH_TRIGRAMS)

    bigram_ratio = bigram_hits / total_bigrams
    trigram_ratio = trigram_hits / total_trigrams

    # Trigrams are stronger language signal than bigrams.
    return bigram_ratio * 0.9 + trigram_ratio * 1.6


def polish_specific_weighting(data: bytes, encoding: str) -> float:
    """Byte-level weighting for cp1250 vs iso-8859-2 Polish profiles."""
    if not data:
        return 0.0

    table = build_byte_frequency_table(data)
    total = len(data)

    if encoding == "windows-1250":
        own = _CP1250_BYTE_WEIGHTS
        opp = _ISO88592_BYTE_WEIGHTS
    elif encoding == "iso-8859-2":
        own = _ISO88592_BYTE_WEIGHTS
        opp = _CP1250_BYTE_WEIGHTS
    else:
        return 0.0

    own_score = sum((table[b] / total) * w for b, w in own.items())
    opp_score = sum((table[b] / total) * w for b, w in opp.items())
    return own_score - opp_score * 0.75


def distribution_match_score(data: bytes, encoding: str) -> float:
    """
    Compare file byte distribution against built-in encoding template.
    Returns score in range [0.0, 1.0], where 1.0 means very close match.
    """
    pattern = _DISTRIBUTION_PATTERNS.get(encoding)
    if not data or pattern is None:
        return 0.0

    table = build_byte_frequency_table(data)
    total = len(data)

    weighted_distance = 0.0
    weight_sum = 0.0
    for b, (expected_ratio, weight) in pattern.items():
        actual_ratio = table[b] / total
        weighted_distance += abs(actual_ratio - expected_ratio) * weight
        weight_sum += weight

    if weight_sum <= 0.0:
        return 0.0

    normalized_distance = weighted_distance / weight_sum
    # Small distances should still give clear positive signal.
    return max(0.0, min(1.0, 1.0 - normalized_distance * 20.0))


def calculate_transition_confidence(valid_transitions: int, invalid_transitions: int) -> float:
    """Estimate probability from valid/invalid automaton transitions."""
    v = max(valid_transitions, 0)
    i = max(invalid_transitions, 0)
    # Laplace-smoothed Bernoulli estimate.
    return (v + 1.0) / (v + i + 2.0)


def _choose_by_language_fallback_map(
    candidates: list[tuple[str, float]],
    ambiguity_delta: float = _AMBIGUITY_DELTA,
) -> tuple[str, float] | None:
    if not candidates:
        return None

    filtered = [(enc, conf) for enc, conf in candidates if enc]
    if not filtered:
        return None

    best_conf = max(conf for _, conf in filtered)
    near_best = [(enc, conf) for enc, conf in filtered if (best_conf - conf) <= ambiguity_delta]
    if len(near_best) == 1:
        _emit_feedback(
            "DEBUG",
            "fallback-map:single",
            "Fallback map accepted top-confidence candidate",
            encoding=near_best[0][0],
            confidence=round(near_best[0][1], 6),
        )
        return near_best[0]

    near_best.sort(
        key=lambda item: (
            _LANGUAGE_FALLBACK_RANK.get(item[0], len(_LANGUAGE_FALLBACK_RANK)),
            -item[1],
            item[0],
        )
    )
    _emit_feedback(
        "DEBUG",
        "fallback-map:tiebreak",
        "Fallback map resolved ambiguous candidates",
        encoding=near_best[0][0],
        confidence=round(near_best[0][1], 6),
        candidates=len(near_best),
    )
    return near_best[0]


def analyze_utf8_dfa(data: bytes) -> tuple[bool, int, int]:
    """Validate UTF-8 bytes and return (is_valid, valid_transitions, invalid_transitions)."""
    remaining = 0
    first_continuation = False
    first_min = 0x80
    first_max = 0xBF
    valid = 0
    invalid = 0

    for byte in data:
        if remaining == 0:
            if byte <= 0x7F:
                valid += 1
                continue
            if 0xC2 <= byte <= 0xDF:
                remaining = 1
                first_continuation = True
                first_min, first_max = 0x80, 0xBF
                valid += 1
                continue
            if byte == 0xE0:
                remaining = 2
                first_continuation = True
                first_min, first_max = 0xA0, 0xBF
                valid += 1
                continue
            if 0xE1 <= byte <= 0xEC or 0xEE <= byte <= 0xEF:
                remaining = 2
                first_continuation = True
                first_min, first_max = 0x80, 0xBF
                valid += 1
                continue
            if byte == 0xED:
                remaining = 2
                first_continuation = True
                first_min, first_max = 0x80, 0x9F
                valid += 1
                continue
            if byte == 0xF0:
                remaining = 3
                first_continuation = True
                first_min, first_max = 0x90, 0xBF
                valid += 1
                continue
            if 0xF1 <= byte <= 0xF3:
                remaining = 3
                first_continuation = True
                first_min, first_max = 0x80, 0xBF
                valid += 1
                continue
            if byte == 0xF4:
                remaining = 3
                first_continuation = True
                first_min, first_max = 0x80, 0x8F
                valid += 1
                continue
            invalid += 1
            return False, valid, invalid

        if first_continuation:
            if not (first_min <= byte <= first_max):
                invalid += 1
                return False, valid, invalid
            first_continuation = False
            remaining -= 1
            valid += 1
            continue

        if not (0x80 <= byte <= 0xBF):
            invalid += 1
            return False, valid, invalid
        remaining -= 1
        valid += 1

    if remaining != 0:
        invalid += 1
        return False, valid, invalid
    return True, valid, invalid


def validate_utf8_dfa(data: bytes) -> bool:
    return analyze_utf8_dfa(data)[0]


def analyze_utf16_surrogate_pairs(data: bytes, little_endian: bool) -> tuple[bool, int, int]:
    """Validate UTF-16 surrogate pairs and return transition stats."""
    if len(data) % 2 != 0:
        return False, 0, 1

    expect_low = False
    valid = 0
    invalid = 0
    for i in range(0, len(data), 2):
        if little_endian:
            unit = data[i] | (data[i + 1] << 8)
        else:
            unit = (data[i] << 8) | data[i + 1]

        if 0xD800 <= unit <= 0xDBFF:
            if expect_low:
                invalid += 1
                return False, valid, invalid
            expect_low = True
            valid += 1
            continue

        if 0xDC00 <= unit <= 0xDFFF:
            if not expect_low:
                invalid += 1
                return False, valid, invalid
            expect_low = False
            valid += 1
            continue

        if expect_low:
            invalid += 1
            return False, valid, invalid
        valid += 1

    if expect_low:
        invalid += 1
        return False, valid, invalid
    return True, valid, invalid


def validate_utf16_surrogate_pairs(data: bytes, little_endian: bool) -> bool:
    return analyze_utf16_surrogate_pairs(data, little_endian)[0]


def _single_byte_score(decoded: str) -> float:
    if not decoded:
        return 0.0

    printable = 0
    c1_controls = 0
    polish_hits = 0
    suspicious_symbols = 0

    for ch in decoded:
        code = ord(ch)
        if ch.isprintable() or ch in ("\n", "\r", "\t"):
            printable += 1
        if 0x80 <= code <= 0x9F:
            c1_controls += 1
        if ch in _POLISH_DIACRITICS:
            polish_hits += 1
        if ch in "¤¦¨´¸":
            suspicious_symbols += 1

    length = max(len(decoded), 1)
    printable_ratio = printable / length
    c1_ratio = c1_controls / length
    polish_ratio = polish_hits / length
    suspicious_ratio = suspicious_symbols / length

    score = printable_ratio
    score += min(0.35, polish_ratio * 4.0)
    score += min(0.45, analyze_polish_ngrams(decoded) * 2.8)
    score -= c1_ratio * 2.5
    score -= suspicious_ratio * 0.8
    return score


def probe_single_byte_encoding(data: bytes) -> tuple[str, float] | None:
    candidates = ("windows-1250", "iso-8859-2")
    best_encoding = "windows-1250"
    best_score = -10.0

    for enc in candidates:
        try:
            decoded = data.decode(enc, errors="strict")
        except UnicodeDecodeError:
            _emit_feedback("DEBUG", "single-byte:reject", "Single-byte candidate rejected", encoding=enc)
            continue
        score = _single_byte_score(decoded)
        score += max(-0.9, min(0.9, polish_specific_weighting(data, enc)))
        score += (distribution_match_score(data, enc) - 0.5) * 1.1
        if score > best_score:
            best_score = score
            best_encoding = enc

    if best_score <= -9.0:
        _emit_feedback("DEBUG", "single-byte:none", "No valid single-byte candidate", size=len(data))
        return None

    confidence = max(0.0, min(0.93, 0.45 + best_score * 0.32))
    _emit_feedback(
        "DEBUG",
        "single-byte:select",
        "Single-byte candidate selected",
        encoding=best_encoding,
        confidence=round(confidence, 6),
    )
    return best_encoding, confidence


def _validate_shift_jis(data: bytes) -> tuple[bool, int]:
    i = 0
    signal = 0
    pair_count = 0
    has_high = False
    n = len(data)
    while i < n:
        b = data[i]
        if b <= 0x7F:
            i += 1
            continue
        has_high = True
        if 0xA1 <= b <= 0xDF:
            signal += 1
            i += 1
            continue
        if (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC):
            if i + 1 >= n:
                return False, 0
            t = data[i + 1]
            if not ((0x40 <= t <= 0x7E) or (0x80 <= t <= 0xFC)) or t == 0x7F:
                return False, 0
            signal += 2
            pair_count += 1
            i += 2
            continue
        return False, 0
    if has_high and pair_count == 0:
        return False, 0
    return True, signal


def _validate_euc_jp(data: bytes) -> tuple[bool, int]:
    i = 0
    signal = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b <= 0x7F:
            i += 1
            continue
        if b == 0x8E:
            if i + 1 >= n:
                return False, 0
            t = data[i + 1]
            if not (0xA1 <= t <= 0xDF):
                return False, 0
            signal += 2
            i += 2
            continue
        if b == 0x8F:
            if i + 2 >= n:
                return False, 0
            t1 = data[i + 1]
            t2 = data[i + 2]
            if not (0xA1 <= t1 <= 0xFE and 0xA1 <= t2 <= 0xFE):
                return False, 0
            signal += 3
            i += 3
            continue
        if 0xA1 <= b <= 0xFE:
            if i + 1 >= n:
                return False, 0
            t = data[i + 1]
            if not (0xA1 <= t <= 0xFE):
                return False, 0
            signal += 2
            i += 2
            continue
        return False, 0
    return True, signal


def _validate_big5(data: bytes) -> tuple[bool, int]:
    i = 0
    signal = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b <= 0x7F:
            i += 1
            continue
        if 0x81 <= b <= 0xFE:
            if i + 1 >= n:
                return False, 0
            t = data[i + 1]
            if not ((0x40 <= t <= 0x7E) or (0xA1 <= t <= 0xFE)):
                return False, 0
            signal += 2
            i += 2
            continue
        return False, 0
    return True, signal


def _multibyte_text_score(decoded: str, encoding: str) -> float:
    if not decoded:
        return -10.0

    kana = 0
    cjk = 0
    printable = 0
    for ch in decoded:
        code = ord(ch)
        if 0x3040 <= code <= 0x30FF:
            kana += 1
        if 0x4E00 <= code <= 0x9FFF:
            cjk += 1
        if ch.isprintable() or ch in ("\n", "\r", "\t"):
            printable += 1

    length = max(len(decoded), 1)
    printable_ratio = printable / length
    kana_ratio = kana / length
    cjk_ratio = cjk / length

    score = printable_ratio + cjk_ratio * 0.8
    if encoding in ("shift_jis", "euc_jp"):
        score += kana_ratio * 1.0
    elif encoding == "big5":
        if kana_ratio == 0.0 and cjk_ratio >= 0.5:
            score += 0.25
        score -= kana_ratio * 1.2
    return score


def probe_multi_byte_encoding(data: bytes) -> tuple[str, float] | None:
    checks = (
        ("shift_jis", _validate_shift_jis),
        ("euc_jp", _validate_euc_jp),
        ("big5", _validate_big5),
    )
    best_encoding = ""
    best_score = -10.0
    best_ratio = 0.0
    best_signal = 0

    for enc, validator in checks:
        ok, signal = validator(data)
        if not ok:
            _emit_feedback("DEBUG", "multi-byte:reject", "Multi-byte candidate rejected", encoding=enc)
            continue
        try:
            decoded = data.decode(enc, errors="strict")
        except UnicodeDecodeError:
            _emit_feedback("DEBUG", "multi-byte:decode-error", "Multi-byte decode failed", encoding=enc)
            continue

        text_score = _multibyte_text_score(decoded, enc)
        ratio = signal / max(len(data), 1)
        score = text_score + ratio * 0.5
        if score > best_score or (score == best_score and ratio > best_ratio):
            best_score = score
            best_ratio = ratio
            best_signal = signal
            best_encoding = enc

    if best_encoding == "":
        _emit_feedback("DEBUG", "multi-byte:none", "No valid multi-byte candidate", size=len(data))
        return None

    confidence = max(0.55, min(0.95, calculate_transition_confidence(best_signal, 0)))
    _emit_feedback(
        "DEBUG",
        "multi-byte:select",
        "Multi-byte candidate selected",
        encoding=best_encoding,
        confidence=round(confidence, 6),
    )
    return best_encoding, confidence


def probe_escape_sequence_encoding(data: bytes) -> tuple[str, float] | None:
    esc = 0x1B
    if esc not in data:
        return None

    if any(b >= 0x80 for b in data):
        _emit_feedback("DEBUG", "escape:reject", "Escape sequence rejected by high-byte content")
        return None

    i = 0
    hits = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b != esc:
            i += 1
            continue

        if i + 2 >= n:
            return None

        b1 = data[i + 1]
        b2 = data[i + 2]

        if b1 == 0x28 and b2 in (0x42, 0x4A, 0x49):  # ESC ( B/J/I
            hits += 1
            i += 3
            continue
        if b1 == 0x24 and b2 in (0x40, 0x42):  # ESC $ @ / ESC $ B
            hits += 1
            i += 3
            continue
        if b1 == 0x24 and b2 == 0x28:  # ESC $ ( D
            if i + 3 >= n or data[i + 3] != 0x44:
                return None
            hits += 1
            i += 4
            continue
        if b1 == 0x26 and b2 == 0x40:  # ESC & @ (prefix in ISO-2022-JP-2004 flows)
            hits += 1
            i += 3
            continue

        return None

    if hits == 0:
        return None

    confidence = max(0.8, min(0.99, calculate_transition_confidence(hits, 0)))
    _emit_feedback(
        "DEBUG",
        "escape:select",
        "Escape-sequence encoding selected",
        encoding="iso-2022-jp",
        confidence=round(confidence, 6),
        hits=hits,
    )
    return "iso-2022-jp", confidence


def _detect_encoding_core(data: bytes) -> DetectionResult:
    """Core detection pass without early-exit wrapper."""
    _emit_feedback("DEBUG", "core:start", "Core detection started", size=len(data))
    bom_encoding = _detect_bom_encoding(data)
    if bom_encoding == "utf-16-le":
        payload = data[2:]
        ok, valid, invalid = analyze_utf16_surrogate_pairs(payload, little_endian=True)
        if ok:
            conf = max(0.9, calculate_transition_confidence(valid, invalid))
            _emit_feedback("DEBUG", "core:bom:utf16le", "UTF-16 LE BOM detected and validated", confidence=round(conf, 6))
            return DetectionResult(encoding=bom_encoding, confidence=conf, used_fallback=False, detected_by_bom=True)
        conf = min(0.49, calculate_transition_confidence(valid, invalid))
        _emit_feedback("WARNING", "core:bom:utf16le-invalid", "UTF-16 LE BOM detected but payload invalid", confidence=round(conf, 6))
        return DetectionResult(encoding=bom_encoding, confidence=conf, used_fallback=True, detected_by_bom=True)

    if bom_encoding == "utf-16-be":
        payload = data[2:]
        ok, valid, invalid = analyze_utf16_surrogate_pairs(payload, little_endian=False)
        if ok:
            conf = max(0.9, calculate_transition_confidence(valid, invalid))
            _emit_feedback("DEBUG", "core:bom:utf16be", "UTF-16 BE BOM detected and validated", confidence=round(conf, 6))
            return DetectionResult(encoding=bom_encoding, confidence=conf, used_fallback=False, detected_by_bom=True)
        conf = min(0.49, calculate_transition_confidence(valid, invalid))
        _emit_feedback("WARNING", "core:bom:utf16be-invalid", "UTF-16 BE BOM detected but payload invalid", confidence=round(conf, 6))
        return DetectionResult(encoding=bom_encoding, confidence=conf, used_fallback=True, detected_by_bom=True)

    if bom_encoding is not None:
        _emit_feedback("DEBUG", "core:bom", "BOM detected", encoding=bom_encoding)
        return DetectionResult(encoding=bom_encoding, confidence=1.0, used_fallback=False, detected_by_bom=True)

    if not data:
        _emit_feedback("DEBUG", "core:empty", "Empty payload, defaulting to utf-8")
        return DetectionResult(encoding="utf-8", confidence=1.0, used_fallback=False, detected_by_bom=False)

    esc_guess = probe_escape_sequence_encoding(data)
    if esc_guess is not None:
        _emit_feedback(
            "DEBUG",
            "core:escape",
            "Escape-sequence prober selected encoding",
            encoding=esc_guess[0],
            confidence=round(esc_guess[1], 6),
        )
        return DetectionResult(
            encoding=esc_guess[0],
            confidence=esc_guess[1],
            used_fallback=False,
            detected_by_bom=False,
        )

    utf8_ok, utf8_valid, utf8_invalid = analyze_utf8_dfa(data)
    if utf8_ok:
        conf = max(0.7, min(0.97, calculate_transition_confidence(utf8_valid, utf8_invalid)))
        _emit_feedback("DEBUG", "core:utf8", "UTF-8 DFA validation passed", confidence=round(conf, 6))
        return DetectionResult(encoding="utf-8", confidence=conf, used_fallback=False, detected_by_bom=False)
    _emit_feedback(
        "DEBUG",
        "core:utf8-invalid",
        "UTF-8 DFA validation failed",
        valid_transitions=utf8_valid,
        invalid_transitions=utf8_invalid,
    )

    has_high_bytes = any(byte >= 0x80 for byte in data)
    if has_high_bytes:
        multi_guess = probe_multi_byte_encoding(data)
        single_guess = probe_single_byte_encoding(data)
        candidates: list[tuple[str, float]] = []
        if multi_guess is not None:
            candidates.append(multi_guess)
        if single_guess is not None:
            candidates.append(single_guess)

        selected = _choose_by_language_fallback_map(candidates)
        if selected is None:
            _emit_feedback("WARNING", "core:fallback-empty", "No encoding candidate available, using fallback")
            return DetectionResult(encoding="utf-8", confidence=0.0, used_fallback=True, detected_by_bom=False)
        guessed_encoding, confidence = selected
        _emit_feedback(
            "DEBUG",
            "core:candidate-selected",
            "Candidate selected by probers/fallback map",
            encoding=guessed_encoding,
            confidence=round(confidence, 6),
            candidate_count=len(candidates),
        )
        return DetectionResult(
            encoding=guessed_encoding,
            confidence=confidence,
            used_fallback=False,
            detected_by_bom=False,
        )

    _emit_feedback("WARNING", "core:binary-fallback", "No high-byte signal, using utf-8 fallback")
    return DetectionResult(encoding="utf-8", confidence=0.0, used_fallback=True, detected_by_bom=False)


def detect_encoding(data: bytes) -> DetectionResult:
    """
    Detect encoding with early-exit logic.
    Stops after first 4KB when confidence is already above threshold.
    """
    if len(data) > _EARLY_EXIT_BYTES:
        _emit_feedback("DEBUG", "detect:early-exit-check", "Running early-exit precheck", size=len(data))
        prefix_result = _detect_encoding_core(data[:_EARLY_EXIT_BYTES])
        if prefix_result.confidence > _EARLY_EXIT_CONFIDENCE:
            _emit_feedback(
                "INFO",
                "detect:early-exit-hit",
                "Early-exit triggered",
                encoding=prefix_result.encoding,
                confidence=round(prefix_result.confidence, 6),
                threshold=_EARLY_EXIT_CONFIDENCE,
            )
            return prefix_result
        _emit_feedback(
            "DEBUG",
            "detect:early-exit-miss",
            "Early-exit threshold not reached; analyzing full payload",
            confidence=round(prefix_result.confidence, 6),
            threshold=_EARLY_EXIT_CONFIDENCE,
        )
    result = _detect_encoding_core(data)
    _emit_feedback(
        "INFO",
        "detect:final",
        "Detection finished",
        encoding=result.encoding,
        confidence=round(result.confidence, 6),
        used_fallback=result.used_fallback,
        detected_by_bom=result.detected_by_bom,
    )
    return result
