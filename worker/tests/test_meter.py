from app.meter import Meter


def test_each_processed_loop_counts_as_video_time() -> None:
    meter = Meter()
    meter.add_ms(0, 60_000)
    first = meter.flush()
    meter.add_ms(0, 60_000)
    second = meter.flush()
    assert first == 1.0
    assert second == 1.0


def test_partial_minutes_round_to_two_decimals() -> None:
    meter = Meter()
    meter.add_ms(0, 20_000)
    assert meter.take(15_000) == 0.33
    assert meter.pending_ms < 1_000
    assert meter.flush() is None
