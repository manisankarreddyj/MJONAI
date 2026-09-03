"""Walk-forward windows: embargo must separate training from
validation so boundary-spanning information cannot leak."""

from datetime import datetime, timedelta

from research.walk_forward.walk_forward_windows import (
    WalkForwardWindowGenerator,
)


def generate(**overrides):
    defaults = dict(
        start=datetime(2020, 1, 1),
        end=datetime(2024, 12, 31),
        training_years=2,
        validation_years=1,
    )
    defaults.update(overrides)
    return WalkForwardWindowGenerator().generate(**defaults)


def test_validation_starts_after_embargo():
    windows = generate(embargo_days=7)

    assert windows

    for window in windows:
        gap = window.validation_start - window.train_end
        assert gap == timedelta(days=7)


def test_zero_embargo_keeps_adjacency():
    windows = generate(embargo_days=0)

    for window in windows:
        assert window.validation_start == window.train_end


def test_default_embargo_is_seven_days():
    windows = generate()

    for window in windows:
        assert window.validation_start - window.train_end == timedelta(days=7)


def test_windows_fit_within_bounds():
    end = datetime(2024, 12, 31)

    for window in generate(embargo_days=10):
        assert window.train_start >= datetime(2020, 1, 1)
        assert window.train_end < window.validation_start
        assert window.validation_end <= end


def test_step_advances_by_one_year():
    windows = generate()

    for previous, current in zip(windows, windows[1:]):
        assert current.train_start.year == previous.train_start.year + 1
