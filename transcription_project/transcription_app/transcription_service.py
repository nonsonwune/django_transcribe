import os
import logging
from pathlib import Path
from pyannote.audio import Pipeline
import whisper
from pydub import AudioSegment
import shutil
import json
import datetime
from django.conf import settings


class TranscriptionService:
    def __init__(self, session_id):
        self.auth_token = settings.PYANNOTE_AUTH_TOKEN
        self.session_id = session_id
        self.pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", use_auth_token=self.auth_token
        )

    def convert_to_wav(self, audio_path):
        try:
            audio_path = Path(audio_path)
            if not audio_path.is_file():
                logging.error(f"Input file does not exist: {audio_path}")
                return None

            if audio_path.suffix.lower() == ".wav":
                logging.info(f"File is already in WAV format: {audio_path}")
                return audio_path

            wav_path = audio_path.with_suffix(".wav")
            non_wave_files_dir = Path("non_wave_files") / self.session_id
            non_wave_files_dir.mkdir(parents=True, exist_ok=True)

            try:
                audio = AudioSegment.from_file(audio_path)
                audio.export(wav_path, format="wav")
                logging.info(f"Successfully converted {audio_path} to {wav_path}")

                shutil.move(audio_path, non_wave_files_dir / audio_path.name)
                logging.info(
                    f"Moved original file to {non_wave_files_dir / audio_path.name}"
                )

                return wav_path
            except Exception as e:
                logging.error(f"Error converting {audio_path} to WAV: {str(e)}")
                return None

        except Exception as e:
            logging.error(f"Unexpected error in convert_to_wav: {str(e)}")
            return None

    def transcribe_audio(self, audio_path):
        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path), language="en")
        logging.info(f"Transcribed {audio_path}")
        return result["text"], result["segments"]

    def perform_speaker_diarization(self, audio_path, segments):
        diarization = self.pipeline(audio_path)
        labels = [
            {"start": segment.start, "end": segment.end, "label": speaker}
            for segment, _, speaker in diarization.itertracks(yield_label=True)
        ]
        for i, segment in enumerate(segments):
            max_overlap = 0
            best_match_label = "UNKNOWN"
            for label in labels:
                overlap_start = max(segment["start"], label["start"])
                overlap_end = min(segment["end"], label["end"])
                overlap = max(0, overlap_end - overlap_start)
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_match_label = label["label"]
            segment["speaker"] = best_match_label
        return segments

    def save_transcription_with_speaker_labels(
        self, transcription, segments, audio_path
    ):
        audio_name = Path(audio_path).stem
        transcription_dir = Path("transcriptions") / self.session_id / audio_name
        transcription_dir.mkdir(parents=True, exist_ok=True)
        file_name = transcription_dir / f"{audio_name}_transcription_with_speakers.txt"

        with open(file_name, "w") as f:
            for segment in segments:
                speaker = segment.get("speaker", "UNKNOWN")
                f.write(f"{speaker}: {segment['text']}\n")
        logging.info(f"Saved transcription to {file_name}")

    def save_transcription_as_json(self, transcription, segments, audio_path):
        audio_name = Path(audio_path).stem
        transcription_dir = (
            Path(settings.MEDIA_ROOT)
            / "transcriptions"
            / str(self.session_id)
            / audio_name
        )
        transcription_dir.mkdir(parents=True, exist_ok=True)
        file_name = transcription_dir / f"{audio_name}_transcription_with_speakers.json"

        segments_with_speakers = [
            {
                "text": segment["text"],
                "speaker": segment.get("speaker", "UNKNOWN"),
                "start": segment["start"],
                "end": segment["end"],
            }
            for segment in segments
        ]
        json_data = {"transcription": transcription, "segments": segments_with_speakers}

        with open(file_name, "w") as f:
            json.dump(json_data, f, indent=4)
        logging.info(f"Saved JSON transcription to {file_name}")

    def save_transcription_as_srt(self, transcription, segments, audio_path):
        audio_name = Path(audio_path).stem
        transcription_dir = (
            Path(settings.MEDIA_ROOT)
            / "transcriptions"
            / str(self.session_id)
            / audio_name
        )
        transcription_dir.mkdir(parents=True, exist_ok=True)
        file_name = transcription_dir / f"{audio_name}_transcription_with_speakers.srt"

        with open(file_name, "w") as f:
            for i, segment in enumerate(segments, start=1):
                speaker = segment.get("speaker", "UNKNOWN")
                start_time = datetime.timedelta(seconds=segment["start"])
                end_time = datetime.timedelta(seconds=segment["end"])
                f.write(
                    f"{i}\n{start_time} --> {end_time}\n{speaker}: {segment['text']}\n\n"
                )
        logging.info(f"Saved SRT transcription to {file_name}")

    def save_transcription_as_vtt(self, transcription, segments, audio_path):
        audio_name = Path(audio_path).stem
        transcription_dir = (
            Path(settings.MEDIA_ROOT)
            / "transcriptions"
            / str(self.session_id)
            / audio_name
        )
        transcription_dir.mkdir(parents=True, exist_ok=True)
        file_name = transcription_dir / f"{audio_name}_transcription_with_speakers.vtt"

        with open(file_name, "w") as f:
            f.write("WEBVTT\n\n")
            for i, segment in enumerate(segments, start=1):
                speaker = segment.get("speaker", "UNKNOWN")
                start_time = datetime.timedelta(seconds=segment["start"])
                end_time = datetime.timedelta(seconds=segment["end"])
                f.write(
                    f"{i}\n{start_time} --> {end_time}\n{speaker}: {segment['text']}\n\n"
                )
        logging.info(f"Saved VTT transcription to {file_name}")

    def process_audio_file(service, audio_file):
        try:
            logging.info(f"Starting processing for {audio_file}")

            wav_file = service.convert_to_wav(audio_file)
            if wav_file is None:
                logging.error(f"Failed to convert {audio_file} to WAV format")
                return False

            logging.info(f"Successfully converted to WAV: {wav_file}")

            transcription, segments = service.transcribe_audio(wav_file)
            if not transcription or not segments:
                logging.error(f"Transcription failed for {wav_file}")
                return False

            logging.info(f"Transcription successful for {wav_file}")

            segments = service.perform_speaker_diarization(wav_file, segments)
            if not segments:
                logging.error(f"Diarization failed for {wav_file}")
                return False

            logging.info(f"Diarization successful for {wav_file}")

            service.save_transcription_with_speaker_labels(
                transcription, segments, wav_file
            )
            service.save_transcription_as_json(transcription, segments, wav_file)
            service.save_transcription_as_srt(transcription, segments, wav_file)
            service.save_transcription_as_vtt(transcription, segments, wav_file)

            logging.info(f"Successfully processed {wav_file}")
            return True, "Processing completed successfully"
        except Exception as e:
            error_message = f"An error occurred processing {audio_file}: {str(e)}"
            logging.error(error_message, exc_info=True)
            return False, error_message


def process_audio_file_wrapper(args):
    service, audio_file = args
    process_audio_file(service, audio_file)
