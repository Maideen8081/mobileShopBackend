from django.urls import path
from . import views

# Admin area authentication — mounted under /api/v1/admin/auth/ by config.urls,
# isolated from the client login flow and protected by IsAdminUser (server-side
# role/staff/superuser checks) plus its own policies.
urlpatterns = [
    path('login/', views.AdminLoginAPIView.as_view(), name='admin-auth-login'),
    path('logout/', views.AdminLogoutAPIView.as_view(), name='admin-auth-logout'),
    path('profile/', views.AdminProfileAPIView.as_view(), name='admin-auth-profile'),
]