from django.db.models import Avg, Count
from rest_framework import status
from rest_framework.generics import (
    ListAPIView,
    CreateAPIView,
    RetrieveAPIView,
    UpdateAPIView,
    DestroyAPIView,
)
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Review, ReviewImage
from .serializers import (
    ReviewSerializer,
    ReviewCreateSerializer,
    ReviewUpdateSerializer,
    ReviewImageSerializer,
)


class ReviewListAPIView(ListAPIView):
    serializer_class = ReviewSerializer

    def get_queryset(self):
        qs = Review.objects.select_related('user', 'product').prefetch_related('images')
        product = self.request.query_params.get('product')
        star = self.request.query_params.get('star')
        is_published = self.request.query_params.get('is_published')

        if product:
            qs = qs.filter(product_id=product)
        if star:
            qs = qs.filter(star=star)
        if is_published is not None:
            qs = qs.filter(is_published=is_published.lower() == 'true')
        else:
            qs = qs.filter(is_published=True)

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        summary = queryset.aggregate(average_star=Avg('star'), total=Count('id'))
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'average_star': round(summary['average_star'], 2) if summary['average_star'] else 0,
            'total_reviews': summary['total'],
            'data': serializer.data,
        })


class ReviewCreateAPIView(CreateAPIView):
    queryset = Review.objects.all()
    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = serializer.save()

        detail = ReviewSerializer(review, context={'request': request})
        return Response({
            'success': True,
            'message': 'Review submitted successfully',
            'data': detail.data,
        }, status=status.HTTP_201_CREATED)


class ReviewDetailAPIView(RetrieveAPIView):
    queryset = Review.objects.select_related('user', 'product').prefetch_related('images')
    serializer_class = ReviewSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class ReviewUpdateAPIView(UpdateAPIView):
    serializer_class = ReviewUpdateSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        review = serializer.save()

        detail = ReviewSerializer(review, context={'request': request})
        return Response({
            'success': True,
            'message': 'Review updated successfully',
            'data': detail.data,
        })


class ReviewDeleteAPIView(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        for img in instance.images.all():
            img.image.delete(save=False)
        instance.delete()
        return Response({
            'success': True,
            'message': 'Review deleted successfully',
        }, status=status.HTTP_200_OK)


class ReviewImageUploadAPIView(CreateAPIView):
    serializer_class = ReviewImageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        review_id = kwargs.get('review_pk')
        try:
            review = Review.objects.get(id=review_id, user=request.user)
        except Review.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Review not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        images = request.FILES.getlist('images')
        if len(images) < 1:
            return Response({
                'success': False,
                'message': 'At least one image is required.',
            }, status=status.HTTP_400_BAD_REQUEST)

        if review.images.count() + len(images) > 10:
            return Response({
                'success': False,
                'message': 'Maximum 10 images allowed per review.',
            }, status=status.HTTP_400_BAD_REQUEST)

        created = []
        for image in images:
            img = ReviewImage.objects.create(review=review, image=image)
            created.append(ReviewImageSerializer(img, context={'request': request}).data)

        return Response({
            'success': True,
            'message': f'{len(created)} image(s) uploaded successfully',
            'data': created,
        }, status=status.HTTP_201_CREATED)


class ReviewImageDeleteAPIView(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ReviewImage.objects.filter(review__user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.image.delete(save=False)
        instance.delete()
        return Response({
            'success': True,
            'message': 'Image deleted successfully',
        }, status=status.HTTP_200_OK)
