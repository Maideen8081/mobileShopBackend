from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponseRedirect
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
import traceback
import logging

logger = logging.getLogger(__name__)

def api_root(request):
    return HttpResponseRedirect('/api/v1/')

def custom_500(request, exception=None):
    logger.error('500 Error: %s', traceback.format_exc())
    from django.http import HttpResponseServerError
    return HttpResponseServerError('Internal Server Error')

api_urlpatterns = [
    path('products/', include('apps.products.urls')),
    path('categories/', include('apps.categories.urls')),
    path('sub-categories/', include('apps.categories.sub_urls')),
    path('repairs/', include('apps.repairs.urls')),
    path('cart/', include('apps.cart.urls')),
    path('reviews/', include('apps.reviews.urls')),
    path('chat/', include('apps.chat.urls')),
    path('', include('apps.customers.urls')),
    path('', include('apps.orders.urls')),
    path('admin/auth/', include('apps.customers.admin_urls')),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api_root, name='api-root'),
    path('api/v1/', include(api_urlpatterns)),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

handler500 = 'config.urls.custom_500'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
