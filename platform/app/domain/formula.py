"""Безопасная формула: числа, имена, сравнения и несколько функций. Без произвольного кода."""

from __future__ import annotations

import math
import re

_TOKEN = re.compile(
    r"\s*(?:(\d+(?:[.,]\d+)?)|([A-Za-z_\u0400-\u04FF][\w.\u0400-\u04FF]*)|(<=|>=|==|!=)|(.))"
)
_FUNCS = {"ceil": math.ceil, "floor": math.floor, "abs": abs, "round": round, "min": min, "max": max, "sqrt": math.sqrt}


class FormulaError(Exception):
    pass


class MissingName(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(name)


def identifiers(formula: str) -> list[str]:
    names: list[str] = []
    for match in _TOKEN.finditer(formula or ""):
        name = match.group(2)
        if name and name not in _FUNCS and name not in {"and", "or"}:
            names.append(name)
    return names


def build_env(
    formula: str,
    input_keys: set[str],
    bindings: dict[str, str],
    site: dict,
    robot: dict,
) -> tuple[str, dict, str]:
    """ok с окружением, skip если величина объекта не задана, missing если нет характеристики."""
    env: dict = {}
    for name in identifiers(formula):
        bare = name.split(".", 1)[1] if name.startswith("robot.") else name
        if bare in input_keys:
            site_key = bindings.get(bare, "")
            if not site_key:
                return "skip", {}, bare
            raw = site.get(site_key)
            if raw is None or raw == "":
                return "skip", {}, bare
            number = _number(raw)
            if number is None:
                return "bad", {}, bare
            env[name] = number
            env[bare] = number
            continue
        raw = robot.get(bare)
        if raw is None or raw == "":
            return "missing", {}, bare
        number = _number(raw)
        if number is None:
            return "bad", {}, bare
        env[name] = number
        env[bare] = number
    return "ok", env, ""


_UNIT = re.compile(r"м[²2]|кв\.?\s*м|дб|мм|см|кг|час|мин", re.IGNORECASE)


def _number(raw: object) -> float | None:
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    compact = re.sub(r"(?<=\d)\s+(?=\d)", "", str(raw).strip()).replace(",", ".")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", compact) and _UNIT.search(compact) is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", compact)
    if match is None:
        return None
    return float(match.group(0))


def evaluate(formula: str, env: dict) -> bool | float:
    tokens = _tokens(formula)
    parser = _Parser(tokens, env)
    value = parser.parse()
    if parser.peek() is not None:
        raise FormulaError("в формуле лишний хвост")
    return value


def _tokens(formula: str) -> list[tuple[str, object]]:
    tokens: list[tuple[str, object]] = []
    pos = 0
    text = formula or ""
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None:
            raise FormulaError(f"не понял «{text[pos:pos + 12]}»")
        pos = match.end()
        if match.group(1) is not None:
            tokens.append(("num", float(match.group(1).replace(",", "."))))
        elif match.group(2) is not None:
            word = match.group(2)
            tokens.append(("word", word))
        elif match.group(3) is not None:
            tokens.append(("op", match.group(3)))
        else:
            symbol = match.group(4)
            if symbol.isspace():
                continue
            tokens.append(("sym", symbol))
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, object]], env: dict) -> None:
        self.tokens = tokens
        self.env = env
        self.index = 0

    def peek(self) -> tuple[str, object] | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def take(self) -> tuple[str, object]:
        token = self.peek()
        if token is None:
            raise FormulaError("формула оборвалась")
        self.index += 1
        return token

    def parse(self) -> bool | float:
        return self._or()

    def _or(self) -> bool | float:
        value = self._and()
        while self._word("or"):
            value = bool(value) or bool(self._and())
        return value

    def _and(self) -> bool | float:
        value = self._cmp()
        while self._word("and"):
            value = bool(value) and bool(self._cmp())
        return value

    def _cmp(self) -> bool | float:
        value = self._sum()
        token = self.peek()
        if token and token[0] == "op":
            op = str(self.take()[1])
            right = self._sum()
            return _compare(op, value, right)
        if token and token[0] == "sym" and token[1] in {"<", ">"}:
            op = str(self.take()[1])
            right = self._sum()
            return _compare(op, value, right)
        return value

    def _sum(self) -> bool | float:
        value = self._prod()
        while self._symbol("+") or self._ahead_symbol("-"):
            op = str(self.take()[1])
            right = self._prod()
            value = float(value) + float(right) if op == "+" else float(value) - float(right)
        return value

    def _ahead_symbol(self, symbol: str) -> bool:
        token = self.peek()
        return bool(token and token[0] == "sym" and token[1] == symbol)

    def _prod(self) -> bool | float:
        value = self._unary()
        while self._symbol("*") or self._symbol("/"):
            op = str(self.take()[1])
            right = self._unary()
            if op == "/" and float(right) == 0:
                raise FormulaError("деление на ноль")
            value = float(value) * float(right) if op == "*" else float(value) / float(right)
        return value

    def _unary(self) -> bool | float:
        if self._symbol("-"):
            self.take()
            return -float(self._unary())
        return self._primary()

    def _primary(self) -> bool | float:
        token = self.peek()
        if token is None:
            raise FormulaError("формула оборвалась")
        if token[0] == "num":
            self.take()
            return float(token[1])
        if token[0] == "word":
            name = str(self.take()[1])
            if name in _FUNCS and self._symbol("("):
                return self._call(name)
            if name not in self.env:
                raise MissingName(name)
            return self.env[name]
        if self._symbol("("):
            self.take()
            value = self.parse()
            if not self._symbol(")"):
                raise FormulaError("не закрыта скобка")
            self.take()
            return value
        raise FormulaError(f"не понял «{token[1]}»")

    def _call(self, name: str) -> bool | float:
        self.take()
        args: list[bool | float] = []
        if not self._symbol(")"):
            args.append(self.parse())
            while self._symbol(","):
                self.take()
                args.append(self.parse())
        if not self._symbol(")"):
            raise FormulaError("не закрыта скобка функции")
        self.take()
        try:
            return _FUNCS[name](*[float(item) for item in args])
        except TypeError as exc:
            raise FormulaError(f"{name} получила не те аргументы") from exc

    def _word(self, word: str) -> bool:
        token = self.peek()
        if token and token[0] == "word" and token[1] == word:
            self.take()
            return True
        return False

    def _symbol(self, symbol: str) -> bool:
        token = self.peek()
        return bool(token and token[0] == "sym" and token[1] == symbol)


def _compare(op: str, left: bool | float, right: bool | float) -> bool:
    a = float(left)
    b = float(right)
    if op == "<":
        return a < b
    if op == ">":
        return a > b
    if op == "<=":
        return a <= b
    if op == ">=":
        return a >= b
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    raise FormulaError(f"оператор {op} не поддерживается")
