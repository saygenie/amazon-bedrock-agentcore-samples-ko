"""WebRTC <-> Nova Sonic 오디오 변환 및 출력 트랙입니다.

Nova Sonic은 16kHz/16-bit/mono PCM 입력을 받고 24kHz/16-bit/mono PCM 출력을
생성합니다. 이 모듈은 형식 변환을 처리하고 Nova Sonic 응답을 브라우저로
스트리밍하는 WebRTC 오디오 트랙을 제공합니다.
"""

import asyncio
import fractions
import time

import av
from aiortc.mediastreams import AudioFrame, MediaStreamTrack

# 오디오 형식 상수
INPUT_SAMPLE_RATE = 16000  # Nova Sonic 입력 형식
OUTPUT_SAMPLE_RATE = 24000  # Nova Sonic 출력 형식
BYTES_PER_SAMPLE = 2  # 16-bit PCM
FRAME_DURATION_MS = 20  # WebRTC 프레임 크기
SAMPLES_PER_FRAME = OUTPUT_SAMPLE_RATE * FRAME_DURATION_MS // 1000  # 480

# Resampler는 WebRTC 입력(일반적으로 48kHz stereo)을 Nova Sonic 형식으로 변환
_resampler = av.AudioResampler(format="s16", layout="mono", rate=INPUT_SAMPLE_RATE)

# 사용 가능한 오디오가 없을 때 사용할 미리 생성된 무음 프레임
_SILENCE = AudioFrame(format="s16", layout="mono", samples=SAMPLES_PER_FRAME)
_SILENCE.sample_rate = OUTPUT_SAMPLE_RATE
_SILENCE.planes[0].update(bytes(SAMPLES_PER_FRAME * BYTES_PER_SAMPLE))


def convert_to_16khz(frame):
    """WebRTC 오디오 프레임을 16kHz/16-bit/mono PCM 바이트로 변환합니다."""
    resampled = _resampler.resample(frame)
    return b"".join(f.planes[0] for f in resampled) if resampled else b""


class OutputTrack(MediaStreamTrack):
    """Nova Sonic 응답을 브라우저에서 재생하는 WebRTC 오디오 트랙입니다.

    add_audio()를 통해 오디오 바이트를 av.AudioFifo에 대기시키며, 이 큐가 정확한
    프레임 크기로 분할합니다. recv()는 실시간 속도에 맞춰 고정 크기 프레임을
    읽고, 버퍼가 비어 있으면 무음을 반환합니다.
    """

    kind = "audio"

    def __init__(self):
        super().__init__()
        self._fifo = av.AudioFifo()
        self._start_time = None
        self._timestamp = 0
        self._muted = False

    async def recv(self):
        """실시간 속도에 맞춰 다음 20ms 오디오 프레임을 반환합니다."""
        # 첫 호출에서 시간 측정 초기화
        if self._start_time is None:
            self._start_time = time.time()
            self._frame_count = 0

        # 이 프레임의 예약 시각까지 대기(20ms 간격 유지)
        delay = self._start_time + self._frame_count * (FRAME_DURATION_MS / 1000) - time.time()
        if delay > 0:
            await asyncio.sleep(delay)

        # 음소거(barge-in) 상태이거나 버퍼가 비어 있으면 무음 반환
        if self._muted:
            frame = _SILENCE
        else:
            frame = self._fifo.read(SAMPLES_PER_FRAME, partial=False)
            if frame is None:
                frame = _SILENCE

        frame.pts = self._timestamp
        frame.time_base = fractions.Fraction(1, OUTPUT_SAMPLE_RATE)
        self._timestamp += SAMPLES_PER_FRAME
        self._frame_count += 1
        return frame

    def clear(self):
        """재생을 중지하고 버퍼링된 모든 오디오를 폐기합니다(barge-in)."""
        self._muted = True
        self._fifo = av.AudioFifo()

    def add_audio(self, audio_bytes):
        """Nova Sonic의 PCM 바이트를 버퍼링합니다. AudioFifo가 분할을 처리합니다."""
        self._muted = False
        frame = AudioFrame(format="s16", layout="mono", samples=len(audio_bytes) // BYTES_PER_SAMPLE)
        frame.planes[0].update(audio_bytes)
        frame.sample_rate = OUTPUT_SAMPLE_RATE
        self._fifo.write(frame)
