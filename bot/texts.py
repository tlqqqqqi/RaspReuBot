START_WELCOME = (
    "Привет! Я помогу следить за расписанием РЭУ им. Плеханова.\n\n"
    "Введи номер группы или ФИО преподавателя:"
)
ASK_GROUP_AGAIN = "Введи номер группы или ФИО преподавателя:"
SEARCH_PICK = "Выбери из найденного:"
SEARCH_EMPTY = "Ничего не нашлось. Попробуй другой запрос:"
SEARCH_ERROR = "⚠️ Не удалось связаться с сайтом. Попробуй позже."
GROUP_SAVED = "✅ Сохранено: <b>{name}</b>"
GROUP_NOT_SET = "Сначала выбери группу — нажми /start."

MAIN_MENU = "Главное меню:"

BTN_TODAY = "📅 Сегодня"
BTN_TOMORROW = "📅 Завтра"
BTN_WEEK = "📋 Вся неделя"
BTN_CHANGE_GROUP = "✏️ Изменить группу"
BTN_SETTINGS = "⚙️ Настройки рассылки"
BTN_BACK = "← Назад"

SETTINGS_TITLE = "⚙️ Настройки рассылки\n\n{morning_line}\n{evening_line}\n{weekly_line}"
MORNING_ON = "🌅 Утренняя (на сегодня): <b>вкл.</b> в <b>{time}</b>"
MORNING_OFF = "🌅 Утренняя (на сегодня): <b>выкл.</b>"
EVENING_ON = "🌙 Вечерняя (на завтра): <b>вкл.</b> в <b>{time}</b>"
EVENING_OFF = "🌙 Вечерняя (на завтра): <b>выкл.</b>"
WEEKLY_ON = "📋 Еженедельная (по воскр.): <b>вкл.</b> в <b>{time}</b>"
WEEKLY_OFF = "📋 Еженедельная (по воскр.): <b>выкл.</b>"

BTN_MORNING_ON = "🌅 Утренняя: вкл."
BTN_MORNING_OFF = "🌅 Утренняя: выкл."
BTN_EVENING_ON = "🌙 Вечерняя: вкл."
BTN_EVENING_OFF = "🌙 Вечерняя: выкл."
BTN_WEEKLY_ON = "📋 Еженедельная: вкл."
BTN_WEEKLY_OFF = "📋 Еженедельная: выкл."
BTN_SET_MORNING_TIME = "🕐 Время утренней"
BTN_SET_EVENING_TIME = "🕐 Время вечерней"
BTN_SET_WEEKLY_TIME = "🕐 Время еженедельной"

ASK_TIME = (
    "Введи время в формате ЧЧ:ММ\n"
    "(например, <code>07:30</code>):"
)
TIME_INVALID = "⚠️ Неверный формат. Введи время как ЧЧ:ММ, например <code>07:30</code>:"
TIME_SAVED = "✅ Время сохранено: <b>{time}</b>"

SCHEDULE_LOADING = "Загружаю расписание…"
SCHEDULE_ERROR = "⚠️ Не удалось загрузить расписание. Попробуй позже."

BTN_BY_DATE = "📆 На дату"
BTN_BY_RANGE = "📆 Период"

ASK_DATE = (
    "Введи дату в формате <code>ДД.ММ</code> или <code>ДД.ММ.ГГГГ</code>\n"
    "(например, <code>24.05</code>):"
)
ASK_RANGE = (
    "Введи период в формате <code>ДД.ММ–ДД.ММ</code> или <code>ДД.ММ.ГГГГ–ДД.ММ.ГГГГ</code>\n"
    "(например, <code>24.05–27.05</code>):"
)
DATE_INVALID = (
    "⚠️ Неверный формат даты. Введи как <code>ДД.ММ</code> или <code>ДД.ММ.ГГГГ</code>:"
)
RANGE_INVALID = (
    "⚠️ Неверный формат. Введи период как <code>ДД.ММ–ДД.ММ</code>\n"
    "(например, <code>24.05–27.05</code>):"
)
RANGE_TOO_LONG = "⚠️ Максимальный период — 14 дней."
