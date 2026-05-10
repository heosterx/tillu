"""
TILLU Indian Rules Engine
=========================
Hard rules that apply to EVERY response TILLU generates.
These are non-negotiable — they override personality params.

Rules enforced:
  1. Currency    → Always INR (₹), never USD/EUR/GBP
  2. Time format → IST (UTC+5:30), 12-hour with AM/PM in Hindi style
  3. Date format → DD Month YYYY (Indian style), Hindi month names optional
  4. Dialect     → NCR-focused Hinglish (Delhi/Noida/Gurgaon register)
  5. Units       → km not miles, kg not lbs, °C not °F, lakh/crore not million/billion
  6. Language    → Hindi-first for casual, English for technical — never pure formal English

Location context: NCR (National Capital Region)
  → Delhi, Noida, Gurgaon, Faridabad, Ghaziabad
  → Local references: Metro, DTC, Yamuna, Connaught Place, etc.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

IST = ZoneInfo("Asia/Kolkata")

# ── Currency conversion patterns ─────────────────────────────────────────────

_USD_PATTERN = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_EUR_PATTERN = re.compile(r"€\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_GBP_PATTERN = re.compile(r"£\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_MILLION_PATTERN = re.compile(r"([\d,]+(?:\.\d+)?)\s*million", re.IGNORECASE)
_BILLION_PATTERN = re.compile(r"([\d,]+(?:\.\d+)?)\s*billion", re.IGNORECASE)
_TRILLION_PATTERN = re.compile(r"([\d,]+(?:\.\d+)?)\s*trillion", re.IGNORECASE)

# Approximate rates (update via config/env in production)
USD_TO_INR = 93.5
EUR_TO_INR = 90.0
GBP_TO_INR = 105.0


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _inr_format(amount: float) -> str:
    """Format amount in Indian number system (lakh/crore)."""
    if amount >= 1_00_00_000:  # 1 crore
        crore = amount / 1_00_00_000
        if crore == int(crore):
            return f"₹{int(crore)} करोड़"
        return f"₹{crore:.1f} करोड़"
    if amount >= 1_00_000:  # 1 lakh
        lakh = amount / 1_00_000
        if lakh == int(lakh):
            return f"₹{int(lakh)} लाख"
        return f"₹{lakh:.1f} लाख"
    if amount >= 1_000:
        return f"₹{amount:,.0f}"
    return f"₹{amount:.0f}"


def normalize_currency(text: str) -> str:
    """Replace foreign currency symbols with INR equivalents."""
    # $X → ₹X (INR)
    def replace_usd(m: re.Match) -> str:
        inr = _num(m.group(1)) * USD_TO_INR
        return _inr_format(inr)

    def replace_eur(m: re.Match) -> str:
        inr = _num(m.group(1)) * EUR_TO_INR
        return _inr_format(inr)

    def replace_gbp(m: re.Match) -> str:
        inr = _num(m.group(1)) * GBP_TO_INR
        return _inr_format(inr)

    def replace_million(m: re.Match) -> str:
        val = _num(m.group(1)) * 1_000_000
        return _inr_format(val)  # treat as INR millions → lakh/crore

    def replace_billion(m: re.Match) -> str:
        val = _num(m.group(1)) * 1_000_000_000
        return _inr_format(val)

    def replace_trillion(m: re.Match) -> str:
        val = _num(m.group(1)) * 1_000_000_000_000
        return _inr_format(val)

    text = _USD_PATTERN.sub(replace_usd, text)
    text = _EUR_PATTERN.sub(replace_eur, text)
    text = _GBP_PATTERN.sub(replace_gbp, text)
    text = _MILLION_PATTERN.sub(replace_million, text)
    text = _BILLION_PATTERN.sub(replace_billion, text)
    text = _TRILLION_PATTERN.sub(replace_trillion, text)
    return text


# ── Time / Date formatting ────────────────────────────────────────────────────

HINDI_MONTHS = {
    1: "जनवरी", 2: "फ़रवरी", 3: "मार्च", 4: "अप्रैल",
    5: "मई", 6: "जून", 7: "जुलाई", 8: "अगस्त",
    9: "सितंबर", 10: "अक्टूबर", 11: "नवंबर", 12: "दिसंबर",
}

HINDI_DAYS = {
    0: "सोमवार", 1: "मंगलवार", 2: "बुधवार", 3: "गुरुवार",
    4: "शुक्रवार", 5: "शनिवार", 6: "रविवार",
}


def now_ist() -> datetime:
    """Current datetime in IST."""
    return datetime.now(IST)


def format_time_ist(dt: datetime | None = None) -> str:
    """
    Format time in IST, 12-hour with Hindi AM/PM style.
    e.g. "रात 11:45 बजे" / "सुबह 7:30 बजे"
    """
    if dt is None:
        dt = now_ist()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)

    hour = dt.hour
    minute = dt.minute

    # Hindi time-of-day prefix
    if 5 <= hour < 12:
        prefix = "सुबह"
    elif 12 <= hour < 17:
        prefix = "दोपहर"
    elif 17 <= hour < 21:
        prefix = "शाम"
    else:
        prefix = "रात"

    # 12-hour conversion
    h12 = hour % 12 or 12
    time_str = f"{h12}:{minute:02d}"
    return f"{prefix} {time_str} बजे"


def format_date_indian(dt: datetime | None = None, hindi_month: bool = True) -> str:
    """
    Format date in Indian style: DD Month YYYY
    e.g. "9 मई 2026" or "9 May 2026"
    """
    if dt is None:
        dt = now_ist()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)

    month = HINDI_MONTHS[dt.month] if hindi_month else dt.strftime("%B")
    return f"{dt.day} {month} {dt.year}"


def format_datetime_full(dt: datetime | None = None) -> str:
    """Full IST datetime: 'शनिवार, 9 मई 2026, शाम 7:30 बजे'"""
    if dt is None:
        dt = now_ist()
    day_name = HINDI_DAYS[dt.weekday()]
    date_str = format_date_indian(dt)
    time_str = format_time_ist(dt)
    return f"{day_name}, {date_str}, {time_str}"


# ── Unit normalization ────────────────────────────────────────────────────────

_MILES_PATTERN = re.compile(r"([\d.]+)\s*miles?", re.IGNORECASE)
_LBS_PATTERN = re.compile(r"([\d.]+)\s*(?:lbs?|pounds?)", re.IGNORECASE)
_FAHRENHEIT_PATTERN = re.compile(r"([\d.]+)\s*°?F\b")


def normalize_units(text: str) -> str:
    """Convert imperial units to metric/Indian standard."""
    def miles_to_km(m: re.Match) -> str:
        km = float(m.group(1)) * 1.609
        return f"{km:.1f} km"

    def lbs_to_kg(m: re.Match) -> str:
        kg = float(m.group(1)) * 0.453
        return f"{kg:.1f} kg"

    def f_to_c(m: re.Match) -> str:
        c = (float(m.group(1)) - 32) * 5 / 9
        return f"{c:.1f}°C"

    text = _MILES_PATTERN.sub(miles_to_km, text)
    text = _LBS_PATTERN.sub(lbs_to_kg, text)
    text = _FAHRENHEIT_PATTERN.sub(f_to_c, text)
    return text


# ── NCR dialect vocabulary ────────────────────────────────────────────────────

# Common NCR Hinglish substitutions for overly formal English phrases
_NCR_SUBSTITUTIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bI am unable to\b", re.I), "main nahi kar sakta"),
    (re.compile(r"\bplease note that\b", re.I), "sun"),
    (re.compile(r"\bkindly\b", re.I), "please"),
    (re.compile(r"\bfurthermore\b", re.I), "aur bhi"),
    (re.compile(r"\bnevertheless\b", re.I), "phir bhi"),
    (re.compile(r"\bconsequently\b", re.I), "toh"),
    (re.compile(r"\bsubsequently\b", re.I), "uske baad"),
    (re.compile(r"\bpresently\b", re.I), "abhi"),
    (re.compile(r"\bI would like to inform you\b", re.I), "bata deta hoon"),
    (re.compile(r"\bAs per your request\b", re.I), "tune jo maanga tha"),
]


def apply_ncr_dialect(text: str) -> str:
    """
    Lightly apply NCR Hinglish register.
    Only replaces overly formal English phrases — does not force Hindi.
    """
    for pattern, replacement in _NCR_SUBSTITUTIONS:
        text = pattern.sub(replacement, text)
    return text


# ── Master apply function ─────────────────────────────────────────────────────

def apply_all_rules(text: str, apply_dialect: bool = True) -> str:
    """
    Apply all Indian rules to a response text.
    Call this on every TILLU response before delivery.

    Args:
        text: Raw LLM response
        apply_dialect: Whether to apply NCR dialect substitutions

    Returns:
        Rule-compliant response text
    """
    text = normalize_currency(text)
    text = normalize_units(text)
    if apply_dialect:
        text = apply_ncr_dialect(text)
    return text


# ── System prompt injection ───────────────────────────────────────────────────

INDIAN_RULES_SYSTEM_PROMPT = """
## TILLU — Indian Rules (Non-Negotiable)

You are TILLU, a personal AI for an Indian user based in NCR (Delhi/Noida/Gurgaon area).

### Currency Rules
- ALWAYS use ₹ (Indian Rupee) for all money values
- Use Indian number system: लाख (1,00,000), करोड़ (1,00,00,000)
- Never use $, €, £, or "million/billion" — convert to ₹ lakh/crore
- Example: "₹50 लाख" not "$60,000"

### Time & Date Rules
- ALWAYS use IST (Indian Standard Time, UTC+5:30)
- Use 12-hour format with Hindi time-of-day: सुबह/दोपहर/शाम/रात
- Date format: DD Month YYYY (e.g., "9 मई 2026")
- Never say "EST", "PST", "UTC" — always convert to IST

### Language & Dialect Rules
- You speak NCR Hinglish — natural mix of Hindi and English
- Casual conversation: lean Hindi (Dilli/Noida register)
- Technical topics: English terms are fine, but sentence structure stays Hinglish
- Never use overly formal British English phrases
- Local references: Delhi Metro, DTC bus, Yamuna, CP (Connaught Place), Sector routes

### Units
- Distance: km (not miles)
- Weight: kg (not lbs)
- Temperature: °C (not °F)

### Tone
- You are talking to a young Indian man from NCR
- Be direct, slightly casual, like a smart friend — not a corporate assistant
- Use "yaar", "bhai", "sun" naturally when appropriate
- Avoid "Dear User", "I hope this helps", "Please feel free to"
"""


def get_rules_prompt() -> str:
    """Return the Indian rules system prompt to inject into every chain."""
    return INDIAN_RULES_SYSTEM_PROMPT.strip()


def get_current_ist_context() -> dict[str, str]:
    """Return current IST time context for injection into prompts."""
    now = now_ist()
    return {
        "current_time_ist": format_time_ist(now),
        "current_date_indian": format_date_indian(now),
        "current_datetime_full": format_datetime_full(now),
        "day_of_week_hindi": HINDI_DAYS[now.weekday()],
        "timezone": "IST (UTC+5:30)",
    }
