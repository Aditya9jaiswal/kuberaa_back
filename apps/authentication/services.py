import secrets
import hashlib
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

from apps.users.models import PasswordResetOTP

User = get_user_model()
logger = logging.getLogger(__name__)


class OTPAuthService:

    @staticmethod
    def _hash_otp(otp: str) -> str:
        return hashlib.sha256(otp.encode()).hexdigest()

    @staticmethod
    def generate_otp() -> str:
        length = settings.OTP_LENGTH
        return ''.join(str(secrets.randbelow(10)) for _ in range(length))

    @classmethod
    def request_password_reset(cls, email: str) -> dict:
        try:
            user = User.objects.get(email=email.lower())
        except User.DoesNotExist:
            return {'success': True, 'message': 'If email exists, OTP sent'}

        recent = PasswordResetOTP.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS),
            is_used=False,
        ).first()

        if recent and recent.is_valid():
            return {'success': False, 'message': f'Please wait {settings.OTP_RESEND_COOLDOWN_SECONDS}s before requesting again'}

        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

        otp = cls.generate_otp()
        expires = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

        PasswordResetOTP.objects.create(
            user=user,
            otp_hash=cls._hash_otp(otp),
            expires_at=expires,
            max_attempts=settings.OTP_MAX_ATTEMPTS,
        )

        try:
            send_mail(
                subject='Kuberaa Password Reset OTP',
                message=f'Your OTP is: {otp}\n\nValid for {settings.OTP_EXPIRY_MINUTES} minutes.\nDo not share.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.exception(f"Email send failed: {e}")
            return {'success': False, 'message': 'Failed to send email'}

        return {'success': True, 'message': 'OTP sent to email'}

    @classmethod
    def verify_otp(cls, email: str, otp: str) -> dict:
        try:
            user = User.objects.get(email=email.lower())
        except User.DoesNotExist:
            return {'success': False, 'message': 'Invalid OTP'}

        otp_record = PasswordResetOTP.objects.filter(
            user=user, is_used=False
        ).order_by('-created_at').first()

        if not otp_record:
            return {'success': False, 'message': 'No active OTP'}

        if otp_record.is_expired():
            return {'success': False, 'message': 'OTP expired'}

        if otp_record.attempts >= otp_record.max_attempts:
            return {'success': False, 'message': 'Max attempts reached'}

        otp_record.attempts += 1
        otp_record.save(update_fields=['attempts'])

        if otp_record.otp_hash != cls._hash_otp(otp):
            return {'success': False, 'message': 'Invalid OTP'}

        return {'success': True, 'message': 'OTP verified', 'user': user, 'otp_record': otp_record}

    @classmethod
    def confirm_password_reset(cls, email: str, otp: str, new_password: str) -> dict:
        result = cls.verify_otp(email, otp)
        if not result['success']:
            return result

        user = result['user']
        otp_record = result['otp_record']

        user.set_password(new_password)
        user.save()

        otp_record.is_used = True
        otp_record.save(update_fields=['is_used'])

        return {'success': True, 'message': 'Password reset successful'}