"""Сжатый итог подбора. Считает успех, пустой результат и роботов с пометкой, в базу не ходит."""

from __future__ import annotations

_NOTE_CODES = {
    "robot_attribute_missing",
    "catalog_attribute_ambiguous",
    "optional_attribute_missing",
}
_BLOCK_CODES = {
    "robot_attribute_missing",
    "catalog_attribute_ambiguous",
}
_SKIP_SITE = ("email", "phone", "password", "login", "fio", "owner", "name")


def public_params(site: dict | None) -> list[dict]:
    """Параметры площадки, которые человек ввёл сам. Почту, телефон и служебные ключи не берём."""
    rows: list[dict] = []
    if not isinstance(site, dict):
        return rows
    for key, value in site.items():
        if len(rows) >= 40:
            break
        name = str(key).strip()
        if not name or name.startswith("__"):
            continue
        folded = name.casefold()
        if any(word in folded for word in _SKIP_SITE):
            continue
        clean = _scalar(value)
        if clean is None:
            continue
        rows.append({"key": name[:80], "label": name[:80], "value": clean})
    return rows


def participation(linked: bool, on_object: bool, gaps: list[dict]) -> tuple[str, str]:
    """in: карточки хватает. note: робот в подборе, но с пометкой. out: в подбор не попадает."""
    if not linked:
        return "out", "Не указано, какие работы выполняет робот. Пока работы нет, подбор его не видит."
    if not on_object:
        return "out", "Работы робота не стоят ни на одном типе площадки. В подбор он не попадает."
    blocking = [item for item in gaps if item.get("used_in") == "условие"]
    if blocking:
        names = _join(item.get("label") or item.get("key") for item in blocking)
        return "out", f"Не заполнены характеристики, без которых подбор не проверяет робота: {names}."
    if gaps:
        names = _join(item.get("label") or item.get("key") for item in gaps)
        return "note", f"Попадает в подбор с пометкой, потому что не хватает: {names}."
    return "in", "Карточки хватает, робот участвует в подборе."


def digest_match(groups: list | None) -> dict:
    """Успех, если хотя бы один робот получил «Подходит». Иначе подбор пустой, даже если кто-то попал в «Уточнить»."""
    processes = []
    noted = []
    blocked = []
    passed = []
    passed_total = 0
    for group in groups or []:
        hits = group.get("hits") or []
        ok_hits = []
        unknown_hits = []
        fail_hits = []
        for hit in hits:
            verdict = hit.get("verdict")
            if verdict == "pass":
                ok_hits.append(hit)
            elif verdict == "unknown":
                unknown_hits.append(hit)
            elif verdict == "fail":
                fail_hits.append(hit)
        passed_total += len(ok_hits)
        reasons = _process_reasons(unknown_hits + fail_hits)
        code = str(group.get("process_code") or "")
        title = str(group.get("process_name") or code)
        for hit in ok_hits:
            passed.append(_robot_ref(hit, code, title))
            missing = _missing(hit)
            if hit.get("applicability") == "conditional" or missing:
                noted.append({**_robot_ref(hit, code, title), "missing": missing[:8]})
        for hit in unknown_hits:
            noted.append({**_robot_ref(hit, code, title), "missing": _missing(hit)[:8]})
        for hit in fail_hits:
            gap_reasons = _block_reasons(hit)
            if gap_reasons:
                blocked.append({**_robot_ref(hit, code, title), "reasons": gap_reasons[:6]})
        processes.append({
            "code": code,
            "name": title,
            "passed": len(ok_hits),
            "noted": len(unknown_hits),
            "failed": len(fail_hits),
            "empty": not ok_hits and not unknown_hits,
            "reasons": reasons,
        })
    outcome = "success" if passed_total else "empty"
    return {
        "outcome": outcome,
        "passed_count": passed_total,
        "shown_count": passed_total + len(noted),
        "processes": processes,
        "passed": _trim(passed, 80),
        "noted": _trim(noted, 40),
        "blocked": _trim(blocked, 40),
        "reasons": _outcome_reasons(outcome, processes, noted, blocked),
    }


def count_reasons(chunks: list[list[str]]) -> list[dict]:
    bag: dict[str, int] = {}
    for chunk in chunks:
        for text in chunk:
            clean = str(text).strip()
            if clean:
                bag[clean] = bag.get(clean, 0) + 1
    ranked = sorted(bag.items(), key=lambda pair: (-pair[1], pair[0]))
    return [{"text": text, "count": count} for text, count in ranked[:12]]


def _outcome_reasons(outcome: str, processes: list, noted: list, blocked: list) -> list[str]:
    found: list[str] = []
    if outcome == "empty":
        for process in processes:
            for text in process["reasons"]:
                _push(found, text)
    for item in noted:
        for text in item.get("missing") or []:
            _push(found, text)
    for item in blocked:
        for text in item.get("reasons") or []:
            _push(found, text)
    return found[:12]


def _process_reasons(hits: list) -> list[str]:
    found: list[str] = []
    for hit in hits:
        for item in (hit.get("significant_reasons") or hit.get("reasons") or []):
            if not isinstance(item, dict):
                continue
            _push(found, item.get("message"))
            if len(found) >= 6:
                return found
    return found


def _missing(hit: dict) -> list[str]:
    found: list[str] = []
    bags = list(hit.get("reasons") or []) + list(hit.get("clarifications") or [])
    for item in bags:
        if not isinstance(item, dict) or item.get("code") not in _NOTE_CODES:
            continue
        _push(found, item.get("message") or item.get("field"))
    return found


def _block_reasons(hit: dict) -> list[str]:
    found: list[str] = []
    for item in hit.get("reasons") or []:
        if not isinstance(item, dict) or item.get("code") not in _BLOCK_CODES:
            continue
        _push(found, item.get("message") or item.get("field"))
    return found


def _robot_ref(hit: dict, code: str, title: str) -> dict:
    return {
        "slug": str(hit.get("slug") or ""),
        "name": str(hit.get("name") or "Робот"),
        "process_code": code,
        "process": title,
        "manufacturer": "",
    }


def _scalar(value):
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text[:180] if text else None
    return None


def _join(items) -> str:
    names = []
    for item in items:
        text = str(item or "").strip()
        if text and text not in names:
            names.append(text)
    return ", ".join(names[:8]) or "нужные характеристики"


def _push(found: list[str], value) -> None:
    text = str(value or "").strip()
    if text and text not in found:
        found.append(text)


def _trim(rows: list, limit: int) -> list:
    return rows[:limit]
