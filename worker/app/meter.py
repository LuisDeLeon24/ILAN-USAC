"""Video time converted to analyzed minutes. Each loop adds its own span."""


class Meter:
    def __init__(self) -> None:
        self.pending_ms = 0.0

    def add_ms(self, start_ms: float, end_ms: float) -> None:
        if end_ms > start_ms:
            self.pending_ms += end_ms - start_ms

    def take(self, minimum_ms: float) -> float | None:
        if self.pending_ms < minimum_ms:
            return None
        return self._emit()

    def flush(self) -> float | None:
        if self.pending_ms <= 0:
            return None
        return self._emit()

    def _emit(self) -> float | None:
        minutes = round(self.pending_ms / 60_000, 2)
        if minutes <= 0:
            return None
        self.pending_ms = max(0.0, self.pending_ms - minutes * 60_000)
        return minutes
