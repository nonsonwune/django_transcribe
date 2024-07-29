from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
import os


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    # Add any other fields you might need


class AudioFile(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    file = models.FileField(upload_to="uploads/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="pending")
    transcription_text = models.TextField(blank=True, null=True)
    transcription_json = models.JSONField(blank=True, null=True)

    def get_file_path(self, extension):
        base_name = os.path.splitext(os.path.basename(self.file.name))[0]
        return os.path.join(
            settings.MEDIA_ROOT,
            "transcriptions",
            f"{self.id}",
            f"{base_name}.{extension}",
        )

    def get_file_url(self, extension):
        base_name = os.path.splitext(self.file.name)[0]
        return os.path.join(settings.MEDIA_URL, f"{base_name}.{extension}")

    def get_srt_url(self):
        return self.get_file_url("srt")

    def get_vtt_url(self):
        return self.get_file_url("vtt")

    def get_txt_url(self):
        return self.get_file_url("txt")

    def get_json_url(self):
        return self.get_file_url("json")
