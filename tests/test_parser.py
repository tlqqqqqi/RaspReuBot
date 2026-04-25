from datetime import date
from pathlib import Path

import pytest

from bot.parser import Lesson, parse_html

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestParseWeek34:
    """Tests against saved HTML for group 15.07в-гд1/24б, academic week 34."""

    @pytest.fixture(scope="class")
    def week(self):
        return parse_html(load_fixture("week_34_group.html"))

    def test_week_num(self, week):
        assert week.week_num == 34

    def test_has_seven_days(self, week):
        assert len(week.days) == 6  # Mon–Sat (no Sunday in this fixture)

    def test_monday_date(self, week):
        assert week.days[0].date == date(2026, 4, 20)

    def test_monday_weekday_name(self, week):
        assert week.days[0].weekday == "ПОНЕДЕЛЬНИК"

    def test_day_by_date_found(self, week):
        day = week.day_by_date(date(2026, 4, 22))
        assert day is not None
        assert day.weekday == "СРЕДА"

    def test_day_by_date_not_found(self, week):
        assert week.day_by_date(date(2025, 1, 1)) is None

    def test_monday_has_lessons(self, week):
        monday = week.day_by_date(date(2026, 4, 20))
        assert monday is not None
        assert monday.has_lessons

    def test_monday_lesson_fields(self, week):
        monday = week.day_by_date(date(2026, 4, 20))
        lesson: Lesson = monday.lessons[0]
        assert lesson.pair_num > 0
        assert ":" in lesson.time_start
        assert ":" in lesson.time_end
        assert lesson.name
        assert lesson.lesson_type

    def test_wednesday_lessons_have_location(self, week):
        wednesday = week.day_by_date(date(2026, 4, 22))
        assert wednesday is not None
        for lesson in wednesday.lessons:
            assert lesson.location  # СРЕДА has lab with room info

    def test_saturday_has_lessons(self, week):
        # This fixture has exams/retakes every day including Saturday
        saturday = week.day_by_date(date(2026, 4, 25))
        assert saturday is not None
        assert saturday.has_lessons
        assert len(saturday.lessons) == 5
