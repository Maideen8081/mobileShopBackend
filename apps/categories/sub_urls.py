from django.urls import path
from . import views

urlpatterns = [
    path('', views.SubCategoryListAPIView.as_view(), name='sub-category-list'),
    path('create/', views.SubCategoryCreateAPIView.as_view(), name='sub-category-create'),
]
