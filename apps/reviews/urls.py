from django.urls import path
from . import views

urlpatterns = [
    path('', views.ReviewListAPIView.as_view(), name='review-list'),
    path('create/', views.ReviewCreateAPIView.as_view(), name='review-create'),
    path('<int:pk>/', views.ReviewDetailAPIView.as_view(), name='review-detail'),
    path('<int:pk>/update/', views.ReviewUpdateAPIView.as_view(), name='review-update'),
    path('<int:pk>/delete/', views.ReviewDeleteAPIView.as_view(), name='review-delete'),
    path('<int:review_pk>/images/upload/', views.ReviewImageUploadAPIView.as_view(), name='review-image-upload'),
    path('images/<int:pk>/delete/', views.ReviewImageDeleteAPIView.as_view(), name='review-image-delete'),
]
