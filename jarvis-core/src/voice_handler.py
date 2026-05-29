"""STT/TTS 음성 인터페이스 처리 모듈 (선택 기능).

의존 라이브러리가 없는 환경에서도 import가 가능하도록
SpeechRecognition / pyttsx3를 소프트 임포트로 처리한다.
설치: pip install SpeechRecognition pyttsx3 pyaudio
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False
    logger.warning("SpeechRecognition 미설치 — STT 비활성화")

try:
    import pyttsx3
    _TTS_AVAILABLE = True
except ImportError:
    _TTS_AVAILABLE = False
    logger.warning("pyttsx3 미설치 — TTS 비활성화")


class VoiceHandler:
    """STT(음성→텍스트) 및 TTS(텍스트→음성) 인터페이스."""

    def __init__(self, language: str = "ko-KR"):
        self.language = language
        self._recognizer = sr.Recognizer() if _SR_AVAILABLE else None
        self._tts_engine = pyttsx3.init() if _TTS_AVAILABLE else None

        if self._tts_engine:
            self._tts_engine.setProperty("rate", 160)   # 말하기 속도
            self._tts_engine.setProperty("volume", 0.9)

    # ------------------------------------------------------------------
    # STT
    # ------------------------------------------------------------------

    def listen(self, timeout: int = 5, phrase_limit: int = 10) -> Optional[str]:
        """마이크 입력을 텍스트로 변환.

        Returns:
            인식된 텍스트 문자열, 실패 시 None.
        """
        if not _SR_AVAILABLE or self._recognizer is None:
            logger.error("STT 불가: SpeechRecognition 미설치")
            return None

        with sr.Microphone() as source:
            logger.info("음성 입력 대기 중... (최대 %ds)", timeout)
            self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self._recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_limit
                )
                text = self._recognizer.recognize_google(audio, language=self.language)
                logger.info("STT 결과: %s", text)
                return text
            except sr.WaitTimeoutError:
                logger.warning("음성 입력 시간 초과")
            except sr.UnknownValueError:
                logger.warning("음성 인식 실패 (명확하지 않은 입력)")
            except sr.RequestError as exc:
                logger.error("STT 서비스 오류: %s", exc)
        return None

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------

    def speak(self, text: str) -> None:
        """텍스트를 음성으로 출력."""
        if not _TTS_AVAILABLE or self._tts_engine is None:
            logger.error("TTS 불가: pyttsx3 미설치")
            print(f"[JARVIS] {text}")   # 폴백: 터미널 출력
            return

        logger.info("TTS 출력: %s", text[:50])
        self._tts_engine.say(text)
        self._tts_engine.runAndWait()

    # ------------------------------------------------------------------
    # 편의 메서드
    # ------------------------------------------------------------------

    def listen_and_speak(self, prompt: str = "") -> Optional[str]:
        """TTS로 프롬프트 읽기 → STT로 응답 수신."""
        if prompt:
            self.speak(prompt)
        return self.listen()

    @property
    def available(self) -> dict:
        return {"stt": _SR_AVAILABLE, "tts": _TTS_AVAILABLE}
