from django.urls import path
from .views import ComplaintListCreateView, ComplaintDetailView

urlpatterns = [
    path('complaints/', ComplaintListCreateView.as_view()),
    path('complaints/<uuid:pk>/', ComplaintDetailView.as_view()),
]
