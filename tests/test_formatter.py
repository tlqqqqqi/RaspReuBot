from datetime import date

from bot.formatter import format_day, format_free_rooms, format_range, format_week
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


class TestFormatRange:
    def test_range_with_lessons(self):
        days = [
            Day(date=date(2026, 5, 4), weekday="ПОНЕДЕЛЬНИК", lessons=[_lesson(name="Химия")]),
            Day(date=date(2026, 5, 5), weekday="ВТОРНИК", lessons=[]),
        ]
        text = format_range(days, "МояГруппа")
        assert "МояГруппа" in text
        assert "Химия" in text
        assert "Занятий нет" in text

    def test_range_all_empty(self):
        days = [Day(date=date(2026, 5, i), weekday="X", lessons=[]) for i in range(4, 8)]
        text = format_range(days, "МояГруппа")
        assert "МояГруппа" in text
        assert "занятий нет" in text.lower()

    def test_range_contains_all_days(self):
        days = [
            Day(date=date(2026, 5, 4), weekday="ПОНЕДЕЛЬНИК", lessons=[_lesson(name="Химия")]),
            Day(date=date(2026, 5, 5), weekday="ВТОРНИК", lessons=[_lesson(name="Физика")]),
        ]
        text = format_range(days, "Г")
        assert "Химия" in text
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


class TestFreeRooms:
    def _rooms(self):
        return [
            {"room_number": "305", "floor": 3, "capacity": 30,
             "room_category": "Общего назначения"},
            {"room_number": "101", "floor": 1, "capacity": 40,
             "room_category": "Мультимедийная"},
            {"room_number": "310", "floor": 3, "capacity": None,
             "room_category": None},
        ]

    def test_groups_by_floor(self):
        text = format_free_rooms("3 корпус", date(2026, 6, 9), 2, self._rooms())
        assert "3 корпус" in text
        assert "2 пара (10:10–11:40)" in text
        assert "Свободно: 3" in text
        assert "1 этаж" in text and "3 этаж" in text
        # этаж 1 идёт раньше этажа 3
        assert text.index("1 этаж") < text.index("3 этаж")
        assert "• 101 — 40 мест, Мультимедийная" in text
        # пустые capacity/category не ломают строку
        assert "• 310" in text

    def test_empty(self):
        text = format_free_rooms("9 корпус", date(2026, 6, 9), 1, [])
        assert "Свободных аудиторий нет" in text
