"""Transaction categorization for VAT exclusions and alerts."""

import os
from typing import Dict, Iterable, List, Set


def _load_keywords(env_name: str, defaults: Iterable[str]) -> List[str]:
    raw = os.getenv(env_name, "")
    if raw.strip():
        return [item.strip().lower() for item in raw.split(",") if item.strip()]
    return [item.lower() for item in defaults]


DEFAULT_KEYWORDS: Dict[str, List[str]] = {
    "fx_conversion": ["fx", "forex", "exchange", "conversion"],
    "bank_fee": ["bank fee", "fee", "charge", "commission"],
    "internal_transfer": ["internal transfer", "own account", "between accounts"],
    "salary": ["salary", "payroll", "wages"],
    "tax_zus": ["zus", "tax", "social insurance"],
    "customer_payment": ["customer payment", "payment received", "incoming transfer", "credit"],
}


def _combined_text(transaction: Dict[str, object]) -> str:
    parts = [
        str(transaction.get("description") or ""),
        str(transaction.get("payment_details") or ""),
        str(transaction.get("partner_name") or ""),
        str(transaction.get("ref_number") or ""),
    ]
    return " | ".join(parts).lower()


def categorize_transaction(transaction: Dict[str, object]) -> Set[str]:
    """Return a set of category names for a transaction."""
    text = _combined_text(transaction)
    categories: Set[str] = set()

    for category, defaults in DEFAULT_KEYWORDS.items():
        keywords = _load_keywords(f"VAT_EXCLUDE_{category.upper()}_KEYWORDS", defaults)
        if any(keyword in text for keyword in keywords):
            categories.add(category)

    return categories


def is_vat_excluded(transaction: Dict[str, object]) -> bool:
    return bool(categorize_transaction(transaction))
