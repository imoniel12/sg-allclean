from django import forms

from .image_security import sanitize_public_image
from .models import Post, SiteSettings


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = "__all__"

    def clean_logo(self):
        upload = self.cleaned_data.get("logo")
        if upload and upload != getattr(self.instance, "logo", None):
            return sanitize_public_image(upload, "logo")
        return upload


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = "__all__"

    def clean_image(self):
        upload = self.cleaned_data.get("image")
        if upload and upload != getattr(self.instance, "image", None):
            return sanitize_public_image(upload, "post")
        return upload
