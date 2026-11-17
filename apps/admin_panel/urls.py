# apps/admin_panel/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

# ❌ YE HATAO — cache wale views tournaments/urls.py aur matches/urls.py me hain
# router.register('tournaments', views.AdminTournamentViewSet, basename='admin-tournaments')
# router.register('matches', views.AdminMatchViewSet, basename='admin-matches')

# ✅ Sirf users + payments (jo cache me nahi chahiye)
router.register('users', views.AdminUserViewSet, basename='admin-users')
router.register('payments', views.AdminPaymentViewSet, basename='admin-payments')

urlpatterns = [
    # ═══════════════════════════════════════════════════════
    # USERS — custom actions
    # ═══════════════════════════════════════════════════════
    path('users/search/', views.UserSearchView.as_view(), name='user-search'),
    path('users/<uuid:user_id>/block/', views.AdminBlockUserView.as_view(), name='block-user'),
    path('users/<uuid:user_id>/role/', views.AdminUserRoleView.as_view(), name='user-role'),

    # ═══════════════════════════════════════════════════════
    # REGISTRATIONS
    # ═══════════════════════════════════════════════════════
    path(
        'registrations/<uuid:registration_id>/toggle-can-play/',
        views.AdminToggleCanPlayView.as_view(),
        name='toggle-can-play',
    ),

    # ═══════════════════════════════════════════════════════
    # TOURNAMENTS — custom actions (list/detail cache wale hain)
    # ═══════════════════════════════════════════════════════
    path(
        'tournaments/<uuid:tournament_id>/registrations/',
        views.AdminTournamentRegistrationsView.as_view(),
        name='tournament-registrations',
    ),
    path(
        'tournaments/<uuid:tournament_id>/prize-config/',
        views.AdminPrizeConfigView.as_view(),
        name='prize-config',
    ),
    path(
        'tournaments/<uuid:tournament_id>/publish-results/',
        views.AdminPublishResultsFromTournamentView.as_view(),
        name='tournament-publish-results',
    ),

    # ═══════════════════════════════════════════════════════
    # APP VERSION
    # ═══════════════════════════════════════════════════════
    path('app-version/', views.AppVersionCheckView.as_view(), name='app-version'),

    # ═══════════════════════════════════════════════════════
    # PAYMENTS
    # ═══════════════════════════════════════════════════════
    path(
        'payments/<uuid:payment_id>/verify/',
        views.AdminVerifyPaymentView.as_view(),
        name='verify-payment',
    ),

    # ═══════════════════════════════════════════════════════
    # MATCHES — custom actions (list/detail cache wale hain)
    # ═══════════════════════════════════════════════════════
    path(
        'matches/<uuid:match_id>/publish-results/',
        views.AdminPublishResultsView.as_view(),
        name='publish-results',
    ),
    path(
        'matches/<uuid:match_id>/results/',
        views.AdminMatchResultsView.as_view(),
        name='match-results',
    ),

    # ❌ RESULTS ROUTES — already /api/admin/results/ pe jaayenge
    # path('results/upload/', ...),
    # path('results/bulk-save/', ...),
    # path('results/<uuid:result_id>/delete/', ...),

    # ═══════════════════════════════════════════════════════
    # NOTIFICATIONS
    # ═══════════════════════════════════════════════════════
    path(
        'notifications/',
        views.AdminNotificationViewSet.as_view(),
        name='notifications',
    ),

    # ═══════════════════════════════════════════════════════
    # ROUTER — fallback (users + payments)
    # ═══════════════════════════════════════════════════════
    path('', include(router.urls)),
]