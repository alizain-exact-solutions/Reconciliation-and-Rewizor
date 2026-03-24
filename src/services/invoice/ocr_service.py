"""
Document Analyzer Processor
Uses OpenAI Vision API to extract and match invoice data.
"""

import os
import base64
import logging
import json
import re
from typing import Dict, Any, List
from openai import OpenAI
from PIL import Image
import fitz  # PyMuPDF
import io

from src.core.utils import normalize_amount, normalize_date

logger = logging.getLogger(__name__)

class DocumentAnalyzerProcessor:
    """Process and match tax invoices with account statements."""
    
    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.client = OpenAI(api_key=api_key, timeout=120.0, max_retries=3)  # 2 minute timeout, 3 retries
        self.model = "gpt-4o"
        
        
    def normalize_invoice_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize invoice fields to consistent formats."""
        normalized = dict(data)

        # Amounts: ensure positive and rounded to 2 decimals
        for amount_key in ["total_amount", "vat_amount", "gross_amount", "net_amount"]:
            normalized[amount_key] = normalize_amount(normalized.get(amount_key))

        # Date: standard YYYY-MM-DD
        normalized["date"] = normalize_date(normalized.get("date"))

        # Vendor: lowercase and collapse spaces
        vendor = normalized.get("vendor")
        if isinstance(vendor, str):
            normalized["vendor"] = self._collapse_spaces(vendor).lower()

        return normalized


# this data should be fetched from the Subiekt API
    def normalize_transaction_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize transaction fields to consistent formats."""
        normalized = dict(data)

        # Amounts: ensure positive and rounded to 2 decimals
        for amount_key in ["net_amount", "vat_amount", "gross_amount", "amount", "transactionAmount"]:
            if amount_key in normalized:
                normalized[amount_key] = normalize_amount(normalized.get(amount_key))

        # Date: standard YYYY-MM-DD
        for date_key in ["date", "book_date", "transactionOperationDate", "transactionBookingDate"]:
            if date_key in normalized:
                normalized[date_key] = normalize_date(normalized.get(date_key))

        # Operation title/description cleaning
        if isinstance(normalized.get("operation_title"), str):
            normalized["operation_title"] = self._clean_description(normalized["operation_title"])
        if isinstance(normalized.get("transactionDescription"), str):
            normalized["transactionDescription"] = self._clean_description(normalized["transactionDescription"])
        if isinstance(normalized.get("transactionPaymentDetails"), str):
            normalized["transactionPaymentDetails"] = self._clean_description(normalized["transactionPaymentDetails"])
        if isinstance(normalized.get("transactionPartnerAccountNo"), str):
            normalized["transactionPartnerAccountNo"] = self._collapse_spaces(normalized["transactionPartnerAccountNo"])

        # Clean vendor name from counterparty data or operation title or partner name
        vendor_source = (
            normalized.get("transactionPartnerName")
            or normalized.get("counterparty_data")
            or normalized.get("operation_title")
            or normalized.get("transactionDescription")
            or ""
        )
        if isinstance(vendor_source, str):
            clean_vendor = self._extract_vendor_name(vendor_source)
            if "transactionPartnerName" in normalized:
                normalized["transactionPartnerName"] = clean_vendor
            if "counterparty_data" in normalized:
                normalized["counterparty_data"] = clean_vendor

        return normalized


    def _collapse_spaces(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _clean_description(self, text: str) -> str:
        cleaned = self._collapse_spaces(text)
        # Remove redundant punctuation spacing
        cleaned = re.sub(r"\s*([,;:])\s*", r"\1 ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _extract_vendor_name(self, text: str) -> str:
        cleaned = self._collapse_spaces(text).lower()

        # Drop numeric-heavy trailing fragments (e.g., "048583 702")
        cleaned = re.sub(r"\s+\d[\d\s-]*$", "", cleaned)

        # Remove common transaction markers that do not belong to vendor names
        cleaned = re.sub(r"\b(visa|mastercard|mc|debit|card|payment|transaction)\b", "", cleaned)

        cleaned = self._collapse_spaces(cleaned)
        return cleaned
    

    def convert_pdf_to_image(self, pdf_path: str) -> str:
        """
        Convert PDF to image (first page only).
        Returns path to the generated image.
        """
        try:
            logger.info(f"Converting PDF to image: {pdf_path}")
            
            # Open PDF
            pdf_document = fitz.open(pdf_path)
            
            # Get first page
            page = pdf_document[0]
            
            # Render page to image (higher resolution for better OCR)
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            # Save as PNG
            image_path = pdf_path.replace('.pdf', '_page1.png')
            image.save(image_path, 'PNG')
            
            pdf_document.close()
            
            logger.info(f"PDF converted to image: {image_path}")
            return image_path
            
        except Exception as e:
            logger.error(f"Error converting PDF to image: {e}")
            raise
    
    def encode_image(self, image_path: str) -> str:
        """Encode image to base64."""
        # Check if it's a PDF
        if image_path.lower().endswith('.pdf'):
            image_path = self.convert_pdf_to_image(image_path)
        
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def analyze_tax_invoice(self, image_path: str) -> Dict[str, Any]:
        """
        Extract data from tax invoice using OpenAI Vision.
        
        Returns:
            {
                "invoice_number": str,
                "total_amount": float,
                "currency": str,
                "vat_amount": float,
                "gross_amount": float,
                "net_amount": float,
                "date": str,
                "vendor": str,
                "customer": str
            }
        """
        logger.info(f"Analyzing tax invoice: {image_path}")
        base64_image = self.encode_image(image_path)
        
        prompt = """
        Analyze this tax invoice and extract the following information in JSON format:
        
        {
            "invoice_number": "invoice number",
            "total_amount": numeric value,
            "currency": "currency code",
            "vat_amount": numeric VAT amount or null,
            "gross_amount": numeric gross amount,
            "net_amount": numeric net amount or null,
            "date": "YYYY-MM-DD",
            "vendor": "vendor name",
            "customer": "customer name"
        }
        
        Return ONLY valid JSON. Use null for missing fields.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0
            )
            
            result = response.choices[0].message.content
            # Extract JSON from markdown code blocks if present
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result)
            data = self.normalize_invoice_data(data)
            logger.info(f"Successfully extracted invoice data: {data.get('invoice_number')}")
            return data
            
        except Exception as e:
            logger.error(f"Error analyzing tax invoice: {e}")
            raise
    
    

