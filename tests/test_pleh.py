"""Офлайн-тесты маппинга pleh.tech и провайдера. В сеть не ходят."""
from datetime import date
from pathlib import Path

import pytest

from bot import pleh_client as p
from bot import provider
from bot.parser import Day, SubgroupInfo

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


class TestReaFallbackEnrich:
    @pytest.mark.asyncio
    async def test_fallback_fills_teacher_from_details(self, monkeypatch):
        # Карточка rasp без ФИО → fallback обязан дотянуть его через GetDetails.
        html = (Path(__file__).parent / "fixtures" / "week_34_group.html").read_text()

        async def fake_search(session, query):
            return [{"key": "k"}]

        async def fake_week(session, key, week_num=-1):
            return html

        async def fake_details(session, key, d, pair):
            return [SubgroupInfo(name="", teacher="Иванов Иван Иванович", location="x")]

        monkeypatch.setattr(provider.rea_client, "search", fake_search)
        monkeypatch.setattr(provider.rea_client, "fetch_week", fake_week)
        monkeypatch.setattr(provider.rea_client, "fetch_details", fake_details)

        days = await provider._rea_days(None, "q", date(2026, 4, 20), date(2026, 4, 26))
        lessons = [l for d in days for l in d.lessons]
        assert lessons
        assert all(l.subgroups[0].teacher == "Иванов Иван Иванович" for l in lessons)


class TestFetchDaysRpc:
    @pytest.mark.asyncio
    async def test_long_range_split_into_7_day_windows(self, monkeypatch):
        # RPC group_week режет диапазон > 7 дней (400 «invalid range»).
        calls = []

        async def fake_get(session, path, headers, params):
            calls.append((path, dict(params)))
            return []

        monkeypatch.setattr(p, "_get", fake_get)
        await p.fetch_days(None, "guid", "group", date(2026, 9, 28), date(2026, 10, 14))
        assert [c[0] for c in calls] == ["rpc/group_week"] * 3
        assert [(c[1]["p_from"], c[1]["p_to"]) for c in calls] == [
            ("2026-09-28", "2026-10-04"),
            ("2026-10-05", "2026-10-11"),
            ("2026-10-12", "2026-10-14"),
        ]
        assert all(c[1]["p_group_guid"] == "guid" for c in calls)

    @pytest.mark.asyncio
    async def test_teacher_uses_teacher_week(self, monkeypatch):
        calls = []

        async def fake_get(session, path, headers, params):
            calls.append((path, dict(params)))
            return [_TEACHER_ROW]

        monkeypatch.setattr(p, "_get", fake_get)
        days = await p.fetch_days(None, "slug", "teacher", date(2026, 7, 10), date(2026, 7, 10))
        assert calls[0][0] == "rpc/teacher_week"
        assert calls[0][1]["p_teacher_slug"] == "slug"
        assert days[0].lessons[0].subgroups[0].teacher == "Группа: 15.25Д-ЭФК03/25б"


class TestRpcRows:
    def test_teacher_name_fallback(self):
        row = {**_GROUP_ROW, "instructor_names": None, "teacher_names": None,
               "teacher_name": "Муратова Ольга Анатольевна"}
        les = p._rows_to_days([row], is_teacher=False)[0].lessons[0]
        assert les.subgroups[0].teacher == "Муратова Ольга Анатольевна"

    def test_teacher_stream_rows_merged(self):
        # Поточная пара у препода: одна строка на группу → одно занятие, группы через запятую.
        rows = [_TEACHER_ROW, {**_TEACHER_ROW, "group_name": "15.25Д-ЭФК04/25б"}]
        lessons = p._rows_to_days(rows, is_teacher=True)[0].lessons
        assert len(lessons) == 1
        assert lessons[0].subgroups[0].teacher == "Группа: 15.25Д-ЭФК03/25б, 15.25Д-ЭФК04/25б"
