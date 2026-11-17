from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.throttling import AnonRateThrottle
from django.contrib.auth import authenticate, get_user_model
from firebase_admin import auth as firebase_auth

from core.responses import success_response, error_response
from .serializers import (
    RegisterSerializer, LoginSerializer,
    PasswordResetRequestSerializer, PasswordResetVerifySerializer,
    PasswordResetConfirmSerializer,
)
from .services import OTPAuthService

User = get_user_model()


class LoginThrottle(AnonRateThrottle):
    scope = 'login'


class OTPThrottle(AnonRateThrottle):
    scope = 'otp'


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)

        user = serializer.save()

        # ✅ REFERRAL APPLY KARO
        referral_code = request.data.get('referral_code', '').strip().upper()
        if referral_code:
            from apps.users.services.referral_service import ReferralService
            ReferralService.apply_referral(user, referral_code)

        tokens = _tokens_for_user(user)

        return success_response(
            data={
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'display_name': user.display_name,
                    'referral_code': user.referral_code,
                },
                'tokens': tokens,
            },
            message='Registration successful',
            status=201,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)

        email = serializer.validated_data['email'].lower()
        password = serializer.validated_data['password']

        user = authenticate(request, username=email, password=password)
        if not user:
            return error_response('Invalid credentials', 401)

        if user.status == User.Status.BLOCKED:
            return error_response('Account blocked', 403)
        if user.status == User.Status.SUSPENDED:
            return error_response('Account suspended', 403)

        tokens = _tokens_for_user(user)
        return success_response(
            data={
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'display_name': user.display_name,
                    'role': user.role,
                },
                'tokens': tokens,
            },
            message='Login successful',
        )


# ═══════════════════════════════════════════════════════════
# ✅ FIREBASE LOGIN
# ═══════════════════════════════════════════════════════════
class FirebaseLoginView(APIView):
    """Firebase token verify karo + Django JWT return karo"""
    permission_classes = [AllowAny]

    def post(self, request):
        id_token = request.data.get('id_token', '').strip()

        if not id_token:
            return error_response('Firebase ID token required', 400)

        try:
            decoded_token = firebase_auth.verify_id_token(
                id_token,
                clock_skew_seconds=60,
            )

            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email', '')
            name = decoded_token.get('name', '')
            phone = decoded_token.get('phone_number', '')

            if not email:
                return error_response('Email required in Firebase token', 400)

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'firebase_uid': firebase_uid,
                    'display_name': name,
                    'mobile_number': phone,
                },
            )

            if created:
                user.set_unusable_password()
                user.save()

            tokens = _tokens_for_user(user)

            return success_response(
                data={
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'display_name': user.display_name,
                        'role': user.role,
                    },
                    'tokens': tokens,
                },
                message='Firebase login successful',
            )
        except Exception as e:
            import traceback
            print(f"🔴 Firebase login error: {e}")
            print(traceback.format_exc())
            return error_response(f'Invalid Firebase token: {str(e)}', 401)


# ═══════════════════════════════════════════════════════════
# LOGOUT
# ═══════════════════════════════════════════════════════════

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass
        return success_response(message='Logged out')


# ═══════════════════════════════════════════════════════════
# PASSWORD RESET (OTP)
# ═══════════════════════════════════════════════════════════

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)

        result = OTPAuthService.request_password_reset(serializer.validated_data['email'])
        if not result['success']:
            return error_response(result['message'], 400)
        return success_response(message=result['message'])


class PasswordResetVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = PasswordResetVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)

        result = OTPAuthService.verify_otp(
            serializer.validated_data['email'],
            serializer.validated_data['otp']
        )
        if not result['success']:
            return error_response(result['message'], 400)
        return success_response(message='OTP verified')


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)

        result = OTPAuthService.confirm_password_reset(
            serializer.validated_data['email'],
            serializer.validated_data['otp'],
            serializer.validated_data['new_password'],
        )
        if not result['success']:
            return error_response(result['message'], 400)
        return success_response(message=result['message'])

# apps/authentication/views.py

class FirebaseLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        id_token = request.data.get('id_token', '').strip()
        referral_code = request.data.get('referral_code', '').strip().upper()

        if not id_token:
            return error_response('Firebase ID token required', 400)

        try:
            decoded_token = firebase_auth.verify_id_token(
                id_token, clock_skew_seconds=60,
            )

            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email', '')
            name = decoded_token.get('name', '')
            phone = decoded_token.get('phone_number', '')

            if not email:
                return error_response('Email required in Firebase token', 400)

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'firebase_uid': firebase_uid,
                    'display_name': name,
                    'mobile_number': phone,
                },
            )

            if created:
                user.set_unusable_password()
                user.save()

                # ✅ NAYA user — referral apply karo
                if referral_code:
                    from apps.users.services.referral_service import ReferralService
                    ReferralService.apply_referral(user, referral_code)

            tokens = _tokens_for_user(user)

            return success_response(
                data={
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                        'display_name': user.display_name,
                        'role': user.role,
                        'referral_code': user.referral_code,
                    },
                    'tokens': tokens,
                },
                message='Firebase login successful',
            )
        except Exception as e:
            import traceback
            print(f"🔴 Firebase login error: {e}")
            print(traceback.format_exc())
            return error_response(f'Invalid Firebase token: {str(e)}', 401)