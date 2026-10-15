from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework import status, filters
from rest_framework.generics import ListAPIView, CreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsAdminUser, IsAdminOrReadOnly, is_admin_account
from .models import Category, SubCategory
from .serializers import (
    CategoryWriteSerializer,
    CategoryListSerializer,
    CategoryDetailSerializer,
    CategoryDropdownSerializer,
    SubCategorySerializer,
)
from .services import CatalogInUseError, CategoryService
from apps.common.serializers import get_absolute_image_url


def _category_payload(category, request):
    return {
        'id': category.id,
        'category_name': category.category_name,
        'category_image': get_absolute_image_url(category.category_image, request),
        'status': category.status,
        'created_at': category.created_at,
    }


@extend_schema(tags=['Categories'])
class CategoryListAPIView(ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategoryListSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['category_name']
    ordering_fields = ['category_name', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = CategoryService.get_category_list()
        if not is_admin_account(self.request.user):
            qs = qs.filter(status='active')  # inactive categories are hidden from shoppers
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        counts = CategoryService.get_dashboard_counts()
        return Response({
            'success': True,
            'counts': counts,
            'data': serializer.data,
        })


@extend_schema(tags=['Categories'])
class CategoryCreateAPIView(CreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategoryWriteSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAdminUser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response({
            'success': True,
            'message': 'Category created successfully',
            'data': _category_payload(category, request),
        }, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Categories'])
class CategoryRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        return CategoryService.annotated_categories()

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CategoryDetailSerializer
        return CategoryWriteSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data,
        })

    def update(self, request, *args, **kwargs):
        kwargs.pop('partial', None)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response({
            'success': True,
            'message': 'Category updated successfully',
            'data': _category_payload(category, request),
        })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            sub_count = CategoryService.delete_category(instance)
        except CatalogInUseError as exc:
            return Response({'success': False, 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        msg = 'Category deleted successfully'
        if sub_count > 0:
            msg += f' along with {sub_count} sub categor{"y" if sub_count == 1 else "ies"}'
        return Response({
            'success': True,
            'message': msg,
        }, status=status.HTTP_200_OK)


@extend_schema(tags=['Categories'])
class CategoryDashboardCountsAPIView(ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategoryListSerializer
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        counts = CategoryService.get_dashboard_counts()
        return Response(counts)


@extend_schema(tags=['Categories'])
class CategoryDropdownAPIView(ListAPIView):
    queryset = Category.objects.filter(status='active')
    serializer_class = CategoryDropdownSerializer
    pagination_class = None
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        queryset = CategoryService.get_dropdown_categories()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


def _annotated_sub_categories():
    return SubCategory.objects.select_related('parent_category').annotate(product_count=Count('products'))


@extend_schema(tags=['Sub Categories'])
class SubCategoryListAPIView(ListAPIView):
    queryset = SubCategory.objects.none()
    serializer_class = SubCategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['sub_category_name']
    ordering_fields = ['sub_category_name', 'created_at']
    ordering = ['created_at']

    def get_queryset(self):
        qs = _annotated_sub_categories()
        parent = self.request.query_params.get('parent_category')
        if parent and parent.isdigit():
            qs = qs.filter(parent_category_id=parent)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
        })


@extend_schema(tags=['Sub Categories'])
class SubCategoryCreateAPIView(CreateAPIView):
    queryset = SubCategory.objects.all()
    serializer_class = SubCategorySerializer
    permission_classes = [IsAdminUser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sub_category = serializer.save()
        return Response({
            'success': True,
            'message': 'Sub category created successfully',
            'data': SubCategorySerializer(sub_category).data,
        }, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Sub Categories'])
class SubCategoryDetailAPIView(RetrieveUpdateDestroyAPIView):
    serializer_class = SubCategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        return _annotated_sub_categories()

    def retrieve(self, request, *args, **kwargs):
        return Response({'success': True, 'data': self.get_serializer(self.get_object()).data})

    def update(self, request, *args, **kwargs):
        kwargs.pop('partial', None)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        sub_category = serializer.save()
        return Response({
            'success': True,
            'message': 'Sub category updated successfully',
            'data': self.get_serializer(self.get_queryset().get(pk=sub_category.pk)).data,
        })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            CategoryService.delete_sub_category(instance)
        except CatalogInUseError as exc:
            return Response({'success': False, 'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'success': True, 'message': 'Sub category deleted successfully'})
