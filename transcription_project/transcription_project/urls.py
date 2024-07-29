from django.contrib import admin
from django.urls import path, include
from rest_framework.documentation import include_docs_urls
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from transcription_app.views import (
    AudioFileViewSet,
    RegisterView,
    CustomTokenObtainPairView,
    VerifyTokenView,
)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r"audio-files", AudioFileViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "",
        include_docs_urls(title="Transcription API", description="API documentation"),
    ),
    path("", include(router.urls)),
    path("api/", include(router.urls)),
    path("api/token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/register/", RegisterView.as_view(), name="register"),
    path("api/verify-token/", VerifyTokenView.as_view(), name="verify_token"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
