# apps/users/services/referral_service.py

from django.db import transaction
from django.db import models as django_models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from urllib.parse import urlparse
import random
import string

# ✅ GlobalReferralLink Import
from apps.users.models import User, GlobalReferralLink


def generate_free_entry_code():
    while True:
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        code = f"FREE-{suffix}"
        if not User.objects.filter(free_entry_code=code).exists():
            return code


class ReferralService:

    @staticmethod
    @transaction.atomic
    def apply_referral(new_user, referral_code):
        if not referral_code: return {'success': False, 'message': 'No referral code'}
        referral_code = referral_code.strip().upper()
        if new_user.referral_code == referral_code: return {'success': False, 'message': 'Cannot use own code'}
        try: referrer = User.objects.get(referral_code=referral_code)
        except User.DoesNotExist: return {'success': False, 'message': 'Invalid referral code'}
        if referrer.status != User.Status.ACTIVE: return {'success': False, 'message': 'Referrer not active'}
        if new_user.referred_by_id: return {'success': False, 'message': 'Already referred'}
        new_user.referred_by = referrer
        new_user.save(update_fields=['referred_by'])
        User.objects.filter(pk=referrer.pk).update(total_referrals=referrer.referrals.count())
        try:
            from apps.notifications.services import NotificationService
            NotificationService.create_notification(
                user=referrer, title="👥 Naya Referral!",
                message=f"{new_user.display_name or new_user.email} ne aapka code use kiya!\n\nJab wo pehla match complete karega, aapko ₹10 ki FREE ENTRY milegi. 🎁",
                notification_type='referral',
            )
        except Exception as e: print(f"⚠️ Referral notification failed: {e}")
        return {'success': True, 'referrer': referrer, 'free_entry_granted': False, 'message': 'Free entry match complete hone pe milegi'}

    @staticmethod
    def get_user_referral_data(user):
        if not user.referral_code: user.save()
        referred_users = user.referrals.all().order_by('-created_at')
        free_entry_available = bool(user.free_entry_code and not user.free_entry_used and (not user.free_entry_expires_at or user.free_entry_expires_at > timezone.now()))
        
        # ✅ Agar user ka custom link nahi hai, toh Global Link dikhao
        global_link = GlobalReferralLink.get_link()
        share_link = user.admin_referral_link or global_link
        
        return {
            'referral_code': user.referral_code or '',
            'custom_link': user.admin_referral_link or '',
            'referral_link': share_link, # ✅ Ye global link hoga
            'global_download_link': global_link, # ✅ Frontend ke liye alag se bhi bhejo
            'total_referrals': referred_users.count(),
            'referral_earnings': float(user.referral_earnings or 0),
            'free_entry': {
                'code': user.free_entry_code or '', 'available': free_entry_available,
                'used': user.free_entry_used, 'max_amount': float(user.free_entry_max_amount or 0),
                'expires_at': user.free_entry_expires_at.isoformat() if user.free_entry_expires_at else None,
                'used_at': user.free_entry_used_at.isoformat() if user.free_entry_used_at else None,
                'used_tournament': user.free_entry_used_tournament.title if user.free_entry_used_tournament else None,
            },
            'referred_users': [
                {'id': str(u.id), 'name': u.display_name or 'Player', 'email': u.email, 'mobile': u.mobile_number or '', 'free_fire_name': u.free_fire_name or '', 'free_entry_used': u.free_entry_used, 'joined_at': u.created_at.isoformat() if u.created_at else None}
                for u in referred_users
            ],
        }

    @staticmethod
    def admin_referral_data(user):
        referred = user.referrals.all().order_by('-created_at')
        return {
            'user': {'id': str(user.id), 'email': user.email, 'display_name': user.display_name or '', 'mobile': user.mobile_number or '', 'referral_code': user.referral_code or '', 'custom_link': user.admin_referral_link or '', 'status': user.status, 'role': user.role, 'joined_at': user.created_at.isoformat() if user.created_at else None},
            'referred_by': ({'id': str(user.referred_by.id), 'email': user.referred_by.email, 'display_name': user.referred_by.display_name or '', 'referral_code': user.referred_by.referral_code} if user.referred_by else None),
            'total_referrals': referred.count(), 'referral_earnings': float(user.referral_earnings or 0),
            'free_entry': {'code': user.free_entry_code or '', 'used': user.free_entry_used, 'max_amount': float(user.free_entry_max_amount or 0), 'used_at': user.free_entry_used_at.isoformat() if user.free_entry_used_at else None, 'used_tournament': user.free_entry_used_tournament.title if user.free_entry_used_tournament else None, 'expires_at': user.free_entry_expires_at.isoformat() if user.free_entry_expires_at else None},
            'referred_users': [{'id': str(u.id), 'email': u.email, 'display_name': u.display_name or '', 'mobile': u.mobile_number or '', 'free_fire_name': u.free_fire_name or '', 'free_entry_used': u.free_entry_used, 'joined_at': u.created_at.isoformat() if u.created_at else None} for u in referred],
        }

    @staticmethod
    @transaction.atomic
    def validate_and_use_free_entry(user, tournament):
        if not user.free_entry_code: raise Exception('Free entry code nahi hai')
        if user.free_entry_used: raise Exception('Free entry already used')
        if user.free_entry_expires_at and user.free_entry_expires_at < timezone.now(): raise Exception('Free entry expire ho gayi')
        max_amt = float(user.free_entry_max_amount or 0)
        entry_fee = float(tournament.entry_fee or 0)
        if max_amt and entry_fee > max_amt: raise Exception(f'Free entry sirf ₹{max_amt} tak valid hai. Is tournament ki fee ₹{entry_fee} hai.')
        user.free_entry_used = True
        user.free_entry_used_at = timezone.now()
        user.free_entry_used_tournament = tournament
        user.save(update_fields=['free_entry_used', 'free_entry_used_at', 'free_entry_used_tournament'])
        return True

    @staticmethod
    def has_free_entry_available(user):
        if not user.free_entry_code: return False
        if user.free_entry_used: return False
        if user.free_entry_expires_at and user.free_entry_expires_at < timezone.now(): return False
        return True

    @staticmethod
    @transaction.atomic
    def grant_free_entry(user, amount=10, days=30):
        user.free_entry_code = generate_free_entry_code()
        user.free_entry_used = False
        user.free_entry_max_amount = amount
        user.free_entry_expires_at = timezone.now() + timedelta(days=days)
        user.free_entry_used_at = None
        user.free_entry_used_tournament = None
        user.save(update_fields=['free_entry_code', 'free_entry_used', 'free_entry_max_amount', 'free_entry_expires_at', 'free_entry_used_at', 'free_entry_used_tournament'])
        try:
            from apps.notifications.services import NotificationService
            NotificationService.create_notification(user=user, title="🎁 Free Entry Mil Gayi!", message=f'Aapke referral ne pehla match complete kiya!\n\n💰 ₹{amount} ki FREE ENTRY mili hai\n🎫 Code: {user.free_entry_code}\n\nAb ₹{amount} wale match mein FREE khelo!', notification_type='free_entry_granted')
        except Exception as e: print(f"⚠️ Notification failed: {e}")
        return {'success': True, 'code': user.free_entry_code, 'expires_at': user.free_entry_expires_at.isoformat()}

    @staticmethod
    @transaction.atomic
    def check_and_grant_referral_reward(user):
        from apps.results.models import Result
        if not user.referred_by: return {'success': False, 'message': 'No referrer'}
        referrer = user.referred_by
        if referrer.free_entry_code and not referrer.free_entry_used: return {'success': True, 'message': 'Referrer already has unused free entry', 'free_entry_granted': False}
        completed_count = Result.objects.filter(user=user, verification_status=Result.VerificationStatus.PUBLISHED).count()
        if completed_count != 1: return {'success': False, 'message': f'Not first match (completed: {completed_count})'}
        result = ReferralService.grant_free_entry(referrer, amount=10, days=30)
        User.objects.filter(pk=referrer.pk).update(total_referrals=referrer.referrals.count())
        return {'success': True, 'referrer': referrer, 'free_entry_granted': True, 'free_entry_code': result['code']}

    @staticmethod
    @transaction.atomic
    def admin_update_referral_link(user, custom_link=None):
        try:
            if not user.is_active or user.status != User.Status.ACTIVE: return {'success': False, 'error': 'User account is not active.'}
            if custom_link and custom_link.strip():
                custom_link = custom_link.strip()
                parsed = urlparse(custom_link)
                if not parsed.scheme or not parsed.netloc: return {'success': False, 'error': 'Invalid URL format. Must start with http:// or https://'}
                if len(custom_link) > 255: return {'success': False, 'error': 'Link is too long (max 255 characters).'}
                user.admin_referral_link = custom_link
                is_custom = True
            else:
                base_url = getattr(settings, 'APP_SHARE_URL', 'https://kuberaa.app/join')
                if base_url.endswith('?') or base_url.endswith('&'): base_url = base_url[:-1]
                link = f"{base_url.split('?ref=')[0]}?ref={user.referral_code}" if '?ref=' in base_url else f"{base_url}?ref={user.referral_code}"
                user.admin_referral_link = link
                is_custom = False
            user.admin_link_updated_at = timezone.now()
            if hasattr(user, 'admin_link_active'): user.admin_link_active = True
            user.save(update_fields=['admin_referral_link', 'admin_link_updated_at', 'admin_link_active'])
            return {'success': True, 'link': user.admin_referral_link, 'referral_code': user.referral_code, 'updated_at': user.admin_link_updated_at.isoformat(), 'is_custom': is_custom}
        except Exception as e: return {'success': False, 'error': f'Failed to update link: {str(e)}'}

    @staticmethod
    @transaction.atomic
    def admin_delete_referral_link(user):
        try:
            user.admin_referral_link = None
            user.admin_link_updated_at = timezone.now()
            if hasattr(user, 'admin_link_active'): user.admin_link_active = False
            user.save(update_fields=['admin_referral_link', 'admin_link_updated_at', 'admin_link_active'])
            default_link = f"https://kuberaa.app/join?ref={user.referral_code}"
            return {'success': True, 'message': 'Custom link deleted', 'default_link': default_link}
        except Exception as e: return {'success': False, 'error': f'Failed to delete link: {str(e)}'}

    @staticmethod
    def get_share_message(user):
        # ✅ Admin ka Global Link uthao
        global_link = GlobalReferralLink.get_link()
        
        return (
            f'🎮 *Welcome to Kuberaa!*\n\n'
            f'Khelo, jeeto aur apni skills dikhao!\n\n'
            f'✅ Play fair\n'
            f'✅ Win up to ₹50 + FREE TICKETS 🎟️\n'
            f'✅ Compete with the best\n\n'
            f'👇 Download now:\n'
            f'{global_link}\n\n'
            f'🎁 Use my referral code: *{user.referral_code}*\n\n'  # ✅ Referral Code Highlight
            f"Let's play fair and win together! 🏆"
        )
    @staticmethod
    def admin_all_free_entries(search=None, status=None):
        qs = User.objects.exclude(free_entry_code__isnull=True).exclude(free_entry_code='')
        if search: qs = qs.filter(django_models.Q(email__icontains=search) | django_models.Q(display_name__icontains=search) | django_models.Q(mobile_number__icontains=search) | django_models.Q(free_entry_code__icontains=search))
        if status == 'available': qs = qs.filter(free_entry_used=False, free_entry_expires_at__gt=timezone.now())
        elif status == 'used': qs = qs.filter(free_entry_used=True)
        elif status == 'expired': qs = qs.filter(free_entry_used=False, free_entry_expires_at__lt=timezone.now())
        data = []
        for u in qs.order_by('-created_at'):
            is_available = (not u.free_entry_used and u.free_entry_expires_at and u.free_entry_expires_at > timezone.now())
            data.append({'id': str(u.id), 'email': u.email, 'display_name': u.display_name or '', 'mobile': u.mobile_number or '', 'free_fire_name': u.free_fire_name or '', 'free_entry_code': u.free_entry_code or '', 'free_entry_used': u.free_entry_used, 'free_entry_max_amount': float(u.free_entry_max_amount or 0), 'free_entry_available': is_available, 'free_entry_expires_at': (u.free_entry_expires_at.isoformat() if u.free_entry_expires_at else None), 'free_entry_used_at': (u.free_entry_used_at.isoformat() if u.free_entry_used_at else None), 'free_entry_used_tournament': (u.free_entry_used_tournament.title if u.free_entry_used_tournament else None), 'total_referrals': u.referrals.count(), 'referred_by_email': (u.referred_by.email if u.referred_by else None), 'joined_at': (u.created_at.isoformat() if u.created_at else None)})
        return data

    @staticmethod
    def admin_free_entry_stats():
        total = User.objects.exclude(free_entry_code__isnull=True).exclude(free_entry_code='').count()
        available = User.objects.filter(free_entry_code__isnull=False, free_entry_used=False, free_entry_expires_at__gt=timezone.now()).exclude(free_entry_code='').count()
        used = User.objects.filter(free_entry_used=True).count()
        expired = User.objects.filter(free_entry_code__isnull=False, free_entry_used=False, free_entry_expires_at__lt=timezone.now()).exclude(free_entry_code='').count()
        return {'total_free_entries': total, 'available': available, 'used': used, 'expired': expired}

    @staticmethod
    @transaction.atomic
    def admin_grant_free_entry(user, amount=10, days=30):
        user.free_entry_code = generate_free_entry_code()
        user.free_entry_used = False
        user.free_entry_max_amount = amount
        user.free_entry_expires_at = timezone.now() + timedelta(days=days)
        user.free_entry_used_at = None
        user.free_entry_used_tournament = None
        user.save()
        try:
            from apps.notifications.services import NotificationService
            NotificationService.create_notification(user=user, title="🎁 Free Entry Mil Gayi!", message=f'Admin ne aapko ₹{amount} ki FREE ENTRY di hai.\n\nCode: {user.free_entry_code}', notification_type='free_entry_granted')
        except Exception: pass
        return {'success': True, 'code': user.free_entry_code, 'expires_at': user.free_entry_expires_at.isoformat()}

    @staticmethod
    @transaction.atomic
    def admin_revoke_free_entry(user):
        user.free_entry_code = None
        user.free_entry_used = False
        user.free_entry_max_amount = 0
        user.free_entry_expires_at = None
        user.free_entry_used_at = None
        user.free_entry_used_tournament = None
        user.save()
        return {'success': True, 'message': 'Free entry revoked'}