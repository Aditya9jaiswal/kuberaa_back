# apps/results/admin_urls.py
from django.urls import path
from apps.results import views

app_name = 'results_admin'

urlpatterns = [
    path('upload/', views.AdminResultUploadView.as_view(), name='upload'),
    path('match/<uuid:match_id>/', views.AdminResultListView.as_view(), name='match-results'),
    path('match/<uuid:match_id>/publish/', views.AdminResultPublishView.as_view(), name='publish'),
    path('results/<uuid:result_id>/mark-paid/', views.AdminMarkPrizePaidView.as_view(), name='mark-paid'),
    path('tournament/<uuid:tournament_id>/prize-config/', views.AdminPrizeConfigView.as_view(), name='prize-config'),
]