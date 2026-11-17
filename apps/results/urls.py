# apps/results/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # ═══════════════════════════════════════════════════════
    # ADMIN ENDPOINTS
    # ═══════════════════════════════════════════════════════

    # 1. Result upload (OCR)
    path('upload/', views.AdminResultUploadView.as_view(), name='result-upload'),

    # 2. Match results list (admin)
    path('matches/<uuid:match_id>/', views.AdminResultListView.as_view(), name='admin-match-results'),

    # 3. Add result manually
    path('matches/<uuid:match_id>/add-result/', views.AdminAddResultView.as_view(), name='add-result'),

    # 4. Publish results
    path('matches/<uuid:match_id>/publish/', views.AdminResultPublishView.as_view(), name='publish-results'),

    # 5. Mark prize paid
    path('results/<uuid:result_id>/mark-paid/', views.AdminMarkPrizePaidView.as_view(), name='mark-paid'),

    # 6. Prize config
    path('tournaments/<uuid:tournament_id>/prize-config/', views.AdminPrizeConfigView.as_view(), name='prize-config'),

    # ═══════════════════════════════════════════════════════
    # USER ENDPOINTS
    # ═══════════════════════════════════════════════════════

    # 7. User stats
    path('stats/', views.UserStatsView.as_view(), name='user-stats'),

    # 8. My results
    path('my/', views.UserMyResultsView.as_view(), name='my-results'),

    # 9. ✅ User winnings summary (NAYA)
    path('my-winnings/', views.UserWinningsSummaryView.as_view(), name='my-winnings'),

    # 10. Unread count
    path('unread/', views.UnreadResultsCountView.as_view(), name='unread-count'),

    # 11. Leaderboard
    path('leaderboard/<uuid:match_id>/', views.UserResultListView.as_view(), name='leaderboard'),

    # 12. Match status
    path('match-status/<uuid:match_id>/', views.UserMatchStatusView.as_view(), name='user-match-status'),

    # 13. Withdrawal history
    path('withdrawals/', views.WithdrawalHistoryView.as_view(), name='withdrawals'),
    path(
        'match-status/<uuid:match_id>/',
        views.UserMatchStatusView.as_view(),
        name='user-match-status',
    ),
]