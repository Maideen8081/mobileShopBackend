from django.urls import path
from . import views

urlpatterns = [
    path('coupon/apply/', views.CouponApplyAPIView.as_view(), name='coupon-apply'),
    path('payment/create-order/', views.CreateRazorpayOrderAPIView.as_view(), name='payment-create-order'),
    path('payment/verify/', views.VerifyPaymentAPIView.as_view(), name='payment-verify'),
    path('order/create/', views.CreateOrderAPIView.as_view(), name='order-create'),
    path('order/user/', views.UserOrderListAPIView.as_view(), name='order-user'),
    path('order/<int:order_id>/', views.OrderDetailAPIView.as_view(), name='order-detail'),
    path('orders/create/', views.SimpleCreateOrderAPIView.as_view(), name='simple-order-create'),
    path('orders/list/', views.AllOrdersListAPIView.as_view(), name='all-orders-list'),
    path('orders/detail/<int:order_id>/', views.OrderDetailByNumberAPIView.as_view(), name='order-detail-by-number'),
    path('orders/update-status/<str:order_number>/', views.UpdateOrderStatusAPIView.as_view(), name='update-order-status'),
]
