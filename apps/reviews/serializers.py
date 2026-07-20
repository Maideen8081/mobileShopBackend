from rest_framework import serializers

from .models import Review, ReviewImage


class AbsoluteImageField(serializers.ImageField):
    def to_representation(self, value):
        if not value:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(value.url)
        return value.url


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
    images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Review
        fields = ['product', 'star', 'rating', 'content', 'images']

    def validate_star(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Star must be between 1 and 5.')
        return value

    def validate_images(self, value):
        if len(value) > 10:
            raise serializers.ValidationError('Maximum 10 images allowed per review.')
        return value

    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        user = self.context['request'].user
        review = Review.objects.create(user=user, **validated_data)
        for image in images_data:
            ReviewImage.objects.create(review=review, image=image)
        return review


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
        fields = ['star', 'rating', 'content', 'is_published', 'images', 'remove_image_ids']
        extra_kwargs = {
            'star': {'required': False},
            'rating': {'required': False},
            'content': {'required': False},
            'is_published': {'required': False},
        }

    def validate_star(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Star must be between 1 and 5.')
        return value

    def update(self, instance, validated_data):
        images_data = validated_data.pop('images', None)
        remove_image_ids = validated_data.pop('remove_image_ids', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if remove_image_ids:
            for img in instance.images.filter(id__in=remove_image_ids):
                img.image.delete(save=False)
                img.delete()

        if images_data:
            existing = instance.images.count()
            if existing + len(images_data) > 10:
                raise serializers.ValidationError({'images': 'Maximum 10 images allowed per review.'})
            for image in images_data:
                ReviewImage.objects.create(review=instance, image=image)

        return instance
