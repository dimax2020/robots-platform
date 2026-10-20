"""Итог подбора без базы: пустой результат, пометка и готовность карточки."""

from app.domain.match_digest import count_reasons, digest_match, participation, public_params


def _hit(verdict, **extra):
    row = {"verdict": verdict, "slug": "h1500", "name": "Ronavi H1500", "reasons": [], "clarifications": []}
    row.update(extra)
    return row


def test_empty_match_keeps_site_reason_and_missing_robot():
    summary = digest_match([{
        "process_code": "pallet",
        "process_name": "Перевозка паллет",
        "hits": [_hit(
            "unknown",
            reasons=[{"code": "robot_attribute_missing", "message": "Нет «Грузоподъёмность»", "severity": "unknown"}],
            significant_reasons=[{"code": "robot_attribute_missing", "message": "Нет «Грузоподъёмность»"}],
        )],
    }])
    assert summary["outcome"] == "empty"
    assert summary["passed_count"] == 0
    assert summary["noted"][0]["missing"] == ["Нет «Грузоподъёмность»"]
    assert "Нет «Грузоподъёмность»" in summary["reasons"]
    params = public_params({"height_m": 8, "email": "a@b.c", "__tasks": [], "note": "  "})
    assert params == [{"key": "height_m", "label": "height_m", "value": 8}]


def test_pass_with_note_is_success():
    summary = digest_match([{
        "process_code": "clean",
        "process_name": "Уборка",
        "hits": [
            _hit("pass", applicability="conditional", clarifications=[
                {"code": "optional_attribute_missing", "message": "Уточнить у вендора: Шум"},
            ]),
            _hit("fail", slug="other", name="Чужой", reasons=[
                {"code": "technical_constraint", "message": "Шум выше нормы", "severity": "fail"},
            ]),
        ],
    }])
    assert summary["outcome"] == "success"
    assert summary["noted"][0]["missing"] == ["Уточнить у вендора: Шум"]
    assert summary["blocked"] == []


def test_fail_without_attribute_is_blocked():
    summary = digest_match([{
        "process_code": "pick",
        "process_name": "Отбор",
        "hits": [_hit("fail", reasons=[{"code": "robot_attribute_missing", "message": "нет «Скорость»"}])],
    }])
    assert summary["outcome"] == "empty"
    assert summary["blocked"][0]["reasons"] == ["нет «Скорость»"]


def test_participation_states():
    assert participation(False, False, [])[0] == "out"
    assert participation(True, False, [])[0] == "out"
    state, text = participation(True, True, [{"label": "Груз", "used_in": "условие"}])
    assert state == "out"
    assert "Груз" in text
    state, text = participation(True, True, [{"label": "Цена", "used_in": "экономика"}])
    assert state == "note"
    assert "пометкой" in text
    assert participation(True, True, [])[0] == "in"


def test_reason_counts_drop_empty():
    assert count_reasons([["Нет цены", ""], ["Нет цены"]]) == [{"text": "Нет цены", "count": 2}]
