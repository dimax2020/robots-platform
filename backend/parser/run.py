"""Ежедневный парсинг и импорт внутри контейнера; --once для ручного запуска."""

import argparse
from datetime import datetime, timedelta
import fcntl
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)


def next_run(now, hour):
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return target if target > now else target + timedelta(days=1)


def run_once():
    env = os.environ.copy()
    env.setdefault("OUTPUT_FILE", "/app/data/robots.json")
    output = Path(env["OUTPUT_FILE"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with (output.parent / ".parser.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.warning("Парсинг уже выполняется, повторный запуск пропущен")
            return
        failures = []
        for script, destination in (
            ("parser.py", output),
            ("robort.py", Path(env.get("ROBORT_OUTPUT_FILE", str(output.parent / "robort_robots.json"))))
        ):
            source_env = {**env, "OUTPUT_FILE": str(destination)}
            try:
                subprocess.run([sys.executable, str(Path(__file__).with_name(script))], env=source_env, check=True)
                subprocess.run(
                    [sys.executable, "-m", "scripts.import_robots", str(destination)],
                    env=source_env, check=True,
                )
                # Обновляем каталог после каждого успешного импорта.
                marker = output.parent / ".catalog-refresh"
                temporary = marker.with_suffix(".tmp")
                temporary.write_text(str(uuid4()))
                temporary.replace(marker)
            except subprocess.CalledProcessError:
                log.exception("Ошибка парсинга или импорта %s", script)
                failures.append(script)
        if failures:
            raise RuntimeError("Не обработаны источники: " + ", ".join(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.once:
        run_once()
        return
    zone = ZoneInfo(os.environ.get("PARSER_TIMEZONE", "Europe/Moscow"))
    hour = int(os.environ.get("PARSER_HOUR", "3"))
    while True:
        target = next_run(datetime.now(zone), hour)
        log.info("Следующий запуск парсера: %s", target.isoformat())
        while (remaining := target.timestamp() - time.time()) > 0:
            time.sleep(min(remaining, 30))
        try:
            run_once()
        except Exception:
            log.exception("Парсинг или импорт завершился ошибкой; следующий запуск завтра")


if __name__ == "__main__":
    main()
