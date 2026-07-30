import logging

from django.db import DatabaseError
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import (
    CreateAPIView,
    DestroyAPIView,
    GenericAPIView,
    ListAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.repairs.models import (
    Notification,
    RepairNote,
    RepairService,
    RepairTicket,
    RepairTicketPhoto,
)
from apps.repairs.notifications import (
    send_status_update_notification,
    send_ticket_assigned_notification,
    send_ticket_created_notification,
)
from apps.repairs.serializers import (
    NotificationSerializer,
    RepairBookSerializer,
    RepairCustomerApproveSerializer,
    RepairNoteCreateSerializer,
    RepairNoteListSerializer,
    RepairServiceSerializer,
    RepairTicketCreateSerializer,
    RepairTicketDetailSerializer,
    RepairTicketListSerializer,
    RepairTicketTechnicianSerializer,
    RepairTicketUpdateSerializer,
    RepairStatusUpdateSerializer,
)
from apps.repairs.services import RepairTicketService

logger = logging.getLogger(__name__)


class RepairServiceListAPIView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = RepairServiceSerializer
    queryset = RepairService.objects.filter(is_active=True)

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
            })
        except DatabaseError as e:
            logger.error('[repairService] Database error listing services: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RepairBookAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, *args, **kwargs):
        serializer = RepairBookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = data.get('service')

        try:
            ticket = RepairTicket.objects.create(
                source='online',
                service=service,
                user=request.user,
                customer_name=data['customer_name'],
                mobile_number=data['mobile_number'],
                alternate_number=data.get('alternate_number', ''),
                email=data.get('email', ''),
                address=data.get('address', ''),
                device_brand=data['device_brand'],
                device_model=data['device_model'],
                imei_number=data.get('imei_number', ''),
                serial_number=data.get('serial_number', ''),
                device_color=data.get('device_color', ''),
                warranty_status=data.get('warranty_status', 'unknown'),
                issue_category=data['issue_category'],
                problem_description=data['problem_description'],
                courier_company=data.get('courier_company', ''),
                courier_tracking_number=data.get('courier_tracking_number', ''),
                courier_pickup_date=data.get('courier_pickup_date'),
                courier_expected_delivery_date=data.get('courier_expected_delivery_date'),
            )

            RepairTicketService.create_ticket_with_history(ticket, updated_by=request.user.get_full_name() or request.user.email)

            photos = request.FILES.getlist('photos')
            if photos:
                RepairTicketService.create_photos(ticket, photos)

            send_ticket_created_notification(ticket)

            detail = RepairTicketDetailSerializer(ticket, context={'request': request})
            return Response({
                'success': True,
                'message': 'Repair ticket created successfully',
                'data': detail.data,
            }, status=status.HTTP_201_CREATED)

        except DatabaseError as e:
            logger.error('[repairService] Database error creating online ticket: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error('[repairService] Unexpected error creating online ticket: %s', e)
            return Response({
                'success': False,
                'message': 'An error occurred while creating the repair ticket.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RepairMyTicketsAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RepairTicketListSerializer

    def get_queryset(self):
        return RepairTicket.objects.filter(user=self.request.user).select_related('service').prefetch_related('photos')

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
            })
        except DatabaseError as e:
            logger.error('[repairService] Database error listing my tickets: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RepairMyTicketDetailAPIView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RepairTicketDetailSerializer

    def get_queryset(self):
        return RepairTicket.objects.filter(user=self.request.user).prefetch_related('photos', 'notes', 'status_history')

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({
                'success': True,
                'data': serializer.data,
            })
        except RepairTicket.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Repair ticket not found.',
            }, status=status.HTTP_404_NOT_FOUND)
        except DatabaseError as e:
            logger.error('[repairService] Database error fetching my ticket: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RepairTicketListAPIView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = RepairTicketListSerializer
    search_fields = [
        'ticket_number', 'customer_name', 'mobile_number',
        'device_brand', 'device_model', 'email',
    ]
    ordering_fields = ['created_at', 'estimated_cost', 'priority', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = RepairTicket.objects.select_related('service').prefetch_related('photos').all()

        status_param = self.request.query_params.get('status')
        source = self.request.query_params.get('source')
        priority = self.request.query_params.get('priority')
        search = self.request.query_params.get('search')

        if status_param:
            qs = qs.filter(status=status_param)
        if source:
            qs = qs.filter(source=source)
        if priority:
            qs = qs.filter(priority=priority)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(ticket_number__icontains=search) |
                Q(customer_name__icontains=search) |
                Q(mobile_number__icontains=search) |
                Q(email__icontains=search)
            )

        return qs

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response({
                    'success': True,
                    'data': serializer.data,
                })

            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
            })
        except DatabaseError as e:
            logger.error('[repairService] Database error listing tickets: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RepairTicketCreateAPIView(CreateAPIView):
    permission_classes = [AllowAny]
    queryset = RepairTicket.objects.all()
    serializer_class = RepairTicketCreateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            ticket = serializer.save(
                user=request.user if request.user.is_authenticated else None,
            )

            RepairTicketService.create_ticket_with_history(ticket, updated_by='Admin')

            send_ticket_created_notification(ticket)

            detail = RepairTicketDetailSerializer(ticket)
            return Response({
                'success': True,
                'message': 'Repair ticket created successfully',
                'data': detail.data,
            }, status=status.HTTP_201_CREATED)
        except DatabaseError as e:
            logger.error('[repairService] Database error creating ticket: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error('[repairService] Unexpected error creating ticket: %s', e)
            return Response({
                'success': False,
                'message': 'An error occurred while creating the repair ticket.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RepairTicketDetailAPIView(RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = RepairTicket.objects.select_related('service').prefetch_related('photos', 'notes', 'status_history').all()
    serializer_class = RepairTicketDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({
                'success': True,
                'data': serializer.data,
            })
        except RepairTicket.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Repair ticket not found.',
            }, status=status.HTTP_404_NOT_FOUND)
        except DatabaseError as e:
            logger.error('[repairService] Database error fetching ticket: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RepairTicketUpdateAPIView(UpdateAPIView):
    permission_classes = [AllowAny]
    queryset = RepairTicket.objects.prefetch_related('photos').all()
    serializer_class = RepairTicketUpdateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            ticket = RepairTicket.objects.prefetch_related('photos').get(pk=instance.pk)
        except DatabaseError as e:
            logger.error('[repairService] Database error updating ticket: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            detail = RepairTicketDetailSerializer(ticket)
            return Response({
                'success': True,
                'message': message,
                'data': detail.data,
            })
        except DatabaseError as e:
            logger.error('[repairService] Database error serializing ticket after approve: %s', e)
            return Response({
                'success': True,
                'message': message,
                'data': None,
            })
        except RepairTicket.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Repair ticket not found.',
            }, status=status.HTTP_404_NOT_FOUND)
        except DatabaseError as e:
            logger.error('[repairService] Database error updating ticket: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RepairTicketDeleteAPIView(DestroyAPIView):
    permission_classes = [AllowAny]
    queryset = RepairTicket.objects.all()

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            ticket_number = instance.ticket_number
            instance.delete()
            return Response({
                'success': True,
                'message': f'Repair ticket {ticket_number} deleted successfully',
            })
        except RepairTicket.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Repair ticket not found.',
            }, status=status.HTTP_404_NOT_FOUND)
        except DatabaseError as e:
            logger.error('[repairService] Database error deleting ticket: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RepairTicketStatusUpdateAPIView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = RepairStatusUpdateSerializer

    def put(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        try:
            ticket = RepairTicket.objects.get(pk=pk)
        except RepairTicket.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Repair ticket not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        if new_status == 'received':
            new_status = 'device_received'
        notes = serializer.validated_data.get('notes', '')
        updated_by = serializer.validated_data.get('updated_by', 'Admin')
        old_status = ticket.status

        extra_fields = {}
        repair_reason = serializer.validated_data.get('repair_reason', '')
        repair_charge = serializer.validated_data.get('repair_charge')
        if repair_reason:
            extra_fields['repair_reason'] = repair_reason
        if repair_charge is not None:
            extra_fields['repair_charge'] = repair_charge

        success, message = RepairTicketService.update_status(ticket, new_status, updated_by, notes, extra_fields=extra_fields if extra_fields else None)

        if not success:
            return Response({
                'success': False,
                'message': message,
            }, status=status.HTTP_400_BAD_REQUEST)

        send_status_update_notification(ticket, old_status, new_status)

        detail = RepairTicketDetailSerializer(ticket)
        return Response({
            'success': True,
            'message': message,
            'data': detail.data,
        })


class RepairTicketCustomerApproveAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RepairCustomerApproveSerializer

    def post(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        try:
            ticket = RepairTicket.objects.get(pk=pk, user=request.user)
        except RepairTicket.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Repair ticket not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        if ticket.status != 'awaiting_approval':
            return Response({
                'success': False,
                'message': 'Ticket is not awaiting approval.',
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']
        notes = serializer.validated_data.get('notes', '')

        success, message = RepairTicketService.customer_approve(ticket, action, notes)

        if not success:
            return Response({
                'success': False,
                'message': message,
            }, status=status.HTTP_400_BAD_REQUEST)

        detail = RepairTicketDetailSerializer(ticket)
        return Response({
            'success': True,
            'message': message,
            'data': detail.data,
        })


class RepairTicketAssignTechnicianAPIView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = RepairTicketTechnicianSerializer

    def put(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        try:
            ticket = RepairTicket.objects.get(pk=pk)
        except RepairTicket.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Repair ticket not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        technician = serializer.validated_data['assigned_technician']
        success, message = RepairTicketService.assign_technician(ticket, technician)

        send_ticket_assigned_notification(ticket, technician)

        detail = RepairTicketDetailSerializer(ticket)
        return Response({
            'success': True,
            'message': message,
            'data': detail.data,
        })


class RepairDashboardCountsAPIView(GenericAPIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        counts = RepairTicketService.get_dashboard_counts()
        return Response({
            'success': True,
            'data': counts,
        })


class RepairNoteListAPIView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = RepairNoteListSerializer

    def get_queryset(self):
        ticket_id = self.kwargs.get('pk')
        return RepairNote.objects.filter(repair_ticket_id=ticket_id)

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'data': serializer.data,
            })
        except DatabaseError as e:
            logger.error('[repairService] Database error listing notes: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RepairNoteCreateAPIView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RepairNoteCreateSerializer

    def create(self, request, *args, **kwargs):
        ticket_id = kwargs.get('pk')
        try:
            ticket = RepairTicket.objects.get(pk=ticket_id)
        except RepairTicket.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Repair ticket not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            serializer = self.get_serializer(
                data=request.data,
                context={'ticket_id': ticket_id},
            )
            serializer.is_valid(raise_exception=True)
            note = serializer.save()

            out = RepairNoteListSerializer(note)
            return Response({
                'success': True,
                'data': out.data,
            }, status=status.HTTP_201_CREATED)
        except DatabaseError as e:
            logger.error('[repairService] Database error creating note: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class NotificationListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            unread_count = queryset.filter(is_read=False).count()
            serializer = self.get_serializer(queryset, many=True)
            return Response({
                'success': True,
                'unread_count': unread_count,
                'data': serializer.data,
            })
        except DatabaseError as e:
            logger.error('[repairService] Database error listing notifications: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class NotificationMarkReadAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Notification not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        notification.is_read = True
        notification.save(update_fields=['is_read'])

        return Response({
            'success': True,
            'message': 'Notification marked as read.',
        })


class NotificationMarkAllReadAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        try:
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
            return Response({
                'success': True,
                'message': 'All notifications marked as read.',
            })
        except DatabaseError as e:
            logger.error('[repairService] Database error marking notifications: %s', e)
            return Response({
                'success': False,
                'message': 'Database error. Please try again.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
