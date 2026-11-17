# apps/payments/services/payment_verification.py
import os
import hashlib
import logging
from decimal import Decimal
from datetime import timedelta

from django.db import transaction, IntegrityError
from django.utils import timezone

from apps.payments.models import PaymentScreenshot, FraudLog
from apps.payments.services.notifications import notify_admin_review_needed

logger = logging.getLogger(__name__)


class DuplicateTransactionError(Exception):
    pass


class FraudDetectedError(Exception):
    pass


class PaymentVerificationService:

    FRAUD_THRESHOLD_REJECT = 70
    FRAUD_THRESHOLD_REVIEW = 30

    @classmethod
    def submit_payment(
        cls,
        user,
        utr,
        tournament_id='',
        registration_id='',
        match_id='',
        amount=0,
        user_upi_id='',
        user_mobile='',
        detected_app='',
        ip_address=None,
    ):
        """
        UTR based verification. Screenshot save NAHI hoga.
        """

        utr = str(utr).strip().upper()

        # ═══════════════════════════════════════════
        # STEP 1: UTR Validation
        # ═══════════════════════════════════════════
        if not utr:
            raise FraudDetectedError('UTR / Ref No required')

        if len(utr) != 12 or not utr.isdigit():
            raise FraudDetectedError(
                'UTR 12-digit number hona chahiye (e.g. 130169248692)'
            )

        # ═══════════════════════════════════════════
        # STEP 2: Duplicate — kisi aur ne use kiya?
        # ═══════════════════════════════════════════
        existing_other = PaymentScreenshot.objects.filter(
            transaction_id=utr
        ).exclude(uploaded_by=user).first()

        if existing_other:
            cls._log_fraud(user, 'DUPLICATE_UTR', {
                'utr': utr,
                'existing_user': existing_other.uploaded_by.email,
                'existing_id': existing_other.id,
            }, ip_address)

            raise DuplicateTransactionError(
                f"❌ Yeh UTR ({utr}) already use ho chuka hai.\n"
                f"Uploaded by: {existing_other.uploaded_by.email}\n"
                f"Date: {existing_other.uploaded_at.strftime('%d %b %Y')}\n\n"
                f"Ek UTR sirf ek baar use ho sakta hai."
            )

        # ═══════════════════════════════════════════
        # STEP 3: Same user ne same UTR dobara?
        # ═══════════════════════════════════════════
        existing_same = PaymentScreenshot.objects.filter(
            transaction_id=utr,
            uploaded_by=user,
        ).first()

        if existing_same:
            raise DuplicateTransactionError(
                f"❌ Aapne yeh UTR ({utr}) pehle use kiya hai.\n"
                f"Date: {existing_same.uploaded_at.strftime('%d %b %Y')}"
            )

        # ═══════════════════════════════════════════
        # STEP 4: Fraud Score
        # ═══════════════════════════════════════════
        fraud_score, fraud_flags, problems = cls._calculate_fraud_score(
            user, amount, tournament_id
        )

        # ═══════════════════════════════════════════
        # STEP 5: Status
        # ═══════════════════════════════════════════
        if fraud_score >= cls.FRAUD_THRESHOLD_REJECT:
            status = 'rejected'
            message = cls._build_rejection_message(problems)
            admin_needed = False
        else:
            status = 'manual_review'
            message = (
                "✅ Payment submit ho gaya.\n"
                "Admin verify karega. 24 ghante mein update milega."
            )
            admin_needed = True

        # ═══════════════════════════════════════════
        # STEP 6: Save
        # ═══════════════════════════════════════════
        try:
            with transaction.atomic():
                payment = PaymentScreenshot.objects.create(
                    transaction_id=utr,
                    amount=Decimal(str(amount)) if amount else Decimal('0'),
                    uploaded_by=user,
                    user_upi_id=user_upi_id,
                    user_mobile=user_mobile,
                    payment_app=detected_app,
                    tournament_id=tournament_id,
                    registration_id=registration_id,
                    match_id=match_id or tournament_id,
                    status=status,
                    fraud_score=fraud_score,
                    fraud_flags=fraud_flags,
                    review_problems=problems if admin_needed else [],
                    ip_address=ip_address,
                )
        except IntegrityError as e:
            cls._log_fraud(user, 'RACE_CONDITION', {
                'utr': utr, 'error': str(e),
            }, ip_address)
            raise DuplicateTransactionError(
                "❌ Yeh UTR abhi-abhi kisi aur ne upload kiya hai."
            )

        # ═══════════════════════════════════════════
        # STEP 7: Fraud log if rejected
        # ═══════════════════════════════════════════
        if status == 'rejected':
            cls._log_fraud(user, 'FRAUD_SCORE_HIGH', {
                'score': fraud_score,
                'problems': problems,
            }, ip_address)

        # ═══════════════════════════════════════════
        # STEP 8: Notify admin
        # ═══════════════════════════════════════════
        if admin_needed:
            try:
                notify_admin_review_needed(payment, problems)
            except Exception as e:
                logger.exception(f"Admin notification failed: {e}")

        return {
            'status': status,
            'message': message,
            'payment_id': payment.id,
            'problems': problems,
            'fraud_score': fraud_score,
        }

    @classmethod
    def _calculate_fraud_score(cls, user, amount, tournament_id):
        score = 0
        flags = []
        problems = []

        # 1. User rejections
        user_rejections = PaymentScreenshot.objects.filter(
            uploaded_by=user, status='rejected'
        ).count()
        if user_rejections >= 3:
            score += 25
            flags.append(f'USER_HISTORY_{user_rejections}')
            problems.append({
                'code': 'USER_HISTORY',
                'severity': 'high',
                'title': f'User ke {user_rejections} rejections',
                'detail': f'Is user ke pehle {user_rejections} payments reject ho chuke hain.',
                'suggestion': 'Pattern check karo',
            })

        # 2. Rapid submissions
        recent = PaymentScreenshot.objects.filter(
            uploaded_by=user,
            uploaded_at__gte=timezone.now() - timedelta(hours=1),
        ).count()
        if recent >= 5:
            score += 30
            flags.append('RAPID_UPLOADS')
            problems.append({
                'code': 'RAPID_UPLOADS',
                'severity': 'medium',
                'title': f'{recent} submissions 1 hour mein',
                'detail': 'Bahut tezi se submit kar raha hai.',
                'suggestion': 'Rate limit lagao',
            })

        # 3. Amount out of range
        try:
            amt = Decimal(str(amount)) if amount else Decimal('0')
            if amt > Decimal('100000'):
                score += 20
                flags.append('AMOUNT_OUT_OF_RANGE')
                problems.append({
                    'code': 'AMOUNT_OUT_OF_RANGE',
                    'severity': 'high',
                    'title': f'Amount bahut zyada: ₹{amt}',
                    'detail': 'Allowed limit se zyada.',
                    'suggestion': 'Manual verify karo',
                })
        except Exception:
            pass

        # 4. Same amount different tournament
        if amount and tournament_id:
            similar = PaymentScreenshot.objects.filter(
                uploaded_by=user,
                amount=amount,
                status='verified',
            ).exclude(tournament_id=tournament_id).count()
            if similar > 0:
                score += 35
                flags.append('SAME_AMOUNT_DIFFERENT_TOURNAMENT')
                problems.append({
                    'code': 'SAME_AMOUNT_DIFFERENT_TOURNAMENT',
                    'severity': 'high',
                    'title': f'Same amount ₹{amount} dusre tournament mein',
                    'detail': f'Is user ne same amount {similar} baar use kiya hai.',
                    'suggestion': 'History check karo',
                })

        return min(score, 100), flags, problems

    @staticmethod
    def _build_rejection_message(problems):
        critical = [p for p in problems if p.get('severity') == 'critical']
        high = [p for p in problems if p.get('severity') == 'high']

        lines = ["❌ Aapka payment reject kar diya gaya hai.\n"]

        if critical:
            lines.append("🚨 Critical Issues:")
            for p in critical:
                lines.append(f"  • {p['title']}")

        if high:
            lines.append("\n⚠️ High Priority Issues:")
            for p in high:
                lines.append(f"  • {p['title']}")

        lines.append("\nSupport: support@kuberaa.com")
        return '\n'.join(lines)

    @staticmethod
    def _log_fraud(user, reason, details, ip):
        try:
            FraudLog.objects.create(
                user=user, reason=reason,
                details=details, ip_address=ip,
            )
        except Exception as e:
            logger.exception(f"Fraud log failed: {e}")