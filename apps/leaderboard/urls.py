from django.urls import path
from .views import WeeklyLeaderboardView

urlpatterns = [
    path('weekly/', WeeklyLeaderboardView.as_view(), name='weekly-leaderboard'),
]