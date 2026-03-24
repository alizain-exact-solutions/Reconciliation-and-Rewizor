"""Matching engine for bank statement reconciliation."""

import logging
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MatchingEngine:
    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None

        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _normalize_text(value: Optional[str]) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _fuzzy_ratio(left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        return SequenceMatcher(None, left, right).ratio()

    def match_invoices(
        self,
        tax_invoices: List[Dict],
        statement_transactions: List[Dict],
    ) -> Dict[str, Any]:
        """Match tax invoices with account statement transactions."""
        logger.info(
            "Matching %s invoices with %s transactions",
            len(tax_invoices),
            len(statement_transactions),
        )

        matches = []
        matched_count = 0
        unmatched_count = 0
        discrepancy_count = 0

        for invoice in tax_invoices:
            invoice_number = invoice.get("invoice_number") or "Unknown"
            invoice_amount = invoice.get("gross_amount") or invoice.get("total_amount", 0)
            invoice_net = invoice.get("net_amount")
            invoice_vat = invoice.get("vat_amount")
            currency = invoice.get("currency", "PLN")
            vendor = invoice.get("vendor", "")

            logger.info(
                "Processing invoice: %s, gross: %s, net: %s, VAT: %s",
                invoice_number,
                invoice_amount,
                invoice_net,
                invoice_vat,
            )

            if not invoice_number or invoice_number == "Unknown":
                logger.warning("Invoice number not found in document, skipping")
                matches.append(
                    {
                        "status": "unmatched",
                        "invoice_number": "N/A",
                        "vendor": vendor,
                        "invoice_net": invoice_net,
                        "invoice_vat": invoice_vat,
                        "tax_invoice_amount": invoice_amount,
                        "statement_amount": None,
                        "statement_net": None,
                        "vat_amount": None,
                        "difference": None,
                        "currency": currency,
                        "statement_date": None,
                        "operation_title": None,
                        "invoice_reference": None,
                        "book_date": None,
                        "transaction_number": None,
                        "counterparty_data": None,
                        "statement_transaction_amount": None,
                        "notes": "Invoice number not found in document",
                    }
                )
                unmatched_count += 1
                continue

            found_transaction = None
            candidates = []
            invoice_num_upper = invoice_number.upper()
            invoice_date = self._parse_date(invoice.get("date"))
            vendor_text = self._normalize_text(vendor)

            for transaction in statement_transactions:
                operation_title = (transaction.get("operation_title") or "").upper()
                invoice_ref = (transaction.get("invoice_reference") or "").upper()

                if invoice_num_upper in operation_title or invoice_num_upper == invoice_ref:
                    candidates.append(transaction)

            if not candidates:
                for transaction in statement_transactions:
                    transaction_amount = transaction.get("gross_amount")
                    if transaction_amount is None:
                        transaction_amount = transaction.get("amount", 0)
                    if abs(abs(invoice_amount) - abs(transaction_amount)) < 0.5:
                        candidates.append(transaction)

            if candidates:
                def _candidate_key(transaction: Dict[str, Any]) -> tuple:
                    candidate_date = self._parse_date(
                        transaction.get("date") or transaction.get("book_date")
                    )
                    date_diff = (
                        abs((invoice_date - candidate_date).days)
                        if invoice_date and candidate_date
                        else 9999
                    )
                    candidate_vendor = self._normalize_text(
                        transaction.get("transaction_partner_name")
                        or transaction.get("description")
                        or transaction.get("operation_title")
                    )
                    vendor_similarity = self._fuzzy_ratio(vendor_text, candidate_vendor)
                    return (date_diff, -vendor_similarity)

                found_transaction = min(candidates, key=_candidate_key)
                logger.info(
                    "Match found! Invoice %s matched with transaction: %s",
                    invoice_number,
                    (found_transaction.get("operation_title") or "")[:50],
                )

            if not found_transaction:
                logger.warning("No match found for invoice %s", invoice_number)
                matches.append(
                    {
                        "status": "unmatched",
                        "invoice_number": invoice_number,
                        "vendor": vendor,
                        "invoice_net": invoice_net,
                        "invoice_vat": invoice_vat,
                        "tax_invoice_amount": invoice_amount,
                        "statement_amount": None,
                        "statement_net": None,
                        "vat_amount": None,
                        "difference": None,
                        "currency": currency,
                        "statement_date": None,
                        "operation_title": None,
                        "invoice_reference": None,
                        "book_date": None,
                        "transaction_number": None,
                        "counterparty_data": None,
                        "statement_transaction_amount": None,
                        "notes": "Invoice not found in account statement",
                    }
                )
                unmatched_count += 1
                continue

            statement_amount = found_transaction.get("gross_amount", 0)
            statement_net = found_transaction.get("net_amount", 0)
            vat_amount = found_transaction.get("vat_amount", 0)
            statement_currency = found_transaction.get("currency", currency)
            statement_date = found_transaction.get("date", "")
            operation_title = found_transaction.get("operation_title", "")
            invoice_reference = found_transaction.get("invoice_reference", "")
            book_date = found_transaction.get("book_date", "")
            transaction_number = found_transaction.get("transaction_number", "")
            counterparty_data = found_transaction.get("counterparty_data", "")
            statement_transaction_amount = found_transaction.get("gross_amount")
            if statement_transaction_amount is None:
                statement_transaction_amount = found_transaction.get("amount", 0)
            difference = abs(abs(invoice_amount) - abs(statement_transaction_amount))

            score = 0
            score_notes = []

            # Amount match: 50 points, strict or within rounding tolerance (abs diff < 0.5)
            if abs(invoice_amount) == abs(statement_transaction_amount):
                score += 50
                score_notes.append("Amount exact")
            elif difference < 0.5:
                score += 50
                score_notes.append("Amount within rounding tolerance")
            else:
                score_notes.append(f"Amount mismatch ({difference:.2f})")

            # Date match: 20 points, invoice date vs transaction date or booking date within 1-3 days
            invoice_date = self._parse_date(invoice.get("date"))
            transaction_date = self._parse_date(statement_date) or self._parse_date(book_date)
            if invoice_date and transaction_date:
                day_diff = abs((invoice_date - transaction_date).days)
                if day_diff <= 3:
                    score += 20
                    score_notes.append(f"Date within {day_diff} days")
                else:
                    score_notes.append(f"Date mismatch ({day_diff} days)")
            else:
                score_notes.append("Date missing")

            # Vendor match: 20 points, include or fuzzy match
            vendor_text = self._normalize_text(vendor)
            transaction_text = self._normalize_text(
                found_transaction.get("transaction_partner_name")
                or found_transaction.get("description")
                or operation_title
            )
            if vendor_text and transaction_text:
                if vendor_text in transaction_text:
                    score += 20
                    score_notes.append("Vendor included")
                elif self._fuzzy_ratio(vendor_text, transaction_text) >= 0.8:
                    score += 20
                    score_notes.append("Vendor fuzzy match")
                else:
                    score_notes.append("Vendor mismatch")
            else:
                score_notes.append("Vendor missing")

            # Currency match: 10 points
            if currency and statement_currency:
                if currency == statement_currency:
                    score += 10
                    score_notes.append("Currency match")
                else:
                    score_notes.append("Currency mismatch")

            if score >= 80:
                confidence = "high"
                status = "matched"
                matched_count += 1
            elif score >= 60:
                confidence = "medium"
                status = "discrepancy"
                discrepancy_count += 1
            else:
                confidence = "low"
                status = "unmatched"
                unmatched_count += 1

            notes = "; ".join(score_notes)

            matches.append(
                {
                    "status": status,
                    "invoice_number": invoice_number,
                    "vendor": vendor,
                    "invoice_net": invoice_net,
                    "invoice_vat": invoice_vat,
                    "tax_invoice_amount": invoice_amount,
                    "statement_amount": statement_amount,
                    "statement_net": statement_net,
                    "vat_amount": vat_amount,
                    "difference": difference,
                    "currency": statement_currency,
                    "statement_date": statement_date,
                    "operation_title": operation_title,
                    "invoice_reference": invoice_reference,
                    "book_date": book_date,
                    "transaction_number": transaction_number,
                    "counterparty_data": counterparty_data,
                    "statement_transaction_amount": statement_transaction_amount,
                    "score": score,
                    "confidence": confidence,
                    "notes": notes,
                }
            )

        result = {
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
            "discrepancy_count": discrepancy_count,
            "total_count": len(tax_invoices),
            "matches": matches,
        }

        logger.info(
            "Matching complete: %s matched, %s unmatched, %s discrepancies",
            matched_count,
            unmatched_count,
            discrepancy_count,
        )
        return result
