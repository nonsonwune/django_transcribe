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

logger = logging.getLogger(__name__)


class AudioFileViewSet(viewsets.ModelViewSet):
    queryset = AudioFile.objects.all()
    serializer_class = AudioFileSerializer

    def perform_create(self, serializer):
        audio_file = serializer.save(user=self.request.user)
        process_audio_file.delay(audio_file.id)

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        audio_file = self.get_object()
        return Response(
            {
                "status": audio_file.status,
                "progress": getattr(audio_file, "progress", 0),
                "error_message": getattr(audio_file, "error_message", ""),
            }
        )

    @action(detail=True, methods=["get"])
    def transcription(self, request, pk=None):
        audio_file = self.get_object()
        if audio_file.processed:
            return Response(
                {
                    "text": audio_file.transcription_text,
                    "json": audio_file.transcription_json,
                    "srt_url": audio_file.get_srt_url(),
                    "vtt_url": audio_file.get_vtt_url(),
                    "txt_url": audio_file.get_txt_url(),
                    "json_url": audio_file.get_json_url(),
                }
            )
        else:
            return Response(
                {"error": "Transcription not yet processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        audio_file = self.get_object()
        file_format = request.query_params.get("format", "json")

        if not audio_file.processed:
            return Response(
                {"error": "File not yet processed"}, status=status.HTTP_400_BAD_REQUEST
            )

        if file_format == "json":
            return Response(audio_file.transcription_json)
        elif file_format == "txt":
            return Response(audio_file.transcription_text)
        elif file_format == "srt":
            return Response(audio_file.get_srt_url())
        elif file_format == "vtt":
            return Response(audio_file.get_vtt_url())
        else:
            return Response(
                {"error": "Invalid format"}, status=status.HTTP_400_BAD_REQUEST
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
