# apps/tournaments/urls.py

from django.urls import path
from .views import (
    TournamentListView,
    TournamentDetailView,
    TournamentRegisterView,
    MyRegistrationsView,
    MyMatchRoomView,
    AdminMatchRoomView,
    AdminToggleCanPlayView,
    AdminApproveFreeEntryView,   # ✅ NAYA IMPORT
    AdminTournamentResultsView,
    AdminPublishResultsView,
    AdminTournamentListView,
    AdminTournamentDetailView,
)

urlpatterns = [
    # ═══════════════════════════════════════════════════════════
    # USER APIs
    # ═══════════════════════════════════════════════════════════

    path(
        'tournaments/my-registrations/',
        MyRegistrationsView.as_view(),
        name='my-registrations',
    ),
    path(
        'tournaments/',
        TournamentListView.as_view(),
        name='tournament-list',
    ),
    path(
        'tournaments/<uuid:pk>/',
        TournamentDetailView.as_view(),
        name='tournament-detail',
    ),
    path(
        'tournaments/<uuid:pk>/register/',
        TournamentRegisterView.as_view(),
        name='tournament-register',
    ),
    path(
        'tournaments/<uuid:pk>/room/',
        MyMatchRoomView.as_view(),
        name='match-room',
    ),

    # ═══════════════════════════════════════════════════════════
    # ADMIN APIs
    # ═══════════════════════════════════════════════════════════

    path(
        'admin/tournaments/',
        AdminTournamentListView.as_view(),
        name='admin-tournament-list',
    ),
    path(
        'admin/tournaments/<uuid:pk>/',
        AdminTournamentDetailView.as_view(),
        name='admin-tournament-detail',
    ),
    path(
        'admin/tournaments/<uuid:pk>/room/',
        AdminMatchRoomView.as_view(),
        name='admin-match-room',
    ),
    path(
        'admin/tournaments/<uuid:pk>/results/',
        AdminTournamentResultsView.as_view(),
        name='admin-tournament-results',
    ),
    path(
        'admin/tournaments/<uuid:pk>/publish-results/',
        AdminPublishResultsView.as_view(),
        name='admin-publish-results',
    ),

    # ✅ Free entry approval (admin)
    path(
        'admin/free-entries/<uuid:registration_id>/approve/',
        AdminApproveFreeEntryView.as_view(),
        name='admin-free-entry-approve',
    ),

    # ✅ Toggle can play
    path(
        'admin/registrations/<uuid:registration_id>/toggle-can-play/',
        AdminToggleCanPlayView.as_view(),
        name='admin-toggle-can-play',
    ),
]