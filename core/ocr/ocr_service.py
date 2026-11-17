# core/ocr/ocr_service.py

import os
import re
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.conf import settings

logger = logging.getLogger(__name__)


class OCRService:
    """
    Google Cloud Vision OCR Service
    ================================
    - High accuracy (95-99%)
    - Supports images (JPG, PNG, WEBP) + PDFs
    - Auto parse: UTR, amount, UPI, date, time, app
    
    Usage:
        result = OCRService.extract_from_image(image_bytes)
        result = OCRService.extract_from_pdf(pdf_bytes)
    """

    _client = None

    # ═══════════════════════════════════════════════════════════
    # CLIENT INIT
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def _get_client(cls):
        """Lazy init Google Vision client"""
        if cls._client is None:
            try:
                from google.cloud import vision

                key_path = getattr(
                    settings,
                    'GOOGLE_VISION_KEY_PATH',
                    os.path.join(
                        settings.BASE_DIR, 'google-vision-key.json'
                    ),
                )

                if not os.path.exists(key_path):
                    raise Exception(
                        f'Google Vision key not found: {key_path}'
                    )

                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_path
                cls._client = vision.ImageAnnotatorClient()

                logger.info('✅ Google Vision client initialized')
            except Exception as e:
                logger.exception(f'❌ Google Vision init error: {e}')
                raise

        return cls._client

    # ═══════════════════════════════════════════════════════════
    # MAIN — EXTRACT FROM IMAGE
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def extract_from_image(cls, image_input):
        """
        Image se text extract karo.

        Args:
            image_input: str (file path) OR bytes

        Returns: dict with parsed data
        """
        raw_text = ''
        confidence = 0.0

        try:
            from google.cloud import vision

            # Read bytes if path
            if isinstance(image_input, str):
                with open(image_input, 'rb') as f:
                    image_bytes = f.read()
            else:
                image_bytes = image_input

            client = cls._get_client()
            image = vision.Image(content=image_bytes)

            # DOCUMENT_TEXT_DETECTION — best for screenshots
            response = client.document_text_detection(image=image)

            if response.error.message:
                raise Exception(response.error.message)

            raw_text = response.full_text_annotation.text
            confidence = cls._calculate_confidence(response)

            logger.info(
                f'✅ OCR done: {len(raw_text)} chars, '
                f'confidence={confidence:.2f}'
            )

        except Exception as e:
            logger.exception(f'OCR error: {e}')
            return cls._empty_result(raw_text='', confidence=0.0)

        return cls._parse_text(raw_text, confidence)

    # ═══════════════════════════════════════════════════════════
    # MAIN — EXTRACT FROM PDF
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def extract_from_pdf(cls, pdf_input):
        """
        PDF se text extract karo (images mein convert karke).
        """
        try:
            from pdf2image import convert_from_bytes, convert_from_path

            # Read PDF
            if isinstance(pdf_input, str):
                images = convert_from_path(pdf_input, dpi=200)
            else:
                images = convert_from_bytes(pdf_input, dpi=200)

            all_text = []
            total_conf = 0
            count = 0

            for img in images:
                buf = BytesIO()
                img.save(buf, format='PNG')
                img_bytes = buf.getvalue()

                result = cls.extract_from_image(img_bytes)
                if result['raw_text']:
                    all_text.append(result['raw_text'])
                    total_conf += result['confidence']
                    count += 1

            combined_text = '\n'.join(all_text)
            avg_conf = total_conf / count if count > 0 else 0.0

            return cls._parse_text(combined_text, avg_conf)

        except ImportError:
            logger.exception(
                'pdf2image not installed. Run: pip install pdf2image'
            )
            return cls._empty_result()
        except Exception as e:
            logger.exception(f'PDF OCR error: {e}')
            return cls._empty_result()

    # ═══════════════════════════════════════════════════════════
    # CONFIDENCE CALCULATOR
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def _calculate_confidence(cls, response):
        """Average confidence from all blocks"""
        try:
            confidences = []
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    if block.confidence:
                        confidences.append(block.confidence)

            if not confidences:
                return 0.0

            return sum(confidences) / len(confidences)
        except Exception:
            return 0.0

    # ═══════════════════════════════════════════════════════════
    # EMPTY RESULT
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def _empty_result(raw_text='', confidence=0.0):
        return {
            'raw_text': raw_text,
            'confidence': confidence,
            'transaction_id': '',
            'amount': Decimal('0'),
            'payer_name': '',
            'payer_upi_id': '',
            'payment_date': None,
            'payment_time': None,
            'payment_app': '',
        }

    # ═══════════════════════════════════════════════════════════
    # PARSE TEXT → STRUCTURED DATA
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def _parse_text(text, confidence):
        """
        Payment screenshot text ko parse karo.
        - UTR / Transaction ID
        - Amount
        - UPI ID
        - Date / Time
        - Payment App
        - Payer Name
        """
        result = OCRService._empty_result(text, confidence)

        if not text or not text.strip():
            return result

        text_clean = text.strip()

        # ═══════════════════════════════════════════════════════
        # ✅ UTR / Transaction ID
        # ═══════════════════════════════════════════════════════
        utr_patterns = [
            r'(?:UTR|Txn|Transaction|Ref|Reference|Order)\s*(?:ID|No|Number)?[:\s#]*([A-Z0-9]{8,22})',
            r'\b(\d{12})\b',  # 12-digit
            r'\b([A-Z]{2,4}\d{10,18})\b',  # e.g., HDFC1234567890
        ]
        for pattern in utr_patterns:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                result['transaction_id'] = match.group(1)
                break

        # ═══════════════════════════════════════════════════════
        # ✅ AMOUNT — ₹X, XXX.XX
        # ═══════════════════════════════════════════════════════
        amount_patterns = [
            r'(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)',
            r'(?:Amount|Paid|Total)\s*[:\s]*([\d,]+(?:\.\d{1,2})?)',
            r'([\d,]+\.\d{2})',  # X,XXX.XX
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = Decimal(amount_str)
                    if amount > 0 and amount < 1000000:
                        result['amount'] = amount
                        break
                except (InvalidOperation, ValueError):
                    continue

        # ═══════════════════════════════════════════════════════
        # ✅ UPI ID
        # ═══════════════════════════════════════════════════════
        upi_match = re.search(
            r'([a-zA-Z0-9.\-_]{2,}@[a-zA-Z]{2,})',
            text_clean,
        )
        if upi_match:
            result['payer_upi_id'] = upi_match.group(1)

        # ═══════════════════════════════════════════════════════
        # ✅ DATE — DD/MM/YYYY, DD-MM-YYYY, DD MMM YYYY
        # ═══════════════════════════════════════════════════════
        date_patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, text_clean, re.IGNORECASE)
            if date_match:
                date_str = date_match.group(1)
                for fmt in (
                    '%d/%m/%Y', '%d-%m-%Y',
                    '%d/%m/%y', '%d-%m-%y',
                    '%d %b %Y', '%d %B %Y',
                    '%d %b %y',
                ):
                    try:
                        result['payment_date'] = datetime.strptime(
                            date_str, fmt
                        ).date()
                        break
                    except ValueError:
                        continue
                if result['payment_date']:
                    break

        # ═══════════════════════════════════════════════════════
        # ✅ TIME — HH:MM AM/PM
        # ═══════════════════════════════════════════════════════
        time_match = re.search(
            r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)',
            text_clean,
            re.IGNORECASE,
        )
        if time_match:
            time_str = time_match.group(1).strip().upper()
            for fmt in ('%I:%M %p', '%H:%M', '%I:%M%p', '%I:%M %P'):
                try:
                    result['payment_time'] = datetime.strptime(
                        time_str, fmt
                    ).time()
                    break
                except ValueError:
                    continue

        # ═══════════════════════════════════════════════════════
        # ✅ PAYMENT APP
        # ═══════════════════════════════════════════════════════
        text_lower = text_clean.lower()
        app_map = {
            'phonepe': 'PhonePe',
            'paytm': 'Paytm',
            'googlepay': 'Google Pay',
            'google pay': 'Google Pay',
            'gpay': 'Google Pay',
            'bhim': 'BHIM',
            'amazonpay': 'Amazon Pay',
            'amazon pay': 'Amazon Pay',
            'cred': 'CRED',
            'mobikwik': 'MobiKwik',
            'freecharge': 'Freecharge',
        }
        for key, value in app_map.items():
            if key in text_lower:
                result['payment_app'] = value
                break

        # ═══════════════════════════════════════════════════════
        # ✅ PAYER NAME
        # ═══════════════════════════════════════════════════════
        name_patterns = [
            r'(?:Paid to|Paid by|To|From|Sender|Receiver)[:\s]+([A-Z][a-zA-Z\s\.]{2,40})',
            r'(?:Name)[:\s]+([A-Z][a-zA-Z\s\.]{2,40})',
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, text_clean)
            if name_match:
                name = name_match.group(1).strip()
                # Cleanup
                name = re.sub(r'\s+', ' ', name)
                if 2 <= len(name) <= 50:
                    result['payer_name'] = name
                    break

        return result

    # ═══════════════════════════════════════════════════════════
    # EXTRACT RESULT INFO (For tournament results — kills/placement)
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def extract_result_info(cls, image_input):
        """
        Tournament result screenshot se data extract karo.
        
        Returns: {
            'success': bool,
            'raw_text': str,
            'confidence': float,
            'data': {
                'kills': int,
                'placement': int,
                'player_name': str,
                'free_fire_uid': str,
                'score': int,
            }
        }
        """
        try:
            # Get raw text
            if isinstance(image_input, bytes):
                ocr_result = cls.extract_from_image(image_input)
            else:
                ocr_result = cls.extract_from_image(image_input)

            raw_text = ocr_result.get('raw_text', '')
            confidence = ocr_result.get('confidence', 0.0)

            # Parse result data
            data = cls._parse_result_data(raw_text)

            return {
                'success': True,
                'raw_text': raw_text,
                'confidence': confidence,
                'data': data,
            }

        except Exception as e:
            logger.exception(f'extract_result_info error: {e}')
            return {
                'success': False,
                'raw_text': '',
                'confidence': 0.0,
                'data': {},
                'error': str(e),
            }

    # ═══════════════════════════════════════════════════════════
    # PARSE RESULT DATA (Kills, Placement, etc.)
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def _parse_result_data(raw_text):
        """Tournament result text parse karo"""
        if not raw_text:
            return {
                'kills': 0,
                'placement': 0,
                'score': 0,
                'player_name': '',
                'free_fire_uid': '',
            }

        lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
        text_lower = raw_text.lower()

        kills = 0
        placement = 0
        score = 0
        player_name = ''
        free_fire_uid = ''

        # ✅ KILLS
        kill_patterns = [
            r'kills?\s*[:\-]?\s*(\d+)',
            r'(\d+)\s*kills?',
            r'total\s+kills?\s*[:\-]?\s*(\d+)',
        ]
        for pattern in kill_patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = int(match.group(1))
                if 0 < val < 100:
                    kills = val
                    break

        # ✅ PLACEMENT
        place_patterns = [
            r'placement\s*[:\-]?\s*#?\s*(\d+)',
            r'rank\s*[:\-]?\s*#?\s*(\d+)',
            r'#\s*(\d+)',
            r'(\d+)\s*(?:st|nd|rd|th)\s*(?:place|position|rank)',
        ]
        for pattern in place_patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = int(match.group(1))
                if 0 < val < 100:
                    placement = val
                    break

        # ✅ SCORE
        score_patterns = [
            r'score\s*[:\-]?\s*(\d+)',
            r'points?\s*[:\-]?\s*(\d+)',
        ]
        for pattern in score_patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = int(match.group(1))
                if 0 < val < 1000:
                    score = val
                    break

        # ✅ PLAYER NAME
        name_patterns = [
            r'(?:player|username|name|ign)\s*[:\-]?\s*([A-Za-z0-9_\[\]]{2,30})',
            r'(?:ign|nickname)\s*[:\-]?\s*([A-Za-z0-9_\[\]]{2,30})',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) >= 2:
                    player_name = name
                    break

        # ✅ FREE FIRE UID — 8-12 digits, not kills/score
        uid_patterns = [
            r'(?:uid|player\s*id|account)\s*[:\-]?\s*(\d{8,12})',
            r'\b(\d{9,12})\b',
        ]
        for pattern in uid_patterns:
            matches = re.findall(pattern, text_lower)
            for m in matches:
                num = int(m)
                if 100000 < num < 999999999999:
                    free_fire_uid = m
                    break
            if free_fire_uid:
                break

        return {
            'kills': kills,
            'placement': placement,
            'score': score,
            'player_name': player_name,
            'free_fire_uid': free_fire_uid,
        }