# apps/users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils import timezone
from .models import User, PasswordResetOTP


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'email',
        'display_name',
        'mobile_number',
        'free_entry_status',       # ✅ Ab method defined hai
        'free_entry_code',
        'free_entry_max_amount',
        'total_referrals',
        'role',
        'status',
        'created_at',
    )

    list_filter = (
        'role',
        'status',
        'is_staff',
        'free_entry_used',
    )

    search_fields = (
        'email',
        'mobile_number',
        'free_fire_uid',
        'display_name',
        'referral_code',
        'free_entry_code',
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'referral_code',
        'free_entry_code',
        'free_entry_expires_at',
        'free_entry_used_at',
    )

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal', {
            'fields': (
                'display_name',
                'mobile_number',
                'free_fire_uid',
                'free_fire_name',
                'upi_id',
            )
        }),
        ('Permissions', {
            'fields': (
                'role',
                'status',
                'is_staff',
                'is_superuser',
                'is_active',
            )
        }),
        ('🎁 Referral', {
            'fields': (
                'referral_code',
                'referred_by',
            ),
            'classes': ('wide',),
        }),
        ('🎁 Free Entry', {
            'fields': (
                'free_entry_code',
                'free_entry_used',
                'free_entry_max_amount',
                'free_entry_expires_at',
                'free_entry_used_at',
                'free_entry_used_tournament',
            ),
            'classes': ('wide',),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'status'),
        }),
    )

    # ═══════════════════════════════════════════════════════════
    # ✅ CUSTOM COLUMNS
    # ═══════════════════════════════════════════════════════════

    def free_entry_status(self, obj):
        """Free entry ka status dikhao"""
        if not obj.free_entry_code:
            return format_html(
                '<span style="color: #999;">❌ None</span>'
            )

        if obj.free_entry_used:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">🔴 Used</span>'
            )

        if obj.free_entry_expires_at and obj.free_entry_expires_at < timezone.now():
            return format_html(
                '<span style="color: #ff9800; font-weight: bold;">⏰ Expired</span>'
            )

        return format_html(
            '<span style="color: #28a745; font-weight: bold;">✅ AVAILABLE</span>'
        )

    free_entry_status.short_description = '🎁 Free Entry'

    def total_referrals(self, obj):
        """Total referrals count"""
        count = User.objects.filter(referred_by=obj).count()
        if count == 0:
            return format_html('<span style="color: #999;">0</span>')
        return format_html(
            '<span style="color: #007bff; font-weight: bold;">{}</span>',
            count
        )

    total_referrals.short_description = '👥 Referrals'


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_used', 'attempts', 'expires_at', 'created_at')
    list_filter = ('is_used',)
    search_fields = ('user__email',)