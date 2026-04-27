from datetime import date

import pytest

from bot.handlers.date_schedule import _parse_range, _parse_single


class TestParseSingle:
    def test_dd_mm_uses_current_year(self):
        result = _parse_single("24.05")
        assert result is not None
        assert result.month == 5
        assert result.day == 24
        assert result.year == date.today().year

    def test_dd_mm_yyyy(self):
        assert _parse_single("24.05.2027") == date(2027, 5, 24)

    def test_invalid_day(self):
        assert _parse_single("32.05") is None

    def test_invalid_month(self):
        assert _parse_single("10.13") is None

    def test_invalid_format(self):
        assert _parse_single("abc") is None
        assert _parse_single("") is None
        assert _parse_single("24-05") is None

    def test_single_digit_day_and_month(self):
        result = _parse_single("5.9")
        assert result is not None
        assert result.day == 5
        assert result.month == 9


class TestParseRange:
    def test_simple_range(self):
        result = _parse_range("24.05-27.05")
        assert result is not None
        start, end = result
        assert start == date(date.today().year, 5, 24)
        assert end == date(date.today().year, 5, 27)

    def test_with_spaces_around_dash(self):
        result = _parse_range("24.05 - 27.05")
        assert result is not None
        start, end = result
        assert start.day == 24
        assert end.day == 27

    def test_em_dash(self):
        result = _parse_range("24.05–27.05")
        assert result is not None

    def test_long_dash(self):
        result = _parse_range("24.05—27.05")
        assert result is not None

    def test_reversed_dates_corrected(self):
        result = _parse_range("27.05-24.05")
        assert result is not None
        start, end = result
        assert start.day == 24
        assert end.day == 27

    def test_with_full_years(self):
        result = _parse_range("24.05.2027-30.05.2027")
        assert result is not None
        start, end = result
        assert start == date(2027, 5, 24)
        assert end == date(2027, 5, 30)

    def test_invalid_one_part(self):
        assert _parse_range("24.05") is None
        assert _parse_range("abc-27.05") is None
        assert _parse_range("24.05-xyz") is None
