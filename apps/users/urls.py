# apps/users/urls.py

from django.urls import path
from . import views  # ✅ views module import karo

from .views import (
    ProfileView,
    KycUpdateView,
    MyReferralView,
    AdminUserListView,
    AdminUserBlockView,
    AdminUserUpdateRoleView,
    UpdateFCMTokenView,
    AdminReferralListView,
    AdminReferralStatsView,
    AdminUserReferralDetailView,
    AdminSendNotificationView,
    AdminUserWinningsView,
    AdminUpdateReferralLinkView,
    AdminDeleteReferralLinkView,
    UserShareMessageView,
    AdminFreeEntryListView,
    AdminFreeEntryStatsView,
    AdminGrantFreeEntryView,
    AdminRevokeFreeEntryView,
    UserKuberaaPointsView,
    UserKuberaaPointsHistoryView,
    AdminKuberaaPointsStatsView,
    # ✅ NAYA IMPORT
    AdminGetUpdateGlobalLinkView,
)

urlpatterns = [
    # ═══════════════════════════════════════════════════════
    # USER ENDPOINTS
    # ═══════════════════════════════════════════════════════
    path('profile/', ProfileView.as_view(), name='profile'),
    
    path('users/kyc/', KycUpdateView.as_view(), name='kyc-update'),

    path('users/my-referral/', MyReferralView.as_view(), name='my-referral'),
    path('users/update-fcm-token/', UpdateFCMTokenView.as_view(), name='update-fcm-token'),

    path('users/share-message/', UserShareMessageView.as_view(), name='user-share-message'),

    # KUBERAA POINTS — USER
    path('users/kuberaa-points/', UserKuberaaPointsView.as_view(), name='kuberaa-points'),
    path('users/kuberaa-points/history/', UserKuberaaPointsHistoryView.as_view(), name='kuberaa-points-history'),


    # ═══════════════════════════════════════════════════════
    # ADMIN ENDPOINTS
    # ═══════════════════════════════════════════════════════
    
    # --- Users ---
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<uuid:pk>/block/', AdminUserBlockView.as_view(), name='admin-user-block'),
    path('admin/users/<uuid:pk>/role/', AdminUserUpdateRoleView.as_view(), name='admin-user-role'),

    # --- Admin Referral Link Management ---
    path(
        'admin/users/<uuid:user_id>/referral-link/update/',
        AdminUpdateReferralLinkView.as_view(),
        name='admin-referral-link-update',
    ),
    path(
        'admin/users/<uuid:user_id>/referral-link/delete/',
        AdminDeleteReferralLinkView.as_view(),
        name='admin-referral-link-delete',
    ),

    # --- Referral Management ---
    path('admin/referrals/', AdminReferralListView.as_view(), name='admin-referrals'),
    path('admin/referrals/stats/', AdminReferralStatsView.as_view(), name='admin-referral-stats'),
    path(
        'admin/referrals/<uuid:user_id>/',
        AdminUserReferralDetailView.as_view(),
        name='admin-user-referral-detail',
    ),

    # --- Free Entry Management ---
    path('admin/free-entries/', AdminFreeEntryListView.as_view(), name='admin-free-entries'),
    path('admin/free-entries/stats/', AdminFreeEntryStatsView.as_view(), name='admin-free-entry-stats'),
    path(
        'admin/free-entries/<uuid:user_id>/grant/',
        AdminGrantFreeEntryView.as_view(),
        name='admin-free-entry-grant',
    ),
    path(
        'admin/free-entries/<uuid:user_id>/revoke/',
        AdminRevokeFreeEntryView.as_view(),
        name='admin-free-entry-revoke',
    ),

    # --- Kuberaa Points Stats ---
    path(
        'admin/kuberaa-points/stats/',
        AdminKuberaaPointsStatsView.as_view(),
        name='admin-kuberaa-points-stats',
    ),

    # --- Send Notification ---
    path(
        'admin/send-notification/',
        AdminSendNotificationView.as_view(),
        name='admin-send-notification',
    ),

    # --- Admin User Winnings ---
    path(
        'admin/user-winnings/',
        AdminUserWinningsView.as_view(),
        name='admin-user-winnings',
    ),

    # ✅ NAYA: Global Referral Link API
    path(
        'admin/global-referral-link/',
        AdminGetUpdateGlobalLinkView.as_view(),
        name='admin-global-link',
    ),
]