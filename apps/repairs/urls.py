from django.urls import path

from . import views

urlpatterns = [
    path('', views.RepairTicketListAPIView.as_view(), name='repair-ticket-list'),
    path('create/', views.RepairTicketCreateAPIView.as_view(), name='repair-ticket-create'),
    path('dashboard-counts/', views.RepairTicketDashboardCountsAPIView.as_view(), name='repair-ticket-dashboard-counts'),
    path('<int:pk>/', views.RepairTicketDetailAPIView.as_view(), name='repair-ticket-detail'),
    path('<int:pk>/update/', views.RepairTicketUpdateAPIView.as_view(), name='repair-ticket-update'),
    path('<int:pk>/partial-update/', views.RepairTicketPartialUpdateAPIView.as_view(), name='repair-ticket-partial-update'),
    path('<int:pk>/delete/', views.RepairTicketDeleteAPIView.as_view(), name='repair-ticket-delete'),
    path('<int:pk>/status/', views.RepairTicketStatusUpdateAPIView.as_view(), name='repair-ticket-status'),
    path('<int:pk>/assign-technician/', views.RepairTicketAssignTechnicianAPIView.as_view(), name='repair-ticket-assign-technician'),
    path('<int:pk>/notes/', views.RepairNoteListAPIView.as_view(), name='repair-note-list'),
    path('<int:pk>/notes/create/', views.RepairNoteCreateAPIView.as_view(), name='repair-note-create'),
]
