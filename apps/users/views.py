# apps/users/views.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum
from django.utils import timezone

from core.responses import success_response, error_response
from core.pagination import StandardPagination
from core.permissions import IsAdminRole
from .models import User
from .serializers import (
    UserSerializer,
    UserProfileUpdateSerializer,
    KycUpdateSerializer,
)


# ==================================================
# USER PROFILE
# ==================================================

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(data=UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)
        serializer.save()
        return success_response(
            data=UserSerializer(request.user).data,
            message='Profile updated'
        )


# ==================================================
# ✅ KYC — COMPLETE PROFILE
# ==================================================

class KycUpdateView(APIView):
    """KYC — Complete profile for tournament registration"""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = KycUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return error_response('Validation failed', 400, serializer.errors)
        serializer.save()
        return success_response(
            data=UserSerializer(request.user).data,
            message='KYC completed successfully'
        )


# ==================================================
# MY REFERRAL
# ==================================================

class MyReferralView(APIView):
    """User: Apna referral + free entry data + Global Link"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.users.services.referral_service import ReferralService
        from apps.users.models import GlobalReferralLink

        user = request.user
        if not user.referral_code:
            user.save()

        data = ReferralService.get_user_referral_data(user)
        
        # ✅ Admin ka Global Link yahan se aayega
        data['global_download_link'] = GlobalReferralLink.get_link() 
        
        return success_response(data=data)


# ==================================================
# ✅ KUBERAA POINTS — USER
# ==================================================

class UserKuberaaPointsView(APIView):
    """User — apna Kuberaa Points balance dekhe"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return success_response(data={
            'kuberaa_points': user.kuberaa_points or 0,
            'has_played_first_match': user.has_played_first_match,
            'first_match_free_used': user.first_match_free_used,
            'is_new_user': user.is_new_user,
            'can_use_first_free': user.can_use_first_free,
            'can_use_points': user.can_use_points,
        })


class UserKuberaaPointsHistoryView(APIView):
    """User — points history (kaise kamaye, kaise use kiye)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.results.models import Result
        from apps.tournaments.models import Registration

        user = request.user

        # ✅ Points earned (results se)
        earned = Result.objects.filter(
            user=user,
            points_earned__gt=0,
            verification_status=Result.VerificationStatus.PUBLISHED,
        ).select_related('match', 'match__tournament').order_by('-published_at')

        earned_data = [
            {
                'id': str(r.id),
                'type': 'EARNED',
                'points': r.points_earned,
                'match_title': r.match.title if r.match else 'Match',
                'tournament_title': (
                    r.match.tournament.title
                    if r.match and r.match.tournament else ''
                ),
                'kills': r.kills,
                'placement': r.placement,
                'created_at': (
                    r.published_at.isoformat()
                    if r.published_at else r.created_at.isoformat()
                ),
            }
            for r in earned
        ]

        # ✅ Points used (registrations se)
        used = Registration.objects.filter(
            user=user,
            points_used__gt=0,
        ).select_related('tournament').order_by('-created_at')

        used_data = [
            {
                'id': str(reg.id),
                'type': 'USED',
                'points': reg.points_used,
                'match_title': reg.tournament.title,
                'tournament_title': reg.tournament.title,
                'created_at': reg.created_at.isoformat(),
            }
            for reg in used
        ]

        # ✅ Merge and sort
        all_history = earned_data + used_data
        all_history.sort(key=lambda x: x['created_at'], reverse=True)

        return success_response(data={
            'current_balance': user.kuberaa_points or 0,
            'total_earned': sum(h['points'] for h in earned_data),
            'total_used': sum(h['points'] for h in used_data),
            'history': all_history,
        })


# ==================================================
# ADMIN USER MANAGEMENT
# ==================================================

class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        status_filter = request.query_params.get('status')
        role_filter = request.query_params.get('role')
        search = request.query_params.get('search')

        qs = User.objects.all().order_by('-created_at')

        if status_filter:
            qs = qs.filter(status=status_filter)
        if role_filter:
            qs = qs.filter(role=role_filter)
        if search:
            qs = qs.filter(
                Q(email__icontains=search) |
                Q(display_name__icontains=search) |
                Q(mobile_number__icontains=search) |
                Q(free_fire_uid__icontains=search) |
                Q(bgmi_uid__icontains=search) |
                Q(pubg_uid__icontains=search)
            )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = UserSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminUserBlockView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        action = request.data.get('action')
        reason = request.data.get('reason', '')

        try:
            user = User.objects.get(id=pk)
        except User.DoesNotExist:
            return error_response('User not found', 404)

        if user.role == User.Role.SUPER_ADMIN:
            return error_response('Cannot block Super Admin', 403)

        if user.id == request.user.id:
            return error_response('Cannot block yourself', 403)

        if action == 'block':
            user.status = User.Status.BLOCKED
            user.is_active = False
            user.save()
            message = f'User {user.email} blocked'
        elif action == 'unblock':
            user.status = User.Status.ACTIVE
            user.is_active = True
            user.save()
            message = f'User {user.email} unblocked'
        else:
            return error_response('Invalid action', 400)

        return success_response(
            data=UserSerializer(user).data,
            message=message,
        )


class AdminUserUpdateRoleView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        new_role = request.data.get('role')

        valid_roles = [r[0] for r in User.Role.choices]
        if new_role not in valid_roles:
            return error_response(f'Invalid role', 400)

        try:
            user = User.objects.get(id=pk)
        except User.DoesNotExist:
            return error_response('User not found', 404)

        if new_role in ['SUPER_ADMIN', 'ADMIN'] and not request.user.is_super_admin:
            return error_response('Only Super Admin', 403)

        old_role = user.role
        user.role = new_role

        if new_role in ['SUPER_ADMIN', 'ADMIN', 'MODERATOR', 'RESULT_MANAGER', 'SUPPORT']:
            user.is_staff = True
        elif new_role == 'USER':
            user.is_staff = False

        user.save()

        return success_response(
            data=UserSerializer(user).data,
            message=f'Role changed to {new_role}',
        )


# ==================================================
# FCM TOKEN
# ==================================================

class UpdateFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('fcm_token', '').strip()
        if not token:
            return error_response('FCM token required', 400)

        request.user.fcm_token = token
        request.user.save(update_fields=['fcm_token'])

        return success_response(message='FCM token updated')


# ==================================================
# ADMIN — REFERRAL MANAGEMENT
# ==================================================

class AdminReferralListView(APIView):
    """Admin: Saare referrals"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        search = request.query_params.get('search', '').strip()

        qs = User.objects.filter(
            referrals__isnull=False
        ).annotate(
            actual_referrals=Count('referrals', distinct=True),
        ).distinct().order_by('-actual_referrals')

        if search:
            qs = qs.filter(
                Q(email__icontains=search) |
                Q(display_name__icontains=search) |
                Q(referral_code__icontains=search)
            )

        data = []
        for referrer in qs:
            referred = referrer.referrals.all().order_by('-created_at')

            data.append({
                'referrer_id': str(referrer.id),
                'referrer_name': referrer.display_name or 'Unknown',
                'referrer_email': referrer.email,
                'referrer_mobile': referrer.mobile_number or '',
                'referrer_code': referrer.referral_code or '',
                'referrer_link': referrer.admin_referral_link or '',
                'referrer_free_entry': {
                    'code': referrer.free_entry_code or '',
                    'used': referrer.free_entry_used,
                    'used_at': (
                        referrer.free_entry_used_at.isoformat()
                        if referrer.free_entry_used_at else None
                    ),
                    'used_tournament': (
                        referrer.free_entry_used_tournament.title
                        if referrer.free_entry_used_tournament else None
                    ),
                },
                'total_referrals': referrer.referrals.count(),
                'referred_users': [
                    {
                        'id': str(u.id),
                        'name': u.display_name or 'Player',
                        'email': u.email,
                        'mobile': u.mobile_number or '',
                        'ff_name': u.free_fire_name or '',
                        'free_entry_code': u.free_entry_code or '',
                        'free_entry_used': u.free_entry_used,
                        'joined_at': (
                            u.created_at.isoformat() if u.created_at else None
                        ),
                    }
                    for u in referred
                ],
            })

        return success_response(data=data)


class AdminReferralStatsView(APIView):
    """Admin: Referral stats"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        total_referrals = User.objects.filter(referred_by__isnull=False).count()

        total_free_entries = User.objects.filter(
            free_entry_code__isnull=False
        ).exclude(free_entry_code='').count()

        total_free_entries_used = User.objects.filter(
            free_entry_used=True
        ).count()

        top = User.objects.annotate(
            actual_referrals=Count('referrals', distinct=True)
        ).filter(actual_referrals__gt=0).order_by('-actual_referrals')[:10]

        top_data = [
            {
                'id': str(u.id),
                'name': u.display_name or 'Unknown',
                'email': u.email,
                'referral_code': u.referral_code or '',
                'referrals': u.referrals.count(),
                'free_entry_code': u.free_entry_code or '',
                'free_entry_used': u.free_entry_used,
            }
            for u in top
        ]

        return success_response(data={
            'total_referrals': total_referrals,
            'total_free_entries_generated': total_free_entries,
            'total_free_entries_used': total_free_entries_used,
            'total_free_entries_pending': max(0, total_free_entries - total_free_entries_used),
            'top_referrers': top_data,
        })


class AdminUserReferralDetailView(APIView):
    """Admin: Ek user ka referral detail"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return error_response('User not found', 404)

        from apps.users.services.referral_service import ReferralService
        data = ReferralService.admin_referral_data(user)

        return success_response(data=data)


# ==================================================
# ADMIN — SEND NOTIFICATION
# ==================================================

class AdminSendNotificationView(APIView):
    """Admin: Send notification to users"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        from apps.notifications.services import NotificationService

        title = request.data.get('title', '').strip()
        message = request.data.get('message', '').strip()
        target = request.data.get('target', 'ALL')
        user_id = request.data.get('user_id')

        if not title or not message:
            return error_response('Title and message required', 400)

        if target == 'ALL':
            users = User.objects.filter(role='USER', is_active=True)
        elif target == 'SINGLE':
            if not user_id:
                return error_response('user_id required', 400)
            users = User.objects.filter(id=user_id)
        elif target == 'REFERRERS':
            users = User.objects.filter(
                total_referrals__gt=0, role='USER', is_active=True
            )
        else:
            return error_response('Invalid target', 400)

        count = 0
        for user in users:
            try:
                NotificationService.create_notification(
                    user=user,
                    title=title,
                    message=message,
                    notification_type='admin_broadcast',
                )
                count += 1
            except Exception as e:
                print(f'Notification error for {user.email}: {e}')

        return success_response(
            message=f'{count} users ko notification bhej di',
            data={'sent': count},
        )


# ==================================================
# ADMIN — USER WINNINGS
# ==================================================

class AdminUserWinningsView(APIView):
    """Admin: Kis user ne kitna jeeta — total summary"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from apps.results.models import Result

        search = request.query_params.get('search', '').strip()

        users_qs = User.objects.filter(
            results__is_paid=True,
        ).distinct()

        if search:
            users_qs = users_qs.filter(
                Q(email__icontains=search) |
                Q(display_name__icontains=search) |
                Q(mobile_number__icontains=search) |
                Q(free_fire_uid__icontains=search) |
                Q(bgmi_uid__icontains=search) |
                Q(pubg_uid__icontains=search)
            )

        data = []
        for u in users_qs.order_by('-created_at')[:200]:
            paid = Result.objects.filter(user=u, is_paid=True)

            total_won = sum(float(r.prize_amount or 0) for r in paid)
            total_kills = sum(r.kills or 0 for r in paid)

            data.append({
                'user_id': str(u.id),
                'email': u.email,
                'display_name': u.display_name or '',
                'mobile': u.mobile_number or '',
                'upi_id': u.upi_id or '',
                'free_fire_uid': u.free_fire_uid or '',
                'free_fire_name': u.free_fire_name or '',
                'bgmi_uid': u.bgmi_uid or '',
                'bgmi_name': u.bgmi_name or '',
                'pubg_uid': u.pubg_uid or '',
                'pubg_name': u.pubg_name or '',
                'total_won': total_won,
                'total_kills': total_kills,
                'total_matches': paid.count(),
                'total_wins': paid.filter(placement=1).count(),
            })

        all_paid = Result.objects.filter(is_paid=True)
        grand_total = sum(float(r.prize_amount or 0) for r in all_paid)

        return success_response(data={
            'users': data,
            'total_users': len(data),
            'grand_total_won': grand_total,
            'total_paid_results': all_paid.count(),
        })


# ==================================================
# ADMIN — KUBERAA POINTS STATS
# ==================================================

class AdminKuberaaPointsStatsView(APIView):
    """Admin — Kuberaa Points stats"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from apps.results.models import Result
        from apps.tournaments.models import Registration

        total_issued = User.objects.aggregate(
            total=Sum('kuberaa_points')
        )['total'] or 0

        total_earned = Result.objects.aggregate(
            total=Sum('points_earned')
        )['total'] or 0

        total_used = Registration.objects.aggregate(
            total=Sum('points_used')
        )['total'] or 0

        top_users = User.objects.filter(
            kuberaa_points__gt=0
        ).order_by('-kuberaa_points')[:10]

        top_data = [
            {
                'id': str(u.id),
                'name': u.display_name or 'Unknown',
                'email': u.email,
                'points': u.kuberaa_points,
            }
            for u in top_users
        ]

        return success_response(data={
            'total_points_in_circulation': total_issued,
            'total_points_earned': total_earned,
            'total_points_used': total_used,
            'active_points_users': User.objects.filter(
                kuberaa_points__gt=0
            ).count(),
            'top_users': top_data,
        })


# ==================================================
# ADMIN — LINK MANAGEMENT (UPDATED)
# ==================================================

class AdminUpdateReferralLinkView(APIView):
    """Admin — user ka link generate/update kare (custom link support)"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return error_response('User not found', 404)

        custom_link = request.data.get('custom_link', None)

        from apps.users.services.referral_service import ReferralService
        
        result = ReferralService.admin_update_referral_link(user, custom_link=custom_link)

        if not result.get('success'):
            return error_response(result.get('error', 'Failed to update link'), 400)

        return success_response(
            data=result, 
            message='Referral link updated successfully'
        )


class AdminDeleteReferralLinkView(APIView):
    """Admin — user ka custom link delete kare"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return error_response('User not found', 404)

        from apps.users.services.referral_service import ReferralService
        
        result = ReferralService.admin_delete_referral_link(user)

        if not result.get('success'):
            return error_response(result.get('error', 'Failed to delete link'), 400)

        return success_response(
            data=result, 
            message='Referral link deleted successfully'
        )


class UserShareMessageView(APIView):
    """User — apna share message fetch kare"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.users.services.referral_service import ReferralService
        message = ReferralService.get_share_message(request.user)
        return success_response(data={
            'message': message,
            'referral_code': request.user.referral_code,
            'link': request.user.admin_referral_link or (
                f'https://kuberaa.app/join?ref={request.user.referral_code}'
            ),
        })


# ==================================================
# ADMIN — FREE ENTRY MANAGEMENT
# ==================================================

class AdminFreeEntryListView(APIView):
    """Admin — saare free entry users"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from apps.users.services.referral_service import ReferralService
        search = request.query_params.get('search', '')
        status_filter = request.query_params.get('status', '')

        data = ReferralService.admin_all_free_entries(
            search=search or None,
            status=status_filter or None,
        )
        return success_response(data=data)


class AdminFreeEntryStatsView(APIView):
    """Admin — free entry stats"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from apps.users.services.referral_service import ReferralService
        data = ReferralService.admin_free_entry_stats()
        return success_response(data=data)


class AdminGrantFreeEntryView(APIView):
    """Admin — manually free entry grant"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, user_id):
        from apps.users.services.referral_service import ReferralService
        amount = float(request.data.get('amount', 10))
        days = int(request.data.get('days', 30))

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return error_response('User not found', 404)

        result = ReferralService.admin_grant_free_entry(user, amount, days)
        return success_response(data=result, message='Free entry granted')


class AdminRevokeFreeEntryView(APIView):
    """Admin — free entry revoke"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, user_id):
        from apps.users.services.referral_service import ReferralService
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return error_response('User not found', 404)

        result = ReferralService.admin_revoke_free_entry(user)
        return success_response(data=result, message='Free entry revoked')


# ==================================================
# ✅ GLOBAL REFERRAL LINK (ADMIN)
# ==================================================

class AdminGetUpdateGlobalLinkView(APIView):
    """Admin — Global Download Link Get/Update"""
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        from apps.users.models import GlobalReferralLink
        link = GlobalReferralLink.get_link()
        return success_response(data={'download_link': link})

    def post(self, request):
        from apps.users.models import GlobalReferralLink
        new_link = request.data.get('download_link', '').strip()
        
        if not new_link:
            return error_response('Download link required', 400)

        obj = GlobalReferralLink.objects.get_or_create(id=1)[0]
        obj.download_link = new_link
        obj.save()

        return success_response(
            data={'download_link': new_link},
            message='Global link updated successfully'
        )