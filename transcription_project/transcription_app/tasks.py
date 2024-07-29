from celery import shared_task
from .models import AudioFile
from .transcription_service import TranscriptionService
import os
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_audio_file(self, audio_file_id):
    try:
        audio_file = AudioFile.objects.get(id=audio_file_id)
        audio_file.status = "processing"
        audio_file.save()

        service = TranscriptionService(str(audio_file.id))
        result = service.process_audio_file(audio_file.file.path)

        if result:
            audio_file.status = "completed"
            audio_file.processed = True
        else:
            audio_file.status = "failed"
        audio_file.save()

    except Exception as e:
        logger.error(
            f"Error processing audio file {audio_file_id}: {str(e)}", exc_info=True
        )
        audio_file.status = "failed"
        audio_file.save()
        raise self.retry(exc=e)
