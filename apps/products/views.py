from django.db.models import Count, Sum, Min, Q, F
from drf_spectacular.utils import extend_schema
from rest_framework import status, filters
from rest_framework.generics import ListAPIView, CreateAPIView, RetrieveAPIView, UpdateAPIView, DestroyAPIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import Product, ProductVariant, VariantImage
from .serializers import (
    ProductCreateSerializer,
    ProductUpdateSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductVariantSerializer,
    VariantImageSerializer,
)
from rest_framework.pagination import PageNumberPagination


class ProductListAPIView(ListAPIView):
    serializer_class = ProductListSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product_name', 'brand', 'model_number']
    ordering_fields = ['product_name', 'created_at', 'brand']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = Product.objects.select_related('category', 'sub_category').annotate(
            variant_count=Count('variants', filter=Q(variants__is_active=True)),
            total_stock=Sum('variants__stock_quantity'),
            min_price=Min('variants__price'),
        )
        category = self.request.query_params.get('category')
        category_name = self.request.query_params.get('category_name')
        sub_category = self.request.query_params.get('sub_category')
        sub_category_name = self.request.query_params.get('sub_category_name')
        is_trending = self.request.query_params.get('is_trending')
        is_new_arrival = self.request.query_params.get('is_new_arrival')
        is_best_selling = self.request.query_params.get('is_best_selling')
        is_featured = self.request.query_params.get('is_featured')
        is_refurbished = self.request.query_params.get('is_refurbished')
        is_published = self.request.query_params.get('is_published')
        status_param = self.request.query_params.get('status')

        if category:
            if category.isdigit():
                qs = qs.filter(category_id=category)
            else:
                qs = qs.filter(category__category_name__iexact=category)
        if category_name:
            qs = qs.filter(category__category_name__iexact=category_name)
        if sub_category:
            if sub_category.isdigit():
                qs = qs.filter(sub_category_id=sub_category)
            else:
                qs = qs.filter(sub_category__sub_category_name__iexact=sub_category)
        if sub_category_name:
            qs = qs.filter(sub_category__sub_category_name__iexact=sub_category_name)
        if is_trending:
            qs = qs.filter(is_trending=True)
        if is_new_arrival:
            qs = qs.filter(is_new_arrival=True)
        if is_best_selling:
            qs = qs.filter(is_best_selling=True)
        if is_refurbished:
            qs = qs.filter(is_refurbished=True)
        if is_featured:
            qs = qs.filter(is_featured=True)
        if is_published is not None:
            qs = qs.filter(is_published=is_published.lower() == 'true')
        if status_param == 'active':
            qs = qs.filter(is_published=True)
        elif status_param == 'inactive':
            qs = qs.filter(is_published=False)

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


class ProductCreateAPIView(CreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductCreateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        self._handle_variant_images(request, product)

        detail = ProductDetailSerializer(product)
        return Response({
            'success': True,
            'message': 'Product created successfully',
            'data': detail.data,
        }, status=status.HTTP_201_CREATED)

    def _handle_variant_images(self, request, product):
        variant_images = request.FILES.getlist('variant_images')
        variant_image_map = request.data.get('variant_image_map')

        if not variant_images:
            return

        variants = list(product.variants.all())
        if not variants:
            return

        if isinstance(variant_image_map, str):
            import json
            try:
                variant_image_map = json.loads(variant_image_map)
            except json.JSONDecodeError:
                variant_image_map = {}

        if isinstance(variant_image_map, dict):
            mappings = []
            for i in range(len(variant_images)):
                m = variant_image_map.get(str(i)) or variant_image_map.get(i)
                mappings.append(m if m else {})
        elif isinstance(variant_image_map, list):
            mappings = variant_image_map
        else:
            mappings = [{}] * len(variant_images)

        for idx, img_file in enumerate(variant_images):
            mapping = mappings[idx] if idx < len(mappings) else {}
            variant_index = mapping.get('variant_index', 0) if isinstance(mapping, dict) else 0
            is_main = mapping.get('is_main', False) if isinstance(mapping, dict) else False
            if variant_index < len(variants):
                VariantImage.objects.create(
                    variant=variants[variant_index],
                    image=img_file,
                    is_main=is_main,
                )


class ProductDetailAPIView(RetrieveAPIView):
    queryset = Product.objects.select_related('category', 'sub_category').prefetch_related(
        'features', 'care_instructions', 'variants__images'
    )
    serializer_class = ProductDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class ProductUpdateAPIView(UpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductUpdateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        self._handle_variant_images(request, product)

        detail = ProductDetailSerializer(product)
        return Response({
            'success': True,
            'message': 'Product updated successfully',
            'data': detail.data,
        })

    def _handle_variant_images(self, request, product):
        variant_images = request.FILES.getlist('variant_images')
        variant_image_map = request.data.get('variant_image_map')

        if not variant_images:
            return

        variants = list(product.variants.all())
        if not variants:
            return

        if isinstance(variant_image_map, str):
            import json
            try:
                variant_image_map = json.loads(variant_image_map)
            except json.JSONDecodeError:
                variant_image_map = {}

        if isinstance(variant_image_map, dict):
            mappings = []
            for i in range(len(variant_images)):
                m = variant_image_map.get(str(i)) or variant_image_map.get(i)
                mappings.append(m if m else {})
        elif isinstance(variant_image_map, list):
            mappings = variant_image_map
        else:
            mappings = [{}] * len(variant_images)

        for idx, img_file in enumerate(variant_images):
            mapping = mappings[idx] if idx < len(mappings) else {}
            variant_index = mapping.get('variant_index', 0) if isinstance(mapping, dict) else 0
            is_main = mapping.get('is_main', False) if isinstance(mapping, dict) else False
            if variant_index < len(variants):
                VariantImage.objects.create(
                    variant=variants[variant_index],
                    image=img_file,
                    is_main=is_main,
                )


class ProductDeleteAPIView(DestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({
            'success': True,
            'message': 'Product deleted successfully',
        }, status=status.HTTP_200_OK)


class ProductDashboardCountsAPIView(ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductListSerializer

    def list(self, request, *args, **kwargs):
        total = Product.objects.count()
        active = Product.objects.filter(is_published=True).count()
        inactive = Product.objects.filter(is_published=False).count()
        trending = Product.objects.filter(is_trending=True).count()
        new_arrival = Product.objects.filter(is_new_arrival=True).count()
        best_selling = Product.objects.filter(is_best_selling=True).count()
        featured = Product.objects.filter(is_featured=True).count()
        total_variants = ProductVariant.objects.count()
        low_stock = ProductVariant.objects.filter(
            stock_quantity__gt=0, stock_quantity__lte=F('low_stock_alert'), is_active=True
        ).count()

        return Response({
            'total_products': total,
            'active_products': active,
            'inactive_products': inactive,
            'trending_products': trending,
            'new_arrival_products': new_arrival,
            'best_selling_products': best_selling,
            'featured_products': featured,
            'total_variants': total_variants,
            'low_stock_variants': low_stock,
        })


class ProductSearchAPIView(ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        query = self.request.query_params.get('query', '')
        if not query:
            return Product.objects.none()
        return Product.objects.select_related('category', 'sub_category').filter(
            Q(product_name__icontains=query) |
            Q(brand__icontains=query) |
            Q(model_number__icontains=query) |
            Q(description__icontains=query)
        ).annotate(
            variant_count=Count('variants', filter=Q(variants__is_active=True)),
            total_stock=Sum('variants__stock_quantity'),
            min_price=Min('variants__price'),
        )[:20]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class LowStockProductsAPIView(ListAPIView):
    serializer_class = ProductListSerializer

    def get_queryset(self):
        low_stock_variant_ids = ProductVariant.objects.filter(
            stock_quantity__gt=0,
                    stock_quantity__lte=F('low_stock_alert')
                ).values_list('product_id', flat=True).distinct()

        return Product.objects.filter(id__in=low_stock_variant_ids).select_related(
            'category', 'sub_category'
        ).annotate(
            variant_count=Count('variants', filter=Q(variants__is_active=True)),
            total_stock=Sum('variants__stock_quantity'),
            min_price=Min('variants__price'),
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class VariantImageUploadAPIView(CreateAPIView):
    queryset = VariantImage.objects.all()
    serializer_class = VariantImageSerializer
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        variant_id = kwargs.get('variant_pk')
        try:
            variant = ProductVariant.objects.get(id=variant_id)
        except ProductVariant.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Variant not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        images = request.FILES.getlist('images')
        if len(images) < 1:
            return Response({
                'success': False,
                'message': 'At least one image is required.',
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(images) > 10:
            return Response({
                'success': False,
                'message': 'Maximum 10 images allowed per variant.',
            }, status=status.HTTP_400_BAD_REQUEST)

        created = []
        for image in images:
            img = VariantImage.objects.create(
                variant=variant,
                image=image,
                is_main=not variant.images.exists(),
            )
            created.append(VariantImageSerializer(img).data)

        return Response({
            'success': True,
            'message': f'{len(created)} image(s) uploaded successfully',
            'data': created,
        }, status=status.HTTP_201_CREATED)


class VariantImageDeleteAPIView(DestroyAPIView):
    queryset = VariantImage.objects.all()
    serializer_class = VariantImageSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.image.delete()
        instance.delete()
        return Response({
            'success': True,
            'message': 'Image deleted successfully',
        }, status=status.HTTP_200_OK)
