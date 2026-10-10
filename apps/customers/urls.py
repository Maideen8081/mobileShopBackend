from django.urls import path
from . import views

urlpatterns = [
    # Auth (client area)
    path('auth/csrf/', views.CSRFTokenAPIView.as_view(), name='auth-csrf'),
    path('auth/register/', views.RegisterAPIView.as_view(), name='auth-register'),
    path('auth/login/', views.LoginAPIView.as_view(), name='auth-login'),
    path('auth/logout/', views.LogoutAPIView.as_view(), name='auth-logout'),
    path('auth/profile/', views.UserProfileAPIView.as_view(), name='auth-profile'),
    path('auth/change-password/', views.ChangePasswordAPIView.as_view(), name='auth-change-password'),
    path('auth/password-reset/', views.PasswordResetRequestAPIView.as_view(), name='auth-password-reset'),
    path('auth/password-reset/confirm/', views.PasswordResetConfirmAPIView.as_view(), name='auth-password-reset-confirm'),
    path('auth/verify-email/<str:uid>/<str:token>/', views.VerifyEmailAPIView.as_view(), name='auth-verify-email'),

    # Address
    path('address/create/', views.AddressCreateAPIView.as_view(), name='address-create'),
    path('address/list/', views.AddressListAPIView.as_view(), name='address-list'),
    path('address/update/<int:address_id>/', views.AddressUpdateAPIView.as_view(), name='address-update'),
    path('address/delete/<int:address_id>/', views.AddressDeleteAPIView.as_view(), name='address-delete'),
    path('address/set-default/<int:address_id>/', views.AddressSetDefaultAPIView.as_view(), name='address-set-default'),
]