from django.urls import path

from . import views

urlpatterns = [
    path('', views.TradeInListCreateAPIView.as_view(), name='tradein-list'),
    path('my-submissions/', views.MyTradeInsAPIView.as_view(), name='tradein-mine'),
    path('dashboard-counts/', views.TradeInDashboardCountsAPIView.as_view(), name='tradein-counts'),
    path('<int:pk>/', views.TradeInDetailAPIView.as_view(), name='tradein-detail'),
    path('<int:pk>/status/', views.TradeInStatusAPIView.as_view(), name='tradein-status'),
    path('<int:pk>/quote/', views.TradeInQuoteAPIView.as_view(), name='tradein-quote'),
    path('<int:pk>/accept/', views.TradeInAcceptAPIView.as_view(), name='tradein-accept'),
    path('<int:pk>/reject/', views.TradeInRejectAPIView.as_view(), name='tradein-reject'),
    path('<int:pk>/pay/', views.TradeInPayAPIView.as_view(), name='tradein-pay'),
]
