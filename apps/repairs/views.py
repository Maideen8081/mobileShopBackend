from rest_framework import status
from rest_framework.generics import (
    CreateAPIView,
    DestroyAPIView,
    ListAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.repairs.models import RepairNote, RepairTicket
from apps.repairs.serializers import (
    RepairNoteCreateSerializer,
    RepairNoteListSerializer,
    RepairTicketCreateSerializer,
    RepairTicketDetailSerializer,
    RepairTicketListSerializer,
    RepairTicketStatusSerializer,
    RepairTicketTechnicianSerializer,
    RepairTicketUpdateSerializer,
)
from apps.repairs.services import RepairTicketService


class RepairTicketListAPIView(ListAPIView):
    queryset = RepairTicket.objects.select_related().prefetch_related('photos').all()
    serializer_class = RepairTicketListSerializer
    search_fields = [
        'customer_name',
        'mobile_number',
        'ticket_number',
        'device_model',
        'device_brand',
    ]
    ordering_fields = [
        'created_at',
        'estimated_cost',
        'priority',
    ]
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get('status')
        device_category = self.request.query_params.get('device_category')
        issue_category = self.request.query_params.get('issue_category')
        priority = self.request.query_params.get('priority')

        if status_param:
            qs = qs.filter(status=status_param)
        if device_category:
            qs = qs.filter(device_category=device_category)
        if issue_category:
            qs = qs.filter(issue_category=issue_category)
        if priority:
            qs = qs.filter(priority=priority)

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return Response({
                'success': True,
                'count': self.paginator.page.paginator.count if self.paginator else len(queryset),
                'next': self.paginator.get_next_link() if self.paginator else None,
                'previous': self.paginator.get_previous_link() if self.paginator else None,
                'data': serializer.data,
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class RepairTicketCreateAPIView(CreateAPIView):
    queryset = RepairTicket.objects.all()
    serializer_class = RepairTicketCreateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()

        detail = RepairTicketDetailSerializer(ticket)
        return Response({
            'success': True,
            'message': 'Repair ticket created successfully',
            'data': detail.data,
        }, status=status.HTTP_201_CREATED)


class RepairTicketDetailAPIView(RetrieveAPIView):
    queryset = RepairTicket.objects.prefetch_related('photos').all()
    serializer_class = RepairTicketDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class RepairTicketUpdateAPIView(UpdateAPIView):
    queryset = RepairTicket.objects.prefetch_related('photos').all()
    serializer_class = RepairTicketUpdateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        ticket = RepairTicket.objects.prefetch_related('photos').get(pk=instance.pk)
        detail = RepairTicketDetailSerializer(ticket)
        return Response({
            'success': True,
            'message': 'Repair ticket updated successfully',
            'data': detail.data,
        })


class RepairTicketPartialUpdateAPIView(UpdateAPIView):
    queryset = RepairTicket.objects.prefetch_related('photos').all()
    serializer_class = RepairTicketUpdateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        ticket = RepairTicket.objects.prefetch_related('photos').get(pk=instance.pk)
        detail = RepairTicketDetailSerializer(ticket)
        return Response({
            'success': True,
            'message': 'Repair ticket updated successfully',
            'data': detail.data,
        })


class RepairTicketDeleteAPIView(DestroyAPIView):
    queryset = RepairTicket.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        ticket_number = instance.ticket_number
        instance.delete()
        return Response({
            'success': True,
            'message': f'Repair ticket {ticket_number} deleted successfully',
        })


class RepairTicketDashboardCountsAPIView(ListAPIView):
    queryset = RepairTicket.objects.all()

    def list(self, request, *args, **kwargs):
        counts = RepairTicketService.get_dashboard_counts()
        return Response({
            'success': True,
            'data': counts,
        })


class RepairTicketStatusUpdateAPIView(UpdateAPIView):
    queryset = RepairTicket.objects.all()
    serializer_class = RepairTicketStatusSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        success, message = RepairTicketService.update_status(instance, new_status)

        if not success:
            return Response({
                'success': False,
                'message': message,
            }, status=status.HTTP_400_BAD_REQUEST)

        detail = RepairTicketDetailSerializer(instance)
        return Response({
            'success': True,
            'message': message,
            'data': detail.data,
        })


class RepairTicketAssignTechnicianAPIView(UpdateAPIView):
    queryset = RepairTicket.objects.all()
    serializer_class = RepairTicketTechnicianSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        technician = serializer.validated_data['assigned_technician']
        success, message = RepairTicketService.assign_technician(instance, technician)

        detail = RepairTicketDetailSerializer(instance)
        return Response({
            'success': True,
            'message': message,
            'data': detail.data,
        })


class RepairNoteListAPIView(ListAPIView):
    serializer_class = RepairNoteListSerializer

    def get_queryset(self):
        ticket_id = self.kwargs.get('pk')
        return RepairNote.objects.filter(repair_ticket_id=ticket_id)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class RepairNoteCreateAPIView(CreateAPIView):
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
