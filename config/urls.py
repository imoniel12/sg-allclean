from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [path("", include("website.urls")), path(settings.ADMIN_BASE_PATH + "/", admin.site.urls)]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
handler404 = "website.views.not_found"
handler400 = "website.views.bad_request"
handler403 = "website.views.permission_denied"
handler500 = "website.views.server_error"
