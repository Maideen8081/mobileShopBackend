from django.urls import path
from . import views

urlpatterns = [
    path('coupon/apply/', views.CouponApplyAPIView.as_view(), name='coupon-apply'),
    path('payment/create-order/', views.CreateRazorpayOrderAPIView.as_view(), name='payment-create-order'),
    path('payment/verify/', views.VerifyPaymentAPIView.as_view(), name='payment-verify'),
    path('order/create/', views.CreateOrderAPIView.as_view(), name='order-create'),
    path('order/user/', views.UserOrderListAPIView.as_view(), name='order-user'),
    path('order/<int:order_id>/', views.OrderDetailAPIView.as_view(), name='order-detail'),
]
