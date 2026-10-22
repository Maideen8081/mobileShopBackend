from django.urls import path

from . import views

# Mounted under /api/v1/admin/ — every view is IsAdminUser.
urlpatterns = [
    path('dashboard/', views.DashboardAPIView.as_view(), name='admin-dashboard'),
    path('customers/', views.CustomerListAPIView.as_view(), name='admin-customer-list'),
    path('customers/<int:pk>/', views.CustomerDetailAPIView.as_view(), name='admin-customer-detail'),
]
