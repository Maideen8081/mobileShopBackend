from django.urls import path

from . import views

urlpatterns = [
    # Public
    path('services/', views.RepairServiceListAPIView.as_view(), name='repair-service-list'),

    # Customer (authenticated)
    path('book/', views.RepairBookAPIView.as_view(), name='repair-book'),
    path('my-tickets/', views.RepairMyTicketsAPIView.as_view(), name='repair-my-tickets'),
    path('my-tickets/<int:pk>/', views.RepairMyTicketDetailAPIView.as_view(), name='repair-my-ticket-detail'),

    # Notifications (authenticated)
    path('notifications/', views.NotificationListAPIView.as_view(), name='repair-notification-list'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadAPIView.as_view(), name='repair-notification-mark-read'),
    path('notifications/read-all/', views.NotificationMarkAllReadAPIView.as_view(), name='repair-notification-mark-all-read'),

    # Admin — tickets
    path('', views.RepairTicketListAPIView.as_view(), name='repair-ticket-list'),
    path('create/', views.RepairTicketCreateAPIView.as_view(), name='repair-ticket-create'),
    path('dashboard-counts/', views.RepairDashboardCountsAPIView.as_view(), name='repair-ticket-dashboard-counts'),
    path('<int:pk>/', views.RepairTicketDetailAPIView.as_view(), name='repair-ticket-detail'),
    path('<int:pk>/update/', views.RepairTicketUpdateAPIView.as_view(), name='repair-ticket-update'),
    path('<int:pk>/delete/', views.RepairTicketDeleteAPIView.as_view(), name='repair-ticket-delete'),
    path('<int:pk>/status/', views.RepairTicketStatusUpdateAPIView.as_view(), name='repair-ticket-status'),
    path('<int:pk>/assign-technician/', views.RepairTicketAssignTechnicianAPIView.as_view(), name='repair-ticket-assign-technician'),

    # Customer approval
    path('<int:pk>/customer-approve/', views.RepairTicketCustomerApproveAPIView.as_view(), name='repair-ticket-customer-approve'),

    # Notes
    path('<int:pk>/notes/', views.RepairNoteListAPIView.as_view(), name='repair-note-list'),
    path('<int:pk>/notes/create/', views.RepairNoteCreateAPIView.as_view(), name='repair-note-create'),
]
