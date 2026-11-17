# apps/users/serializers.py

from rest_framework import serializers
from .models import User, PasswordResetOTP


class UserSerializer(serializers.ModelSerializer):
    free_entry_available = serializers.SerializerMethodField()
    is_new_user = serializers.SerializerMethodField()
    can_use_first_free = serializers.SerializerMethodField()
    can_use_points = serializers.SerializerMethodField()
    has_any_game_account = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'display_name',
            'mobile_number',

            # ═══════════════════════════════════════════════
            # ✅ GAME ACCOUNTS — GAME-WISE COMPARTMENTS
            # ═══════════════════════════════════════════════
            'free_fire_uid',
            'free_fire_name',
            'bgmi_uid',
            'bgmi_name',
            'pubg_uid',
            'pubg_name',
            'cod_uid',
            'cod_name',
            'valorant_uid',
            'valorant_name',

            # ═══════════════════════════════════════════════
            # OTHER
            # ═══════════════════════════════════════════════
            'upi_id',
            'role',
            'status',

            # ═══════════════════════════════════════════════
            # KUBERAA POINTS
            # ═══════════════════════════════════════════════
            'kuberaa_points',
            'has_played_first_match',
            'first_match_free_used',
            'is_new_user',
            'can_use_first_free',
            'can_use_points',

            # ═══════════════════════════════════════════════
            # REFERRAL
            # ═══════════════════════════════════════════════
            'referral_code',
            'total_referrals',
            'referral_earnings',

            # ═══════════════════════════════════════════════
            # FREE ENTRY
            # ═══════════════════════════════════════════════
            'free_entry_code',
            'free_entry_used',
            'free_entry_max_amount',
            'free_entry_expires_at',
            'free_entry_available',

            # ═══════════════════════════════════════════════
            # WALLET
            # ═══════════════════════════════════════════════
            'wallet_balance',

            # ═══════════════════════════════════════════════
            # HELPERS
            # ═══════════════════════════════════════════════
            'has_any_game_account',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'email',
            'role',
            'status',
            'kuberaa_points',
            'has_played_first_match',
            'first_match_free_used',
            'referral_code',
            'total_referrals',
            'referral_earnings',
            'free_entry_code',
            'free_entry_used',
            'free_entry_max_amount',
            'free_entry_expires_at',
            'wallet_balance',
            'created_at',
        ]

    # ═══════════════════════════════════════════════════════════
    # METHOD FIELDS
    # ═══════════════════════════════════════════════════════════

    def get_free_entry_available(self, obj):
        return obj.has_free_entry_available

    def get_is_new_user(self, obj):
        return obj.is_new_user

    def get_can_use_first_free(self, obj):
        return obj.can_use_first_free

    def get_can_use_points(self, obj):
        return obj.can_use_points

    def get_has_any_game_account(self, obj):
        return obj.has_any_game_account


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Profile update — game-wise accounts support
    """
    class Meta:
        model = User
        fields = [
            'display_name',
            'mobile_number',

            # ✅ GAME ACCOUNTS
            'free_fire_uid',
            'free_fire_name',
            'bgmi_uid',
            'bgmi_name',
            'pubg_uid',
            'pubg_name',
            'cod_uid',
            'cod_name',
            'valorant_uid',
            'valorant_name',

            # ✅ UPI
            'upi_id',
        ]

    def validate_mobile_number(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError(
                'Mobile number must contain only digits'
            )
        if value and len(value) != 10:
            raise serializers.ValidationError(
                'Mobile number must be 10 digits'
            )
        if value and value[0] not in '6789':
            raise serializers.ValidationError(
                'Mobile number must start with 6, 7, 8, or 9'
            )
        return value

    def validate_upi_id(self, value):
        if value:
            if '@' not in value:
                raise serializers.ValidationError(
                    'Enter a valid UPI ID (example: name@paytm)'
                )
        return value

    def validate_free_fire_uid(self, value):
        if value:
            if not value.isdigit():
                raise serializers.ValidationError(
                    'Free Fire UID must contain only digits'
                )
            if len(value) < 8 or len(value) > 12:
                raise serializers.ValidationError(
                    'Free Fire UID must be 8-12 digits'
                )
        return value

    def validate_bgmi_uid(self, value):
        if value:
            if not value.isdigit():
                raise serializers.ValidationError(
                    'BGMI UID must contain only digits'
                )
            if len(value) < 8 or len(value) > 12:
                raise serializers.ValidationError(
                    'BGMI UID must be 8-12 digits'
                )
        return value

    def validate_pubg_uid(self, value):
        if value:
            if not value.isdigit():
                raise serializers.ValidationError(
                    'PUBG UID must contain only digits'
                )
            if len(value) < 8 or len(value) > 12:
                raise serializers.ValidationError(
                    'PUBG UID must be 8-12 digits'
                )
        return value

    def validate_cod_uid(self, value):
        if value:
            if len(value) < 6 or len(value) > 20:
                raise serializers.ValidationError(
                    'COD UID must be 6-20 characters'
                )
        return value

    def validate_valorant_uid(self, value):
        if value:
            if len(value) < 6 or len(value) > 20:
                raise serializers.ValidationError(
                    'Valorant UID must be 6-20 characters'
                )
        return value


class KycUpdateSerializer(serializers.ModelSerializer):
    """
    KYC — Required fields for tournament registration
    """
    class Meta:
        model = User
        fields = [
            'upi_id',
            'mobile_number',
            'free_fire_uid',
            'free_fire_name',
        ]

    def validate(self, data):
        # ✅ Required fields
        upi_id = data.get('upi_id', '').strip()
        mobile = data.get('mobile_number', '').strip()
        ff_uid = data.get('free_fire_uid', '').strip()
        ff_name = data.get('free_fire_name', '').strip()

        errors = {}

        # UPI validation
        if not upi_id:
            errors['upi_id'] = 'UPI ID is required'
        elif '@' not in upi_id:
            errors['upi_id'] = 'Enter a valid UPI ID (example: name@paytm)'

        # Mobile validation
        if not mobile:
            errors['mobile_number'] = 'Mobile number is required'
        elif not mobile.isdigit():
            errors['mobile_number'] = 'Mobile number must contain only digits'
        elif len(mobile) != 10:
            errors['mobile_number'] = 'Mobile number must be 10 digits'
        elif mobile[0] not in '6789':
            errors['mobile_number'] = (
                'Mobile number must start with 6, 7, 8, or 9'
            )

        # FF UID validation
        if not ff_uid:
            errors['free_fire_uid'] = 'Free Fire UID is required'
        elif not ff_uid.isdigit():
            errors['free_fire_uid'] = 'Free Fire UID must contain only digits'
        elif len(ff_uid) < 8 or len(ff_uid) > 12:
            errors['free_fire_uid'] = 'Free Fire UID must be 8-12 digits'

        # FF Name validation
        if not ff_name:
            errors['free_fire_name'] = 'Free Fire Name is required'
        elif len(ff_name) < 2:
            errors['free_fire_name'] = (
                'Free Fire Name must be at least 2 characters'
            )
        elif len(ff_name) > 20:
            errors['free_fire_name'] = (
                'Free Fire Name must be less than 20 characters'
            )

        if errors:
            raise serializers.ValidationError(errors)

        return data


class PasswordResetOTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = PasswordResetOTP
        fields = ['id', 'user', 'expires_at', 'is_used', 'created_at']
        read_only_fields = ['id', 'created_at']