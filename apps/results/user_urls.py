# apps/results/user_urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('stats/', views.UserStatsView.as_view(), name='user-stats'),
    path('my/', views.UserMyResultsView.as_view(), name='my-results'),
    path('my-winnings/', views.UserWinningsSummaryView.as_view(), name='my-winnings'),
    path('unread/', views.UnreadResultsCountView.as_view(), name='unread-count'),
    path('leaderboard/<uuid:match_id>/', views.UserResultListView.as_view(), name='leaderboard'),
    path('match-status/<uuid:match_id>/', views.UserMatchStatusView.as_view(), name='user-match-status'),
    path('withdrawals/', views.WithdrawalHistoryView.as_view(), name='withdrawals'),
]