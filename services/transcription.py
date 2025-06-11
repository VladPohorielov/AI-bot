import whisper
import torch
import warnings
import os
import subprocess
import shutil
from config import WHISPER_MODEL_SIZE

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")


def check_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        # Try to find ffmpeg using shutil.which
        ffmpeg_path = shutil.which('ffmpeg')
        if ffmpeg_path:
            print(f"✅ FFmpeg найден: {ffmpeg_path}")
            return True
        
        # Try to run ffmpeg command
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ FFmpeg доступен")
            return True
        else:
            print("❌ FFmpeg не найден в PATH")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
        print(f"❌ Ошибка проверки FFmpeg: {e}")
        return False


def load_whisper_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Whisper model loading on: {device}")
    
    # Check ffmpeg availability
    if not check_ffmpeg():
        print("⚠️ Внимание: FFmpeg не найден. Обработка некоторых аудио форматов может не работать.")
        print("Установите FFmpeg: winget install ffmpeg")
    
    model = whisper.load_model(WHISPER_MODEL_SIZE, device=device)
    print("Whisper model loaded.")
    return model, device


async def transcribe_audio(model, file_path: str, language: str = "auto") -> str:
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Аудио файл не найден: {file_path}")
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError("Аудио файл пуст")
        
        print(f"🎵 Транскрибирую файл: {file_path} (размер: {file_size} байт)")
        
        if language == "auto" or language is None:
            result = model.transcribe(file_path, fp16=False if model.device == "cpu" else True)
        else:
            result = model.transcribe(file_path, language=language, fp16=False if model.device == "cpu" else True)
        
        transcription = result["text"].strip()
        print(f"✅ Транскрипция готова (длина: {len(transcription)} символов)")
        return transcription
        
    except Exception as e:
        print(f"❌ Ошибка транскрипции: {e}")
        raise e
