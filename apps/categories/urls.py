from django.urls import path
from . import views

urlpatterns = [
    path('', views.CategoryListAPIView.as_view(), name='category-list'),
    path('create/', views.CategoryCreateAPIView.as_view(), name='category-create'),
    path('dashboard-counts/', views.CategoryDashboardCountsAPIView.as_view(), name='category-dashboard-counts'),
    path('dropdown/', views.CategoryDropdownAPIView.as_view(), name='category-dropdown'),
    path('<int:pk>/', views.CategoryRetrieveUpdateDestroyAPIView.as_view(), name='category-detail'),
]
