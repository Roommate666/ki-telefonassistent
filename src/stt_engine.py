"""
Speech-to-Text Engine mit Faster-Whisper.
Wandelt Sprache in Text um.
"""

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_model = None


def init_stt(model_size="medium", device="cpu", language="de"):
    """
    Initialisiert das Whisper-Modell.
    Wird beim Start einmalig aufgerufen.
    """
    global _model
    from faster_whisper import WhisperModel

    compute_type = "int8" if device == "cpu" else "float16"

    logger.info(f"Lade Whisper-Modell: {model_size} (Device: {device}, Compute: {compute_type})")
    start = time.time()

    _model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
    )

    duration = time.time() - start
    logger.info(f"Whisper-Modell geladen in {duration:.1f}s")
    return _model


def transcribe(audio_path, language="de"):
    """
    Transkribiert eine Audio-Datei zu Text.

    Args:
        audio_path: Pfad zur Audio-Datei (WAV, MP3, etc.)
        language: Sprache (Standard: Deutsch)

    Returns:
        dict mit 'text', 'segments', 'language', 'duration'
    """
    global _model

    if _model is None:
        raise RuntimeError("STT-Engine nicht initialisiert. Rufe init_stt() auf.")

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio-Datei nicht gefunden: {audio_path}")

    logger.debug(f"Transkribiere: {audio_path}")
    start = time.time()

    segments, info = _model.transcribe(
        str(audio_path),
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=300,
        ),
    )

    # Segmente sammeln
    result_segments = []
    full_text = []

    for segment in segments:
        result_segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
        })
        full_text.append(segment.text.strip())

    text = " ".join(full_text)
    duration = time.time() - start

    logger.info(f"Transkription ({duration:.1f}s): '{text[:100]}...'")

    return {
        "text": text,
        "segments": result_segments,
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "processing_time": duration,
    }


def transcribe_stream(audio_chunks, language="de"):
    """
    Transkribiert Audio-Chunks im Streaming-Modus.
    Nützlich für Echtzeit-Verarbeitung während des Anrufs.

    Args:
        audio_chunks: Iterator über Audio-Bytes
        language: Sprache

    Yields:
        Teilergebnisse der Transkription
    """
    global _model

    if _model is None:
        raise RuntimeError("STT-Engine nicht initialisiert.")

    import tempfile
    import wave
    import io

    buffer = io.BytesIO()

    for chunk in audio_chunks:
        buffer.write(chunk)

        # Alle 2 Sekunden Audio transkribieren
        if buffer.tell() > 32000:  # ~2s bei 16kHz
            buffer.seek(0)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(buffer.read())
                tmp.flush()

                result = transcribe(tmp.name, language)
                if result["text"].strip():
                    yield result

            buffer = io.BytesIO()
