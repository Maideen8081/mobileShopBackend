from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum, Min, Q, F, Value
from django.db.models.functions import Coalesce, NullIf
from drf_spectacular.utils import extend_schema
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, filters
from rest_framework.generics import ListAPIView, CreateAPIView, RetrieveAPIView, UpdateAPIView, DestroyAPIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.permissions import IsAdminUser, is_admin_account

from .models import Product, ProductVariant, VariantImage
from .serializers import (
    ProductWriteSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    VariantImageSerializer,
    published_filter,
)
from .validators import MAX_IMAGES_PER_VARIANT, validate_product_image
from rest_framework.pagination import PageNumberPagination

# What a customer actually pays for a variant: its discount price when set.
SELLING_PRICE = Coalesce(NullIf('variants__discount_price', Value(Decimal('0'))), 'variants__price')


class ProductPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def visible_products(request):
    """Admins see every product; shoppers only published ones in active categories."""
    qs = Product.objects.all()
    if not is_admin_account(request.user):
        qs = qs.filter(published_filter())
    return qs


class ProductListAPIView(ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]
    pagination_class = ProductPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['product_name', 'brand', 'model_number']
    ordering_fields = ['product_name', 'created_at', 'brand']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = visible_products(self.request).select_related('category', 'sub_category').annotate(
            variant_count=Count('variants', filter=Q(variants__is_active=True)),
            total_stock=Sum('variants__stock_quantity'),
            min_price=Min(SELLING_PRICE),
        )
        if self.include_variants():
            qs = qs.prefetch_related('variants__images')
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

    def include_variants(self):
        return self.request.query_params.get('include') == 'variants'

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'include_variants': self.include_variants()}

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
    serializer_class = ProductWriteSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAdminUser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            product = serializer.save()
        return Response({
            'success': True,
            'message': 'Product created successfully',
            'data': ProductDetailSerializer(product, context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)


class ProductDetailAPIView(RetrieveAPIView):
    serializer_class = ProductDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return visible_products(self.request).select_related('category', 'sub_category').prefetch_related(
            'features', 'care_instructions', 'variants__images'
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class ProductUpdateAPIView(UpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductWriteSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAdminUser]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            product = serializer.save()
        product = Product.objects.prefetch_related('features', 'care_instructions', 'variants__images').get(pk=product.pk)
        return Response({
            'success': True,
            'message': 'Product updated successfully',
            'data': ProductDetailSerializer(product, context={'request': request}).data,
        })


class ProductDeleteAPIView(DestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    permission_classes = [IsAdminUser]

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
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        total = Product.objects.count()
        active = Product.objects.filter(is_published=True).count()
        inactive = Product.objects.filter(is_published=False).count()
        trending = Product.objects.filter(is_trending=True).count()
        new_arrival = Product.objects.filter(is_new_arrival=True).count()
        best_selling = Product.objects.filter(is_best_selling=True).count()
        featured = Product.objects.filter(is_featured=True).count()
        total_variants = ProductVariant.objects.count()
        low_stock_qs = ProductVariant.objects.filter(
            stock_quantity__gt=0, stock_quantity__lte=F('low_stock_alert'), is_active=True
        )
        low_stock = low_stock_qs.count()
        low_stock_products = low_stock_qs.values('product_id').distinct().count()

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
            'low_stock_products': low_stock_products,
        })


class ProductSearchAPIView(ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        query = self.request.query_params.get('query', '')
        if not query:
            return Product.objects.none()
        return visible_products(self.request).select_related('category', 'sub_category').filter(
            Q(product_name__icontains=query) |
            Q(brand__icontains=query) |
            Q(model_number__icontains=query) |
            Q(description__icontains=query)
        ).annotate(
            variant_count=Count('variants', filter=Q(variants__is_active=True)),
            total_stock=Sum('variants__stock_quantity'),
            min_price=Min(SELLING_PRICE),
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
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        low_stock_variant_ids = ProductVariant.objects.filter(
            stock_quantity__gt=0, stock_quantity__lte=F('low_stock_alert'), is_active=True,
        ).values_list('product_id', flat=True).distinct()

        return Product.objects.filter(id__in=low_stock_variant_ids).select_related(
            'category', 'sub_category'
        ).annotate(
            variant_count=Count('variants', filter=Q(variants__is_active=True)),
            total_stock=Sum('variants__stock_quantity'),
            min_price=Min(SELLING_PRICE),
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
    permission_classes = [IsAdminUser]

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

        if variant.images.count() + len(images) > MAX_IMAGES_PER_VARIANT:
            return Response({
                'success': False,
                'message': f'Maximum {MAX_IMAGES_PER_VARIANT} images allowed per variant.',
            }, status=status.HTTP_400_BAD_REQUEST)
        for image in images:
            try:
                validate_product_image(image)
            except DjangoValidationError as exc:
                return Response({
                    'success': False,
                    'message': f'{image.name}: {"; ".join(exc.messages)}',
                }, status=status.HTTP_400_BAD_REQUEST)

        created = []
        with transaction.atomic():
            for image in images:
                img = VariantImage.objects.create(
                    variant=variant,
                    image=image,
                    is_main=not variant.images.exists(),
                )
                created.append(VariantImageSerializer(img, context={'request': request}).data)

        return Response({
            'success': True,
            'message': f'{len(created)} image(s) uploaded successfully',
            'data': created,
        }, status=status.HTTP_201_CREATED)


class VariantImageDeleteAPIView(DestroyAPIView):
    queryset = VariantImage.objects.all()
    serializer_class = VariantImageSerializer
    permission_classes = [IsAdminUser]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        variant = instance.variant
        if variant.images.count() <= 1:
            return Response({
                'success': False,
                'message': 'A variant must keep at least one image. Upload another image first.',
            }, status=status.HTTP_400_BAD_REQUEST)
        was_main = instance.is_main
        # The file stays in storage: past order items link to it by URL.
        instance.delete()
        if was_main:
            first = variant.images.order_by('id').first()
            first.is_main = True
            first.save(update_fields=['is_main'])
        return Response({
            'success': True,
            'message': 'Image deleted successfully',
        }, status=status.HTTP_200_OK)
