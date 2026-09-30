from django.conf import settings
from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("about", views.page, {"slug": "about"}, name="about"),
    path("privacy", views.page, {"slug": "privacy"}, name="privacy"),
    path("faq", views.page, {"slug": "faq"}, name="faq"),
    path("how-it-works", views.page, {"slug": "how-it-works"}, name="how_it_works"),
    path("contact", views.contact, name="contact"),
    path("contact", views.contact, name="contact_submit"),
    path("services", views.services, name="services"),
    path("services/<slug:slug>", views.service_detail, name="service_detail"),
    path("journal", views.journal, name="journal"),
    path("journal/<slug:slug>", views.post_detail, name="post_detail"),
    path(settings.ADMIN_BASE_PATH + "/inquiry-photo/<int:photo_id>", views.inquiry_photo, name="inquiry_photo"),
    path("robots.txt", views.robots), path("health", views.health),
    path("favicon.ico", views.legacy_favicon),
    path("favicon/<str:filename>", views.legacy_favicon),
]
