from app.parsers import robob2b, robot_moscow, robort

PARSERS = {
    robob2b.CODE: (
        "robob2b.ru",
        "Обходит каталог robob2b.ru и записывает карточки этого сайта.",
        robob2b.collect,
    ),
    robort.CODE: (
        "robort.ru",
        "Обходит разделы robort.ru: сервисные роботы, манипуляторы, уборщики, склад и колёсные платформы.",
        robort.collect,
    ),
    robot_moscow.CODE: (
        "robot.moscow",
        "Читает HTML-каталог robot.moscow и берёт только роботов с ценой.",
        robot_moscow.collect,
    ),
}


def codes() -> list[str]:
    return sorted(PARSERS)


def collect(code: str):
    try:
        _title, _summary, runner = PARSERS[code]
    except KeyError as exc:
        raise KeyError(code) from exc
    return runner()
