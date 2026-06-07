"""Офлайн-тесты маппинга pleh.tech и провайдера. В сеть не ходят."""
from datetime import date

from bot import pleh_client as p
from bot import provider
from bot.parser import Day

_GROUP_ROW = {
    "day": "2026-06-16", "period": 1, "discipline": "Макроэкономика",
    "workload_type": "Практическое занятие", "room": "549",
    "building": "6 корпус", "campus": "Основная", "subgroup": None,
    "instructor_names": ["Дзарасов Руслан Солтанович"],
}
_TEACHER_ROW = {
    "day": "2026-07-10", "period": 3, "discipline": "Математический анализ",
    "workload_type": "Консультации", "room": "261", "building": "6 корпус",
    "campus": "Основная", "group_name": "15.25Д-ЭФК03/25б",
}


class TestMapping:
    def test_group_row_to_day(self):
        days = p._rows_to_days([_GROUP_ROW], is_teacher=False)
        assert len(days) == 1
        d = days[0]
        assert d.date == date(2026, 6, 16)
        assert d.weekday == "ВТОРНИК"
        les = d.lessons[0]
        assert les.pair_num == 1
        assert les.time_start == "08:30" and les.time_end == "10:00"
        assert les.name == "Макроэкономика"
        assert les.lesson_type == "Практическое занятие"
        assert les.location == "6 корпус — 549, пл. Основная"
        assert les.subgroups[0].teacher == "Дзарасов Руслан Солтанович"

    def test_teacher_row_shows_group(self):
        days = p._rows_to_days([_TEACHER_ROW], is_teacher=True)
        les = days[0].lessons[0]
        assert "15.25Д-ЭФК03/25б" in les.subgroups[0].teacher

    def test_online_location_falls_back_to_platform(self):
        row = {**_GROUP_ROW, "building": None, "room": None,
               "campus": None, "platform": "Teams"}
        assert p._format_location(row) == "Teams"

    def test_days_sorted_and_grouped(self):
        rows = [
            {**_GROUP_ROW, "day": "2026-06-17", "period": 2},
            _GROUP_ROW,
            {**_GROUP_ROW, "period": 3},
        ]
        days = p._rows_to_days(rows, is_teacher=False)
        assert [d.date.isoformat() for d in days] == ["2026-06-16", "2026-06-17"]
        assert [l.pair_num for l in days[0].lessons] == [1, 3]


class TestStubDays:
    def test_fills_missing_dates(self):
        real = Day(date=date(2026, 6, 16), weekday="ВТОРНИК", lessons=[])
        # подменим: день с парами
        real = p._rows_to_days([_GROUP_ROW], is_teacher=False)[0]
        dates = [date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17)]
        out = provider.stub_days([real], dates)
        assert [d.date for d in out] == dates
        assert out[0].lessons == [] and out[2].lessons == []
        assert out[1].lessons  # вторник с парами
        assert out[0].weekday == "ПОНЕДЕЛЬНИК"
