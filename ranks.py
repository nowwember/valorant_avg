# -*- coding: utf-8 -*-
"""
ranks_avg.py — среднее звание команды VALORANT (5 игроков)

Функции:
- average_rank(ranks: list[str]) -> str

Особенности:
- Игнорирует регистр, лишние пробелы, дефисы и точки: "Д 1", "д-1", "diamond1" — валидно.
- Radiant по умолчанию включён в шкалу как максимум (выше Immortal 3).
  Можно отключить через флаг CLI --exclude-radiant, тогда Radiant считается как Immortal 3.

Числовая шкала (без пропусков):
Iron 1..3 (1..3), Bronze 1..3 (4..6), Silver 1..3 (7..9),
Gold 1..3 (10..12), Platinum 1..3 (13..15), Diamond 1..3 (16..18),
Ascendant 1..3 (19..21), Immortal 1..3 (22..24), Radiant (25).

Алгоритм:
1) Парсим 5 званий → числа.
2) Считаем среднее арифметическое (float).
3) Округляем к ближайшему числу (при .5 — вверх).
4) Маппим обратно в звание (русским названием). Radiant — без номера.

Doctest-примеры (запусти: python -m doctest -v ranks_avg.py):

>>> average_rank(["Алмаз 1", "Асцендант 1", "бронза 1", "серебро1", "золото 1"])
'Золото 2'
>>> average_rank(["д1","аск1","б1","с1","г1"])
'Золото 2'
>>> average_rank(["diamond 2","ascendant3","иммо1","gold3","platinum1"])
'Алмаз 2'
# Пример с Radiant: среднее не дотягивает до Radiant в линейной шкале, получается Иммортал 1
>>> average_rank(["Radiant","Immortal 3","Immortal 3","Ascendant 3","Diamond 3"])
'Иммортал 1'
"""

from __future__ import annotations
import argparse
import re
import sys
from typing import List, Optional, Tuple


ORDER = ["iron", "bronze", "silver", "gold", "platinum", "diamond", "ascendant", "immortal"]
RU_NAME = {
    "iron": "Железо",
    "bronze": "Бронза",
    "silver": "Серебро",
    "gold": "Золото",
    "platinum": "Платина",
    "diamond": "Алмаз",
    "ascendant": "Асцендант",
    "immortal": "Иммортал",
    "radiant": "Радиант",
}
MAX_WITHOUT_RADIANT = 24  # Immortal 3
RADIANT_VALUE = 25        # Radiant (если Radiant включен в шкалу)
DEFAULT_INCLUDE_RADIANT = True  # поведение по умолчанию


ALIASES = {
    "iron":      {"железо", "iron", "ж"},
    "bronze":    {"бронза", "bronze", "б"},
    "silver":    {"серебро", "silver", "с"},
    "gold":      {"золото", "голда", "gold", "г"},
    "platinum":  {"платина", "platinum", "п", "плат"},
    "diamond":   {"алмаз", "даймонд", "diamond", "д"},
    "ascendant": {"асцендант", "аскедант", "асцедант", "ascendant", "а", "аск", "асц", "asc"},
    "immortal":  {"иммортал", "immortal", "иммо", "им", "и"},
    "radiant":   {"радиант", "radiant", "рад", "r"},
}


ALIAS_TO_KEY = {}
for key, names in ALIASES.items():
    for nm in names:
        ALIAS_TO_KEY[nm] = key


def _clean_token(s: str) -> str:
    """Очистка токена: к нижнему регистру, убрать пробелы/дефисы/нижние подчеркивания/точки.
    Также нормализуем 'ё' -> 'е'.
    """
    s = s.strip().lower().replace("ё", "е")
    s = re.sub(r"[ \t\-\._]+", "", s)
    return s


def _split_cli_ranks_arg(arg: str) -> List[str]:
    """Разделяем строку аргумента --ranks на 5 значений.
    Сначала по запятым, при их отсутствии — по пробелам.
    """
    if "," in arg:
        parts = [p.strip() for p in arg.split(",")]
    else:
        parts = [p for p in arg.split() if p.strip()]
    return [p for p in parts if p]  


def _parse_rank_token(raw: str) -> Tuple[str, Optional[int], str]:
    """Парсит один вводимый токен ранга.

    Возвращает:
      (key, tier_or_none, ru_base_name)
      - key: один из ORDER или 'radiant'
      - tier_or_none: 1|2|3 или None (для Radiant / если цифры не было)
      - ru_base_name: русское базовое имя ранга (без цифры)

    Ошибки:
      ValueError с понятным текстом.
    """
    original = raw
    token = _clean_token(raw)

    m = re.search(r"([123])$", token)
    tier = int(m.group(1)) if m else None
    core = token[:-1] if m else token

    key = ALIAS_TO_KEY.get(core)
    if not key:
        raise ValueError(
            f"Не удалось распознать ранг: «{original}». "
            f"Поддерживаемые примеры: «алмаз 1», «diamond2», «г1», «ascendant 3», «иммо2», «radiant»."
        )

    ru_base = RU_NAME[key]

    if key != "radiant":
        if tier is None:
            raise ValueError(
                f"Для ранга «{ru_base}» требуется подуровень 1|2|3. "
                f"Например: «{ru_base.lower()} 1»."
            )
        if tier not in (1, 2, 3):
            raise ValueError(f"Неверный подуровень для «{ru_base}»: {tier}. Допустимо: 1, 2 или 3.")
    else:
        tier = None

    return key, tier, ru_base


def _rank_to_number(key: str, tier: Optional[int], include_radiant: bool) -> int:
    """Маппинг (ключ, подуровень) -> число шкалы."""
    if key == "radiant":
        return RADIANT_VALUE if include_radiant else MAX_WITHOUT_RADIANT
    i = ORDER.index(key)
    return i * 3 + int(tier)


def _number_to_ru(num: int, include_radiant: bool) -> str:
    """Обратный маппинг числа в русское человекочитаемое звание."""
    max_value = RADIANT_VALUE if include_radiant else MAX_WITHOUT_RADIANT
    if num < 1:
        num = 1
    if num > max_value:
        num = max_value

    if include_radiant and num == RADIANT_VALUE:
        return RU_NAME["radiant"]

    
    i = (num - 1) // 3          
    tier = (num - 1) % 3 + 1    
    key = ORDER[i]
    return f"{RU_NAME[key]} {tier}"


def _round_half_up(x: float) -> int:
    """Округление .5 вверх (к ближайшему целому)."""
    return int(x + 0.5)


def compute_average_details(ranks: List[str], include_radiant: bool = DEFAULT_INCLUDE_RADIANT):
    """Преобразует входные 5 званий в нормализованные RU-строки, числовые значения и среднее.

    Возвращает кортеж:
      (norm_ru_list: List[str], values: List[int], avg_value: float, final_ru: str)
    """
    if len(ranks) != 5:
        raise ValueError(f"Ожидалось ровно 5 званий, получено: {len(ranks)}.")

    parsed = []
    values = []
    norm_ru = [] 
    for raw in ranks:
        key, tier, ru_base = _parse_rank_token(raw)
        val = _rank_to_number(key, tier, include_radiant)
        values.append(val)
        if key == "radiant":
            norm_ru.append(RU_NAME["radiant"])
        else:
            norm_ru.append(f"{ru_base} {tier}")
        parsed.append((key, tier, val))

    avg_value = sum(values) / 5.0
    final_num = _round_half_up(avg_value)
    final_ru = _number_to_ru(final_num, include_radiant)
    return norm_ru, values, avg_value, final_ru


def average_rank(ranks: List[str]) -> str:
    """Возвращает итоговое среднее звание по 5 входным.

    Параметры:
      ranks: список из 5 строк (RU/EN, любые регистры, пробелы/дефисы допустимы).

    Возвращает:
      русскую строку, например: "Алмаз 1", "Иммортал 2" или "Радиант".

    См. doctest в верхнем docstring.
    """
    _, _, _, final_ru = compute_average_details(ranks, include_radiant=DEFAULT_INCLUDE_RADIANT)
    return final_ru


def _print_cli_report(norm_ru, values, avg_value, final_ru, include_radiant: bool):
    print("Нормализованные звания (RU):")
    print("  " + ", ".join(norm_ru))
    print("Числовые значения:")
    print("  " + ", ".join(str(v) for v in values))
    print(f"Среднее по шкале: {avg_value:.2f}")
    print(f"Итоговое звание: {final_ru}")
    if not include_radiant:
        print("(Примечание: Radiant отключен, трактуется как Immortal 3.)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Посчитать среднее звание команды VALORANT по 5 входным званиям."
    )
    parser.add_argument(
        "--ranks",
        type=str,
        help='Список из 5 званий через запятую или пробел, '
             'например: --ranks "д1, а1, б1, с1, г1" или --ranks "diamond2 ascendant3 иммо1 gold3 platinum1"',
    )
    g = parser.add_mutually_exclusive_group()
    g.add_argument(
        "--include-radiant",
        dest="include_radiant",
        action="store_true",
        help="Включить Radiant как верхнюю точку шкалы (по умолчанию включен).",
    )
    g.add_argument(
        "--exclude-radiant",
        dest="include_radiant",
        action="store_false",
        help="Отключить Radiant (Radiant трактуется как Immortal 3).",
    )
    parser.set_defaults(include_radiant=DEFAULT_INCLUDE_RADIANT)

    args = parser.parse_args(argv)

    if args.ranks:
        items = _split_cli_ranks_arg(args.ranks)
        if len(items) != 5:
            print(
                f"Ошибка: необходимо передать ровно 5 званий в --ranks, получено {len(items)}.",
                file=sys.stderr,
            )
            return 2
        try:
            norm_ru, values, avg_value, final_ru = compute_average_details(
                items, include_radiant=args.include_radiant
            )
        except ValueError as e:
            print(f"Ошибка: {e}", file=sys.stderr)
            return 2
        _print_cli_report(norm_ru, values, avg_value, final_ru, include_radiant=args.include_radiant)
        return 0

    print("Интерактивный режим. Введите 5 званий (RU/EN, можно сокращения). Примеры: д1, аск1, бронза 2, ascendant3, иммо1, radiant")
    inputs = []
    for i in range(1, 6):
        s = input(f"Звание {i}: ").strip()
        inputs.append(s)

    try:
        norm_ru, values, avg_value, final_ru = compute_average_details(
            inputs, include_radiant=args.include_radiant
        )
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 2

    _print_cli_report(norm_ru, values, avg_value, final_ru, include_radiant=args.include_radiant)
    return 0


if __name__ == "__main__":
    sys.exit(main())
