from drf_spectacular.utils import extend_schema
from rest_framework import status, filters
from rest_framework.generics import ListAPIView, CreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import Category, SubCategory
from .serializers import (
    CategoryCreateSerializer,
    CategoryUpdateSerializer,
    CategoryListSerializer,
    CategoryDetailSerializer,
    CategoryDropdownSerializer,
    SubCategorySerializer,
)
from .services import CategoryService


@extend_schema(tags=['Categories'])
class CategoryListAPIView(ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategoryListSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['category_name']
    ordering_fields = ['category_name', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return CategoryService.get_category_list()

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
    serializer_class = CategoryCreateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response({
            'success': True,
            'message': 'Category created successfully',
            'data': {
                'id': category.id,
                'category_name': category.category_name,
                'category_image': request.build_absolute_uri(category.category_image.url) if category.category_image else None,
                'status': category.status,
                'created_at': category.created_at,
            },
        }, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Categories'])
class CategoryRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        from django.db.models import Count
        return Category.objects.annotate(sub_category_count=Count('sub_categories'))

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CategoryDetailSerializer
        return CategoryUpdateSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data,
        })

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response({
            'success': True,
            'message': 'Category updated successfully',
            'data': {
                'id': category.id,
                'category_name': category.category_name,
                'category_image': request.build_absolute_uri(category.category_image.url) if category.category_image else None,
                'status': category.status,
                'created_at': category.created_at,
            },
        })

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        sub_count = instance.sub_categories.count()
        CategoryService.delete_category(instance)
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

    def list(self, request, *args, **kwargs):
        counts = CategoryService.get_dashboard_counts()
        return Response(counts)


@extend_schema(tags=['Categories'])
class CategoryDropdownAPIView(ListAPIView):
    queryset = Category.objects.filter(status='active')
    serializer_class = CategoryDropdownSerializer
    pagination_class = None

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema(tags=['Sub Categories'])
class SubCategoryListAPIView(ListAPIView):
    queryset = SubCategory.objects.select_related('parent_category').all()
    serializer_class = SubCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['sub_category_name']
    ordering_fields = ['sub_category_name', 'created_at']
    ordering = ['-created_at']

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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sub_category = serializer.save()
        return Response({
            'success': True,
            'message': 'Sub category created successfully',
            'data': SubCategorySerializer(sub_category).data,
        }, status=status.HTTP_201_CREATED)
