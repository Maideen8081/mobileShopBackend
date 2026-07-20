from django.urls import path
from . import views

urlpatterns = [
    path('', views.ProductListAPIView.as_view(), name='product-list'),
    path('create/', views.ProductCreateAPIView.as_view(), name='product-create'),
    path('search/', views.ProductSearchAPIView.as_view(), name='product-search'),
    path('low-stock/', views.LowStockProductsAPIView.as_view(), name='product-low-stock'),
    path('dashboard-counts/', views.ProductDashboardCountsAPIView.as_view(), name='product-dashboard-counts'),
    path('<int:pk>/', views.ProductDetailAPIView.as_view(), name='product-detail'),
    path('<int:pk>/update/', views.ProductUpdateAPIView.as_view(), name='product-update'),
    path('<int:pk>/delete/', views.ProductDeleteAPIView.as_view(), name='product-delete'),
    path('<int:variant_pk>/images/upload/', views.VariantImageUploadAPIView.as_view(), name='variant-image-upload'),
    path('images/<int:pk>/delete/', views.VariantImageDeleteAPIView.as_view(), name='variant-image-delete'),
]
