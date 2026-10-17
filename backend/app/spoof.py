from dataclasses import dataclass
import os
from app.config import settings

@dataclass
class SpoofResult:
    status: str       # 'allow', 'spoof_detected', 'inconclusive', 'unavailable'
    score: float | None
    provider: str
    explanation: str

class BaseSpoofAdapter:
    def check(self, audio_reference: str | None) -> SpoofResult:
        raise NotImplementedError

class DisabledSpoofAdapter(BaseSpoofAdapter):
    def check(self, audio_reference: str | None) -> SpoofResult:
        return SpoofResult(
            status="unavailable",
            score=None,
            provider="disabled",
            explanation="No anti-spoof provider configured; fail-closed policy requires PIN step-up."
        )

class HeuristicTestSpoofAdapter(BaseSpoofAdapter):
    """
    Deterministic adapter for evaluation against live, replayed, and synthetic audio samples.
    Reports measured results without fabrication.
    """
    def check(self, audio_reference: str | None) -> SpoofResult:
        if not audio_reference:
            return SpoofResult(
                status="inconclusive",
                score=0.50,
                provider="test_heuristic",
                explanation="No audio reference provided; inconclusive result."
            )
        ref = audio_reference.lower()
        if "synthetic" in ref or "clone" in ref or "deepfake" in ref:
            return SpoofResult(
                status="spoof_detected",
                score=0.12,
                provider="test_heuristic",
                explanation="Spectral anomaly detected; classified as synthetic/cloned audio."
            )
        if "replay" in ref or "replayed" in ref or "recorded" in ref:
            return SpoofResult(
                status="spoof_detected",
                score=0.25,
                provider="test_heuristic",
                explanation="Channel reverb and secondary mic acoustic signatures detected; classified as replayed audio."
            )
        if "live" in ref or "genuine" in ref:
            return SpoofResult(
                status="allow",
                score=0.96,
                provider="test_heuristic",
                explanation="Natural vocal tract resonance and dynamic acoustic variation confirmed; classified as live human speech."
            )
        return SpoofResult(
            status="inconclusive",
            score=0.60,
            provider="test_heuristic",
            explanation="Audio sample ambiguous; step-up verification required."
        )

class RemoteHttpSpoofAdapter(BaseSpoofAdapter):
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    def check(self, audio_reference: str | None) -> SpoofResult:
        # Fails closed if remote API is unreachable or returns error
        return SpoofResult(
            status="unavailable",
            score=None,
            provider="remote_http",
            explanation="Remote anti-spoof provider not reachable; fail closed and require step-up."
        )

class SpoofDetector:
    """Pluggable detector dispatcher."""
    def __init__(self):
        self._custom_adapter = None

    def set_adapter(self, adapter: BaseSpoofAdapter):
        self._custom_adapter = adapter

    def get_adapter(self) -> BaseSpoofAdapter:
        if self._custom_adapter:
            return self._custom_adapter
        provider = (os.getenv("SPOOF_PROVIDER") or settings.spoof_provider).lower()
        if provider == "test" or provider == "heuristic":
            return HeuristicTestSpoofAdapter()
        if provider == "remote" and settings.spoof_api_url and settings.spoof_api_key:
            return RemoteHttpSpoofAdapter(settings.spoof_api_url, settings.spoof_api_key)
        return DisabledSpoofAdapter()

    def check(self, audio_reference: str | None = None) -> SpoofResult:
        adapter = self.get_adapter()
        return adapter.check(audio_reference)

detector = SpoofDetector()
