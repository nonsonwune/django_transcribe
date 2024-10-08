from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken
from .models import AudioFile
from .serializers import AudioFileSerializer, UserSerializer
from .tasks import process_audio_file
from rest_framework.decorators import action
import json
import os
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
import logging
from django.http import FileResponse
from django.conf import settings


logger = logging.getLogger(__name__)


class AudioFileViewSet(viewsets.ModelViewSet):
    queryset = AudioFile.objects.all()
    serializer_class = AudioFileSerializer

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
            audio_file_id = serializer.instance.id
            process_audio_file.delay(audio_file_id)
            logger.info(
                f"AudioFile created successfully for user {self.request.user.username}"
            )
        except Exception as e:
            logger.error(f"Error creating AudioFile: {str(e)}")
            raise

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def transcription(self, request, pk=None):
        try:
            audio_file = self.get_object()
            if not audio_file.processed:
                return Response(
                    {"error": "Transcription not ready"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    "text": audio_file.transcription_text,
                    "json": audio_file.transcription_json,
                }
            )
        except AudioFile.DoesNotExist:
            logger.error(f"Transcription not found for file ID: {pk}")
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        audio_file = self.get_object()
        format = request.query_params.get("format", "txt")

        if format not in ["json", "txt", "srt", "vtt"]:
            return Response(
                {"error": "Invalid format"}, status=status.HTTP_400_BAD_REQUEST
            )

        file_path = audio_file.get_file_path(format)

        if not os.path.exists(file_path):
            return Response(
                {"error": "File not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            with open(file_path, "rb") as file:
                response = HttpResponse(
                    file.read(), content_type="application/octet-stream"
                )
                response["Content-Disposition"] = (
                    f'attachment; filename="{os.path.basename(file_path)}"'
                )
                return response
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            logger.error(f"Token generation failed: {str(e)}")
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST
            )

        user = serializer.user
        token = serializer.validated_data

        response_data = {
            "access": token["access"],
            "refresh": token["refresh"],
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
        }

        logger.info(f"Token generated for user: {user.username}")
        return Response(response_data)


class VerifyTokenView(APIView):
    def post(self, request):
        token = request.data.get("token")
        if not token:
            return Response(
                {"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = AccessToken(token)
            user = token.payload.get("user_id")
            if user:
                logger.info(f"Token verified for user ID: {user}")
                return Response({"valid": True, "user_id": user})
            else:
                logger.warning("Token payload does not contain user_id")
                return Response({"valid": False}, status=status.HTTP_400_BAD_REQUEST)
        except TokenError as e:
            logger.error(f"Token verification failed: {str(e)}")
            return Response({"valid": False}, status=status.HTTP_400_BAD_REQUEST)
