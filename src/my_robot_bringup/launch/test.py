import os
import time
from google.cloud import speech, texttospeech

def test_full_cycle():
    # Khởi tạo clients
    try:
        stt_client = speech.SpeechClient()
        tts_client = texttospeech.TextToSpeechClient()
        print("--- Đã kết nối với Google Cloud thành công ---")
    except Exception as e:
        print(f"Lỗi khởi tạo: {e}")
        return

    # --- PHẦN 1: TEST GOOGLE STT (NGHE) ---
    print("\n1. Đang test GOOGLE STT:")
    print("Mời bạn nói một câu tiếng Việt (trong 4 giây)...")
    
    # Ghi âm từ mic của máy Ryzen (dùng arecord có sẵn trên Ubuntu)
    os.system("arecord -d 4 -f cd -r 16000 test_input.wav")
    
    with open("test_input.wav", "rb") as f:
        audio_content = f.read()

    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="vi-VN"
    )

    print("Đang gửi lên Google để nhận diện...")
    response = stt_client.recognize(config=config, audio=audio)
    
    user_text = ""
    for result in response.results:
        user_text = result.alternatives[0].transcript
        print(f">> Bạn đã nói: '{user_text}'")

    if not user_text:
        print(">> Không nghe thấy gì hoặc lỗi nhận diện.")
        return

    # --- PHẦN 2: TEST GOOGLE TTS (NÓI) ---
    print("\n2. Đang test GOOGLE TTS:")
    print(f"Robot đang lặp lại câu: '{user_text}'...")

    synthesis_input = texttospeech.SynthesisInput(text=f"Bạn vừa nói là: {user_text}")
    voice = texttospeech.VoiceSelectionParams(
        language_code="vi-VN", 
        name="vi-VN-Wavenet-D" # Giọng nữ cao cấp
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

    response_tts = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

    with open("test_output.mp3", "wb") as out:
        out.write(response_tts.audio_content)

    # Phát âm thanh ra loa
    os.system("mpg123 -q test_output.mp3")
    print("--- Hoàn thành bài test ---")

if __name__ == "__main__":
    test_full_cycle()