from django.urls import path
from . import views

urlpatterns = [
    path('add/', views.CartAddAPIView.as_view(), name='cart-add'),
    path('', views.CartDetailAPIView.as_view(), name='cart-detail'),
    path('update-quantity/', views.CartUpdateQuantityAPIView.as_view(), name='cart-update-quantity'),
    path('remove/<int:cart_item_id>/', views.CartRemoveItemAPIView.as_view(), name='cart-remove-item'),
    path('clear/', views.CartClearAPIView.as_view(), name='cart-clear'),
]
