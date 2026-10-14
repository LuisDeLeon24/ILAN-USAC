from app.demo_frames import choose_indexes, pick_positions


def test_indexes_are_spread_and_unique() -> None:
    indexes = choose_indexes(240, 8)
    assert indexes[0] == 0
    assert indexes[-1] == 239
    assert len(indexes) == len(set(indexes))
    assert indexes == sorted(indexes)


def test_pick_prefers_frames_with_detections_and_fills_to_six() -> None:
    hits = [False, True, False, True, False]
    assert pick_positions(hits) == [1, 3, 0, 2, 4]
    many = [True] * 10
    assert pick_positions(many) == list(range(8))
    assert choose_indexes(0, 8) == []
