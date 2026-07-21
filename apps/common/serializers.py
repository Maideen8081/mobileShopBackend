from rest_framework import serializers


class AbsoluteImageField(serializers.ImageField):
    def to_representation(self, value):
        if not value:
            return None
        url = value.url
        if url.startswith(('http://', 'https://')):
            return url
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(url)
        return url


def get_absolute_image_url(image_field, request=None):
    if not image_field:
        return ''
    url = image_field.url
    if url.startswith(('http://', 'https://')):
        return url
    if request:
        return request.build_absolute_uri(url)
    return url
