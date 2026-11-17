# apps/payments/services/ocr_service.py
import os
import re
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

# ✅ Tesseract setup
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Tesseract-OCR\tesseract.exe'
os.environ['TESSDATA_PREFIX'] = r'C:\Tesseract-OCR\tessdata'

logger = logging.getLogger(__name__)


class OCRService:
    """Extract UPI payment info from screenshot."""

    VALID_UPI_HANDLES = {
        'okhdfcbank', 'okicici', 'oksbi', 'okaxis', 'ybl', 'paytm',
        'apl', 'ibl', 'axl', 'upi', 'okbizaxis', 'mahb', 'fbl',
        'yapl', 'axisb', 'hdfcbank', 'icici', 'sbi', 'kotak',
        'yesbank', 'idfcbank', 'indus', 'federal', 'rbl',
    }

    # ✅ App detection map
    APP_MAP = {
        'phonepe': 'PhonePe',
        'phone pe': 'PhonePe',
        'paytm': 'Paytm',
        'googlepay': 'GooglePay',
        'google pay': 'GooglePay',
        'gpay': 'GooglePay',
        'bhim': 'BHIM',
        'amazonpay': 'AmazonPay',
        'amazon pay': 'AmazonPay',
        'cred': 'CRED',
    }

    @staticmethod
    def extract_from_image(image_path_or_file):
        """Extract data from image using Tesseract OCR."""
        raw_text = ''
        confidence = 0.0
        warnings = []

        try:
            from PIL import Image

            # ✅ Path dobara set karo (safety)
            pytesseract.pytesseract.tesseract_cmd = r'C:\Tesseract-OCR\tesseract.exe'
            os.environ['TESSDATA_PREFIX'] = r'C:\Tesseract-OCR\tessdata'

            # Image open karo
            img = Image.open(image_path_or_file)

            # ✅ OCR with confidence
            try:
                data = pytesseract.image_to_data(
                    img, output_type=pytesseract.Output.DICT
                )
                confs = [int(c) for c in data['conf'] if str(c) != '-1']
                confidence = (sum(confs) / len(confs) / 100) if confs else 0.0
            except Exception:
                confidence = 0.7

            # ✅ Main OCR text
            raw_text = pytesseract.image_to_string(img)

        except ImportError as e:
            logger.warning(f"Import error: {e}")
            warnings.append("OCR engine missing")
        except Exception as e:
            logger.exception(f"OCR failed: {e}")
            warnings.append(f"OCR error: {str(e)}")

        result = OCRService._parse_text(raw_text, confidence)
        result['warnings'] = warnings

        # Reset file pointer
        if hasattr(image_path_or_file, 'seek'):
            image_path_or_file.seek(0)

        return result

    @staticmethod
    def _parse_text(text, confidence):
        """Parse OCR text and extract fields."""
        result = {
            'raw_text': text,
            'confidence': confidence,
            'transaction_id': '',
            'amount': Decimal('0'),
            'payer_name': '',
            'payer_upi_id': '',
            'payment_date': None,
            'payment_time': None,
            'payment_app': '',
            'warnings': [],
        }

        if not text:
            return result

        # ═══════════════════════════════════════════
        # 1. UTR / TRANSACTION ID
        # ═══════════════════════════════════════════
        utr = ''

        # Pattern 1: "UTR: XXX" / "Txn ID: XXX" / "Ref No: XXX"
        utr_match = re.search(
            r'(?:UTR|Txn\s*ID|Transaction\s*ID|Ref\s*No|Reference\s*No)'
            r'[:\s#]*([A-Z0-9]{10,22})',
            text, re.I
        )
        if utr_match:
            utr = utr_match.group(1).upper()

        # Pattern 2: Alphanumeric with T prefix (PhonePe format)
        if not utr:
            utr_match = re.search(r'\b(T[A-Z0-9]{15,25})\b', text)
            if utr_match:
                utr = utr_match.group(1).upper()

        # Pattern 3: 12-digit number
        if not utr:
            utr_match = re.search(r'\b(\d{12})\b', text)
            if utr_match:
                utr = utr_match.group(1)

        result['transaction_id'] = utr

        # ═══════════════════════════════════════════
        # 2. AMOUNT — Multiple patterns
        # ═══════════════════════════════════════════
        amount = Decimal('0')

        # Pattern 1: ₹ / Rs / INR ke saath
        amount_match = re.search(
            r'(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)',
            text, re.I
        )
        if amount_match:
            try:
                amount = Decimal(amount_match.group(1).replace(',', ''))
            except InvalidOperation:
                pass

        # Pattern 2: "Amount" / "Paid" / "Total" ke baad
        if amount == Decimal('0'):
            amount_match = re.search(
                r'(?:Amount|Paid|Total|Pay)[:\s]*'
                r'([\d,]+(?:\.\d{1,2})?)',
                text, re.I
            )
            if amount_match:
                try:
                    amount = Decimal(amount_match.group(1).replace(',', ''))
                except InvalidOperation:
                    pass

        # Pattern 3: Lone numbers (₹1 jaise)
        if amount == Decimal('0'):
            for line in text.split('\n'):
                line = line.strip()
                # Skip lines with keywords
                if any(kw in line.lower() for kw in [
                    'utr', 'transaction', 'ref', 'txn', 'id',
                    'phone', 'upi', 'paid to', 'from',
                ]):
                    continue
                # Match standalone number
                m = re.match(r'^[₹Rs.]*\s*([\d,]+(?:\.\d{1,2})?)$', line)
                if m:
                    try:
                        val = Decimal(m.group(1).replace(',', ''))
                        if Decimal('1') <= val <= Decimal('100000'):
                            amount = val
                            break
                    except InvalidOperation:
                        continue

        # Pattern 4: "to" ke baad number
        if amount == Decimal('0'):
            amount_match = re.search(
                r'\bTo\b[^\d]*?([\d,]+(?:\.\d{1,2})?)',
                text, re.I
            )
            if amount_match:
                try:
                    val = Decimal(amount_match.group(1).replace(',', ''))
                    if Decimal('1') <= val <= Decimal('100000'):
                        amount = val
                except InvalidOperation:
                    pass

        result['amount'] = amount

        # ═══════════════════════════════════════════
        # 3. UPI ID
        # ═══════════════════════════════════════════
        upi_match = re.search(
            r'([a-zA-Z0-9.\-_]{2,})@([a-zA-Z]{2,})', text
        )
        if upi_match:
            result['payer_upi_id'] = upi_match.group(0).lower()

        # ═══════════════════════════════════════════
        # 4. DATE
        # ═══════════════════════════════════════════
        date_patterns = [
            (r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
             ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']),
            (r'(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})',
             ['%d %b %Y', '%d %B %Y']),
            (r'([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})',
             ['%b %d, %Y', '%B %d, %Y', '%b %d %Y']),
            (r'(\d{4}-\d{2}-\d{2})', ['%Y-%m-%d']),
        ]
        for pattern, formats in date_patterns:
            m = re.search(pattern, text)
            if m:
                for fmt in formats:
                    try:
                        result['payment_date'] = datetime.strptime(
                            m.group(1).strip(), fmt
                        ).date()
                        break
                    except ValueError:
                        continue
                if result['payment_date']:
                    break

        # ═══════════════════════════════════════════
        # 5. TIME
        # ═══════════════════════════════════════════
        time_match = re.search(
            r'(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?)', text, re.I
        )
        if time_match:
            time_str = time_match.group(1).strip().upper()
            for fmt in ('%I:%M %p', '%I:%M:%S %p', '%H:%M', '%H:%M:%S'):
                try:
                    result['payment_time'] = datetime.strptime(
                        time_str, fmt
                    ).time()
                    break
                except ValueError:
                    continue

        # ═══════════════════════════════════════════
        # 6. APP DETECTION
        # ═══════════════════════════════════════════
        text_lower = text.lower()
        for key, name in OCRService.APP_MAP.items():
            if key in text_lower:
                result['payment_app'] = name
                break

        # ═══════════════════════════════════════════
        # 7. PAYER NAME
        # ═══════════════════════════════════════════
        name_match = re.search(
            r'(?:Paid\s+to|To|From|Sender)[:\s]*\n?\s*'
            r'([A-Z][a-zA-Z\s.]{2,40})',
            text
        )
        if name_match:
            result['payer_name'] = name_match.group(1).strip()

        return result