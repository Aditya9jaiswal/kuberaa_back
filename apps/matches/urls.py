from django.urls import path
from .views import (
    MatchListView,
    MatchDetailView,
    MatchRoomView,
    AdminMatchListCreateView,
    AdminMatchUpdateView,
    AdminMatchParticipantsView,
    AdminParticipantActionView,
)

urlpatterns = [
    # ========== USER ==========
    path('matches/', MatchListView.as_view(), name='match-list'),
    path('matches/<uuid:pk>/', MatchDetailView.as_view(), name='match-detail'),
    path('matches/<uuid:pk>/room/', MatchRoomView.as_view(), name='match-room'),

    # ========== ADMIN ==========
    path('admin/matches/', AdminMatchListCreateView.as_view(), name='admin-match-list-create'),
    path('admin/matches/<uuid:pk>/', AdminMatchUpdateView.as_view(), name='admin-match-detail'),
    path('admin/matches/<uuid:pk>/participants/', AdminMatchParticipantsView.as_view(), name='admin-match-participants'),
    path('admin/matches/<uuid:pk>/participants/<uuid:participant_id>/action/', AdminParticipantActionView.as_view(), name='admin-participant-action'),
]