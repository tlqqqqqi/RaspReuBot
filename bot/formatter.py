from datetime import date

from .parser import Day, Lesson, SubgroupInfo, Week

_WEEKDAY_RU = {
    "ПОНЕДЕЛЬНИК": "Понедельник",
    "ВТОРНИК": "Вторник",
    "СРЕДА": "Среда",
    "ЧЕТВЕРГ": "Четверг",
    "ПЯТНИЦА": "Пятница",
    "СУББОТА": "Суббота",
    "ВОСКРЕСЕНЬЕ": "Воскресенье",
}
_MONTH_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

_SEP = "—" * 15


def _date_str(d: date, weekday: str) -> str:
    name = _WEEKDAY_RU.get(weekday, weekday.capitalize())
    return f"{name}, {d.day} {_MONTH_RU[d.month]} {d.year}"


def _subgroup_lines(sg: SubgroupInfo) -> list[str]:
    lines = []
    if sg.location:
        lines.append(f"🏛 {sg.location}")
    if sg.teacher:
        lines.append(sg.teacher)
    return lines


def _lesson_block(lesson: Lesson) -> str:
    lines = [
        f"<b>{lesson.pair_num} пара</b>, {lesson.time_start}–{lesson.time_end}",
        f"<b>{lesson.name}</b> ({lesson.lesson_type})",
    ]

    if not lesson.subgroups:
        # Fallback: info from card (no details fetched)
        if lesson.location:
            lines.append(f"🏛 {lesson.location}")
    elif len(lesson.subgroups) == 1:
        lines.extend(_subgroup_lines(lesson.subgroups[0]))
    else:
        # Deduplicate: if all subgroups share same teacher+location, show once
        unique = {(sg.teacher, sg.location) for sg in lesson.subgroups}
        if len(unique) == 1:
            lines.extend(_subgroup_lines(lesson.subgroups[0]))
        else:
            for sg in lesson.subgroups:
                label = f"  <i>{sg.name}</i>:" if sg.name else "  <i>Вся группа</i>:"
                lines.append(label)
                for detail_line in _subgroup_lines(sg):
                    lines.append(f"  {detail_line}")

    return "\n".join(lines)


def format_day(day: Day) -> str:
    header = f"📅 <b>{_date_str(day.date, day.weekday)}</b>"
    if not day.has_lessons:
        return f"{header}\n\nЗанятий нет"
    blocks = f"\n{_SEP}\n".join(_lesson_block(l) for l in day.lessons)
    return f"{header}\n\n{blocks}"


def format_range(days: list[Day], selection_name: str) -> str:
    if not any(d.has_lessons for d in days):
        return f"<b>{selection_name}</b>\n\nВ этот период занятий нет."
    parts = [f"<b>{selection_name}</b> — расписание на период"]
    for day in days:
        parts.append(format_day(day))
    return "\n\n".join(parts)


def format_week(week: Week, selection_name: str) -> str:
    active_days = [d for d in week.days if d.has_lessons]
    if not active_days:
        return f"<b>{selection_name}</b>\n\nНа этой неделе занятий нет."
    parts = [f"<b>{selection_name}</b> — расписание на неделю"]
    for day in week.days:
        parts.append(format_day(day))
    return "\n\n".join(parts)
