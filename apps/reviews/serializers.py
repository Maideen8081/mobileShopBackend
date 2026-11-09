from rest_framework import serializers

from .models import Review, ReviewImage
from apps.common.serializers import AbsoluteImageField


class ReviewImageSerializer(serializers.ModelSerializer):
    image = AbsoluteImageField()

    class Meta:
        model = ReviewImage
        fields = ['id', 'image', 'uploaded_at']


class ReviewSerializer(serializers.ModelSerializer):
    images = ReviewImageSerializer(many=True, read_only=True)
    user_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.product_name', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'user', 'user_name', 'product', 'product_name',
            'star', 'rating', 'content', 'is_published',
            'images', 'created_at', 'updated_at',
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['product', 'star', 'rating', 'content']

    def validate_star(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Star must be between 1 and 5.')
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        if Review.objects.filter(user=user, product=attrs['product']).exists():
            raise serializers.ValidationError('You have already reviewed this product.')
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        return Review.objects.create(user=user, **validated_data)


class ReviewUpdateSerializer(serializers.ModelSerializer):
    images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        write_only=True,
    )
    remove_image_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Review
        fields = ['star', 'rating', 'content', 'images', 'remove_image_ids']
        extra_kwargs = {
            'star': {'required': False},
            'rating': {'required': False},
            'content': {'required': False},
        }

    def validate_star(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Star must be between 1 and 5.')
        return value

    def update(self, instance, validated_data):
        images_data = validated_data.pop('images', None)
        remove_image_ids = validated_data.pop('remove_image_ids', None)

        # Check the image limit before changing anything, so a rejected update saves nothing.
        if images_data:
            removing = instance.images.filter(id__in=remove_image_ids or []).count()
            if instance.images.count() - removing + len(images_data) > 10:
                raise serializers.ValidationError({'images': 'Maximum 10 images allowed per review.'})

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if remove_image_ids:
            for img in instance.images.filter(id__in=remove_image_ids):
                img.image.delete(save=False)
                img.delete()

        if images_data:
            for image in images_data:
                ReviewImage.objects.create(review=instance, image=image)

        return instance
