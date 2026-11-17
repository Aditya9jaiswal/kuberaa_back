# kuberaa/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ═══════════════════════════════════════════════════════════
    # DJANGO ADMIN
    # ═══════════════════════════════════════════════════════════
    path('admin/', admin.site.urls),

    # ═══════════════════════════════════════════════════════════
    # JWT REFRESH
    # ═══════════════════════════════════════════════════════════
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ═══════════════════════════════════════════════════════════
    # LEADERBOARD
    # ═══════════════════════════════════════════════════════════
    path('api/leaderboard/', include('apps.leaderboard.urls')),

    # ═══════════════════════════════════════════════════════════
    # AUTHENTICATION
    # ═══════════════════════════════════════════════════════════
    path('api/auth/', include('apps.authentication.urls')),

    # ═══════════════════════════════════════════════════════════
    # NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════
    path('api/notifications/', include('apps.notifications.urls')),

    # ═══════════════════════════════════════════════════════════
    # ✅ RESULTS ADMIN — specific prefix (PEHLE)
    # ═══════════════════════════════════════════════════════════
    path('api/admin/results/', include('apps.results.urls')),

    # ═══════════════════════════════════════════════════════════
    # ✅ TOURNAMENTS — cache wale admin views (admin_panel se PEHLE)
    # URL: /api/tournaments/, /api/admin/tournaments/ (cache wala)
    # ═══════════════════════════════════════════════════════════
    path('api/', include('apps.tournaments.urls')),

    # ═══════════════════════════════════════════════════════════
    # ✅ MATCHES — cache wale admin views (admin_panel se PEHLE)
    # URL: /api/matches/, /api/admin/matches/
    # ═══════════════════════════════════════════════════════════
    path('api/', include('apps.matches.urls')),

    # ═══════════════════════════════════════════════════════════
    # ✅ ADMIN PANEL — BAAD ME (sirf users, payments, baaki)
    # URL: /api/admin/users/, /api/admin/payments/
    # ═══════════════════════════════════════════════════════════
    path('api/admin/', include('apps.admin_panel.urls')),

    # ═══════════════════════════════════════════════════════════
    # ✅ USERS
    # ═══════════════════════════════════════════════════════════
    path('api/', include('apps.users.urls')),

    # ═══════════════════════════════════════════════════════════
    # ✅ COMPLAINTS
    # ═══════════════════════════════════════════════════════════
    path('api/', include('apps.complaints.urls')),

    # ═══════════════════════════════════════════════════════════
    # ✅ USER RESULTS — /api/results/my/, /api/results/leaderboard/<id>/
    # ═══════════════════════════════════════════════════════════
    path('api/results/', include('apps.results.user_urls')),

    # ═══════════════════════════════════════════════════════════
    # ✅ PAYMENTS
    # ═══════════════════════════════════════════════════════════
    path('api/payments/', include('apps.payments.urls')),
]

# ═══════════════════════════════════════════════════════════
# MEDIA FILES (DEBUG ONLY)
# ═══════════════════════════════════════════════════════════
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )