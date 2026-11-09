#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Аудит протокола статусов (00-индекс, раздел «Статусы»).

Проверяет то, что можно проверить счётом; содержательные решения не трогает.
Код возврата: 0 — чисто, 1 — есть нарушения.

    python3 scripts/audit_status.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "scripts", "Игнор"}

SERVICE = ("00-", "01-", "02-", "03-")
STATUS_LINE = re.compile(r"^\*\*Статус:\*\*\s*(.+?)\.?$", re.M)
# разрешённые статусы и их формы
ALLOWED = ("принято", "рабочее", "сырое", "кандидат", "сценарий", "лор",
           "проверено", "отложено", "закрыто", "открыто")
PAREN = re.compile(r"\(([^()]{3,90})\)")
# слова, которые встречаются в скобках, но статусом не являются
NOT_STATUS = re.compile(
    r"см\.|ср\.|карточка|механика —|подробн|пример|условие \d|закон \d|"
    r"источник|формула|раздел|пункт|глав|термин\b|так зван|вернее|точнее",
    re.I)


def md_files():
    for p in sorted(ROOT.rglob("*.md")):
        if any(d in p.parts for d in SKIP_DIRS):
            continue
        if p.name == "README.md" or p.name.startswith(("склейка-", ".")):
            continue
        yield p


def main() -> int:
    problems = []
    notes = []
    statuses = 0
    for p in md_files():
        rel = p.relative_to(ROOT)
        text = p.read_text(encoding="utf-8")
        lines = text.split("\n")

        # 1. статус карточки: не больше одного, только под H1
        found = [m for m in STATUS_LINE.finditer(text)]
        statuses += len(found)
        if len(found) > 1:
            problems.append(f"{rel}: статус карточки стоит {len(found)} раза")
        for m in found:
            word = m.group(1).casefold()
            if not any(word.startswith(a) for a in ALLOWED):
                problems.append(
                    f"{rel}: статус «{m.group(1)}» вне списка (00-индекс)")

        # 2. пометки в скобках: только из списка
        for i, line in enumerate(lines, 1):
            for m in PAREN.finditer(line):
                body = m.group(1)
                if NOT_STATUS.search(body):
                    continue
                low = body.casefold()
                if any(low.startswith(a) for a in ALLOWED):
                    continue
                if re.match(r"^(гипотез|рабочая гипотез|рабочий термин|"
                            r"открытая развилк|закрыт[оа]?\b|открыт[оа]?\b|"
                            r"предел открыт)", low):
                    problems.append(
                        f"{rel}:{i}: пометка ({body}) не из списка статусов")

        # 3. двойной статус в одной записи 03
        if rel.name == "03-закрытые-вопросы.md":
            for entry in re.split(r"\n(?=- )", text):
                if "закрыт" in entry and re.search(r"Открыт[оа]?\b", entry):
                    head = entry.strip().split("\n")[0][:60]
                    problems.append(
                        f"{rel}: запись закрыта, но содержит «Открыто»: {head}")

        # 4. длина строки — только для файлов тем: индекс и глоссарий
        #    держат длинные строки карты по устройству
        if not rel.name.startswith(SERVICE):
            for i, line in enumerate(lines, 1):
                if len(line) > 80 and not line.startswith("|"):
                    notes.append(f"{rel}:{i}: строка {len(line)} символов > 80")

    print(f"проверено файлов: {len(list(md_files()))}")
    print(f"статусов карточек: {statuses}")
    if notes:
        print(f"предупреждений (длина строки): {len(notes)}")
        for x in notes[:20]:
            print("  ·", x)
    if problems:
        print(f"нарушений: {len(problems)}")
        for x in problems[:60]:
            print("  •", x)
        if len(problems) > 60:
            print(f"  … ещё {len(problems) - 60}")
        return 1
    print("нарушений нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
