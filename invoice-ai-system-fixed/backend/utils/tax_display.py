"""
Country-Aware Tax Display Utility
----------------------------------
Single source of truth for how tax is labeled, formatted, and cross-checked
per country. Nothing outside this module should hardcode "VAT", "GST",
"CGST", "SGST", "IGST", or "Sales Tax" strings — always go through
get_tax_display() / build_tax_metadata() so the logic stays in one place.

Backward compatible: if country/currency can't be determined, everything
falls back to the generic label "Tax", exactly like the system's original
behavior.
"""

import re
from typing import Optional, Dict, Any

# ──────────────────────────────────────────────
# Country <-> currency / registration-number mapping
# ──────────────────────────────────────────────

CURRENCY_COUNTRY_MAP = {
    "AED": "UAE",
    "INR": "India",
    "USD": "USA",
}

# GSTIN: 2 digit state code + 10 char PAN + 1 entity code + 1 'Z' + 1 checksum
GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]$")

# UAE VAT TRN: 15 numeric digits (commonly formatted, digits-only stored here)
UAE_TRN_PATTERN = re.compile(r"^\d{15}$")

# Official GST 2.0 slabs (effective 22 Sept 2025 onward). Kept here, not
# scattered, so future rate changes only need updating in one place.
INDIA_GST_RATES = {0, 5, 18, 40}
UAE_VAT_STANDARD_RATE = 5
GST_RATE_CUTOVER_DATE = "2025-09-22"


def _extract_gstin_state_code(gstin: Optional[str]) -> Optional[str]:
    if not gstin or not GSTIN_PATTERN.match(gstin.strip().upper()):
        return None
    return gstin.strip().upper()[:2]


def detect_country(
    currency: Optional[str] = None,
    vendor_gstin: Optional[str] = None,
    vendor_vat: Optional[str] = None,
    invoice_country: Optional[str] = None,
    vendor_country: Optional[str] = None,
    buyer_country: Optional[str] = None,
) -> Optional[str]:
    """
    Country detection priority (per spec):
    1. Explicit invoice country field
    2. Vendor country
    3. Buyer country
    4. Currency (AED->UAE, INR->India, USD->USA)
    5. Tax registration number shape (GSTIN->India, TRN->UAE)
    """
    for explicit in (invoice_country, vendor_country, buyer_country):
        if explicit:
            normalized = explicit.strip().title()
            if normalized in ("Uae", "U.A.E", "United Arab Emirates"):
                return "UAE"
            if normalized in ("India", "In"):
                return "India"
            if normalized in ("Usa", "U.S.A", "United States", "United States Of America"):
                return "USA"
            return normalized

    if currency:
        mapped = CURRENCY_COUNTRY_MAP.get(currency.strip().upper())
        if mapped:
            return mapped

    if vendor_gstin and GSTIN_PATTERN.match(vendor_gstin.strip().upper()):
        return "India"

    if vendor_vat and UAE_TRN_PATTERN.match(vendor_vat.strip()):
        return "UAE"

    return None


def determine_gst_type(vendor_gstin: Optional[str], buyer_gstin: Optional[str]) -> str:
    """
    Returns one of: "CGST_SGST", "IGST", "GST" (undetermined).
    Based on comparing the 2-digit state codes embedded in each GSTIN.
    """
    vendor_state = _extract_gstin_state_code(vendor_gstin)
    buyer_state = _extract_gstin_state_code(buyer_gstin)

    if not vendor_state or not buyer_state:
        return "GST"  # not enough info to tell intra vs inter-state

    return "CGST_SGST" if vendor_state == buyer_state else "IGST"


def compute_effective_rate(subtotal: Optional[float], tax_amount: Optional[float]) -> Optional[float]:
    if not subtotal or subtotal <= 0 or tax_amount is None:
        return None
    return round((tax_amount / subtotal) * 100, 1)


def _nearest_slab(rate: Optional[float], slabs: set, tolerance: float = 0.75) -> Optional[float]:
    if rate is None:
        return None
    closest = min(slabs, key=lambda s: abs(s - rate))
    return closest if abs(closest - rate) <= tolerance else None


def get_tax_display(
    country: Optional[str],
    currency: Optional[str],
    tax_type: Optional[str],
    tax_rate: Optional[float],
) -> Dict[str, Any]:
    """
    Pure formatting function. Returns:
        {"label": "...", "rate": "...", "display": "..."}

    tax_type for India should be one of "CGST_SGST", "IGST", "GST".
    For UAE/USA, tax_type is not used for label selection (there's only one
    tax name each) but is accepted for interface consistency.
    """
    rate_str = f"{tax_rate:g}%" if tax_rate is not None else None

    if country == "UAE":
        label = "VAT"
        display = f"VAT ({rate_str})" if rate_str else "VAT"
        return {"label": label, "rate": rate_str, "display": display}

    if country == "India":
        if tax_type == "CGST_SGST":
            half_rate = round(tax_rate / 2, 1) if tax_rate is not None else None
            half_rate_str = f"{half_rate:g}%" if half_rate is not None else None
            label = "CGST + SGST"
            display = (
                f"CGST ({half_rate_str}) + SGST ({half_rate_str})"
                if half_rate_str
                else "CGST + SGST"
            )
            return {"label": label, "rate": half_rate_str, "display": display}
        if tax_type == "IGST":
            label = "IGST"
            display = f"IGST ({rate_str})" if rate_str else "IGST"
            return {"label": label, "rate": rate_str, "display": display}
        # Undetermined intra/inter-state, or rate unknown -> generic GST
        label = "GST"
        display = f"GST ({rate_str})" if rate_str else "GST"
        return {"label": label, "rate": rate_str, "display": display}

    if country == "USA":
        label = "Sales Tax"
        display = f"Sales Tax ({rate_str})" if rate_str else "Sales Tax"
        return {"label": label, "rate": rate_str, "display": display}

    # Fallback for unsupported / undetermined countries
    return {"label": "Tax", "rate": rate_str, "display": f"Tax ({rate_str})" if rate_str else "Tax"}


def get_tax_registration_number(
    country: Optional[str],
    vendor_gstin: Optional[str] = None,
    vendor_vat: Optional[str] = None,
    vendor_ein: Optional[str] = None,
) -> Optional[str]:
    """Returns the relevant tax registration number for the detected country, if any."""
    if country == "India":
        return vendor_gstin or None
    if country == "UAE":
        return vendor_vat or None
    if country == "USA":
        return vendor_ein or None
    return None


def check_country_tax_consistency(country: Optional[str], tax_type_label: str) -> Optional[str]:
    """
    Returns a human-readable warning string if the tax label doesn't match
    the detected country, or None if consistent / undetermined.
    Never raises — this is a soft validation warning only.
    """
    if not country:
        return None

    allowed = {
        "UAE": {"VAT"},
        "India": {"GST", "CGST", "SGST", "IGST", "CGST + SGST"},
        "USA": {"Sales Tax"},
    }
    if country not in allowed:
        return None

    if tax_type_label not in allowed[country]:
        return f"Tax type does not match detected country. Country={country}, Tax={tax_type_label}"
    return None


def check_amount_discrepancy(
    subtotal: Optional[float],
    tax_amount: Optional[float],
    total_amount: Optional[float],
    tolerance: float = 0.01,
) -> Dict[str, Any]:
    """
    Compares subtotal + tax against the stated total.
    Returns a report dict — always, even when there's no mismatch — so it
    can be dropped straight into an export/report row.
    """
    if subtotal is None or tax_amount is None or total_amount is None:
        return {
            "checked": False,
            "mismatch": False,
            "expected_total": None,
            "actual_total": total_amount,
            "difference": None,
            "note": "Insufficient data to verify (missing subtotal, tax, or total).",
        }

    expected_total = round(subtotal + tax_amount, 2)
    difference = round(total_amount - expected_total, 2)
    mismatch = abs(difference) > tolerance

    return {
        "checked": True,
        "mismatch": mismatch,
        "expected_total": expected_total,
        "actual_total": round(total_amount, 2),
        "difference": difference,
        "note": (
            f"Total does not match subtotal + tax (off by {difference:+.2f})."
            if mismatch
            else "Amounts reconcile correctly."
        ),
    }


def build_tax_metadata(
    currency: Optional[str] = None,
    subtotal: Optional[float] = None,
    tax_amount: Optional[float] = None,
    total_amount: Optional[float] = None,
    vendor_gstin: Optional[str] = None,
    buyer_gstin: Optional[str] = None,
    vendor_vat: Optional[str] = None,
    vendor_ein: Optional[str] = None,
    invoice_date: Optional[str] = None,
    invoice_country: Optional[str] = None,
    vendor_country: Optional[str] = None,
    buyer_country: Optional[str] = None,
) -> Dict[str, Any]:
    """
    One-call convenience function: detects country, determines tax type,
    computes the effective rate, formats the display label, fetches the
    registration number, checks country/tax consistency, and checks the
    subtotal+tax vs total arithmetic — all in one dict.

    This is the function extraction/validation/reports/RAG should all call
    instead of re-implementing any of this logic themselves.
    """
    country = detect_country(
        currency=currency,
        vendor_gstin=vendor_gstin,
        vendor_vat=vendor_vat,
        invoice_country=invoice_country,
        vendor_country=vendor_country,
        buyer_country=buyer_country,
    )

    tax_type = None
    if country == "India":
        tax_type = determine_gst_type(vendor_gstin, buyer_gstin)

    effective_rate = compute_effective_rate(subtotal, tax_amount)

    rate_for_display = effective_rate
    slab_warning = None
    if country == "India" and effective_rate is not None:
        # Only enforce the GST 2.0 slab set for invoices dated on/after the
        # cutover date; older invoices may legitimately use retired rates.
        applies_new_slabs = (not invoice_date) or (str(invoice_date) >= GST_RATE_CUTOVER_DATE)
        if applies_new_slabs:
            snapped = _nearest_slab(effective_rate, INDIA_GST_RATES)
            if snapped is None:
                slab_warning = (
                    f"Effective GST rate ({effective_rate}%) does not match a current "
                    f"GST 2.0 slab (0/5/18/40%)."
                )
            else:
                rate_for_display = snapped
    elif country == "UAE" and effective_rate is not None:
        snapped = _nearest_slab(effective_rate, {0, UAE_VAT_STANDARD_RATE}, tolerance=0.5)
        if snapped is not None:
            rate_for_display = snapped

    display = get_tax_display(country, currency, tax_type, rate_for_display)
    registration_number = get_tax_registration_number(country, vendor_gstin, vendor_vat, vendor_ein)
    consistency_warning = check_country_tax_consistency(country, display["label"])
    amount_check = check_amount_discrepancy(subtotal, tax_amount, total_amount)

    warnings = [w for w in (slab_warning, consistency_warning) if w]

    return {
        "country": country,
        "currency": currency,
        "tax_type": tax_type,
        "tax_name": display["label"],
        "tax_rate": rate_for_display,
        "tax_amount": tax_amount,
        "tax_display": display["display"],
        "tax_registration_number": registration_number,
        "warnings": warnings,
        "amount_check": amount_check,
    }
