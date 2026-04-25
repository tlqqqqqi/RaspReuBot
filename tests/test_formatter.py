from datetime import date

from bot.formatter import format_day, format_week
from bot.parser import Day, Lesson, Week


def _lesson(pair_num=1, name="Математика", lesson_type="Лекция", location="1 корп — 101"):
    return Lesson(
        pair_num=pair_num,
        time_start="09:00",
        time_end="10:30",
        name=name,
        lesson_type=lesson_type,
        location=location,
    )


class TestFormatDay:
    def test_day_with_lessons(self):
        day = Day(date=date(2026, 4, 25), weekday="СУББОТА", lessons=[_lesson()])
        text = format_day(day)
        assert "Суббота" in text
        assert "25" in text
        assert "апреля" in text
        assert "Математика" in text
        assert "Лекция" in text
        assert "1 корп" in text
        assert "1 пара" in text

    def test_empty_day(self):
        day = Day(date=date(2026, 4, 26), weekday="ВОСКРЕСЕНЬЕ", lessons=[])
        text = format_day(day)
        assert "Воскресенье" in text
        assert "Занятий нет" in text

    def test_no_location_omits_building_line(self):
        day = Day(date=date(2026, 4, 25), weekday="СУББОТА", lessons=[_lesson(location="")])
        text = format_day(day)
        assert "🏛" not in text

    def test_multiple_lessons_separated(self):
        day = Day(
            date=date(2026, 4, 25),
            weekday="СУББОТА",
            lessons=[_lesson(pair_num=1, name="Матан"), _lesson(pair_num=2, name="Физика")],
        )
        text = format_day(day)
        assert "Матан" in text
        assert "Физика" in text


class TestFormatWeek:
    def test_all_empty_week(self):
        days = [Day(date=date(2026, 4, 20 + i), weekday="X", lessons=[]) for i in range(6)]
        week = Week(week_num=34, days=days)
        text = format_week(week, "МояГруппа")
        assert "МояГруппа" in text
        assert "занятий нет" in text.lower()

    def test_week_with_lessons_contains_name(self):
        days = [Day(date=date(2026, 4, 25), weekday="СУББОТА", lessons=[_lesson()])]
        week = Week(week_num=34, days=days)
        text = format_week(week, "Группа123")
        assert "Группа123" in text
        assert "Математика" in text
