#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Склейка архива: все md-файлы в один файл или по папкам (по группам).

Универсально: новые файлы и новые папки подхватываются сами —
просто пересобери скриптом, и всё подтянется.

Полная сборка живёт в README.md в корне архива: её видно в git (и на GitHub),
и хук пересобирает её перед каждым коммитом. Всё, что в README выше маркера, —
ручная шапка, она сохраняется; ниже маркера — сборка (генерируется, руками не
правится).

Примеры:
    python3 scripts/merge.py                 # и групповые склейки, и полная сборка (README.md)
    python3 scripts/merge.py --mode groups   # только по папкам: Игнор/склейки/склейка-*.md
    python3 scripts/merge.py --mode all      # только полная сборка: README.md в корне
    python3 scripts/merge.py --dry-run       # только показать план, ничего не писать
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # корень архива (родитель scripts/)
# Склейки по группам — рабочая выдача, не архив: кладём в Игнор (он в .gitignore
# и в сборку не попадает), чтобы в scripts/ не копился мусор.
OUT_DIR = ROOT / "Игнор" / "склейки"
README_NAME = "README.md"                    # полная сборка — в корне: читается в git и на GitHub

# Папки, вынесенные из архива: в сборку не попадают (в .gitignore, живут локально).
EXCLUDED_DIRS = {"Игнор"}

# Порядок групп в сборке — как объявлено в шапке README и в «Порядке чтения»
# (00-индекс): материальное → архитектурное → погружения. Прочие папки — после.
GROUP_ORDER = ("Хард", "НАД", "ПОД")

# Латиница в Unicode идёт раньше кириллицы, из-за чего «НАД/ASI/…» прыгал в
# начало группы. Для сортировки только — читаем ASI как АСИ.
SORT_ALIAS = {"asi": "аси"}

# Служебные файлы в корне: идут первыми, по номеру.
SERVICE_RE = re.compile(r"^\d\d-")


def sort_name(name: str) -> str:
    return SORT_ALIAS.get(name.casefold(), name).casefold()


def _is_archived(name: str) -> bool:
    return name.startswith(("склейка-", ".")) or not name.endswith(".md")


def _tree(d: Path, skip: set, out: list) -> None:
    """Порядок внутри папки: свод (файл с именем папки) — первым, дальше по
    алфавиту, подпапки раскрываются на своём месте и так же внутри себя."""
    files, dirs = [], []
    for p in d.iterdir():
        if p.is_dir():
            if p.name not in skip:
                dirs.append(p)
        elif not _is_archived(p.name):
            files.append(p)
    svod = next((p for p in files if p.stem == d.name), None)
    if svod is not None:
        out.append(svod)
        files.remove(svod)
    items = [(sort_name(p.stem if p.is_file() else p.name), p) for p in files + dirs]
    for _, p in sorted(items, key=lambda t: (t[0], t[1].is_dir())):
        if p.is_file():
            out.append(p)
        else:
            _tree(p, skip, out)

MARKER = "<!-- ниже — автоматическая сборка архива (scripts/merge.py); не редактировать вручную -->"

DEFAULT_HEAD = (
    "# Архив\n\n"
    "Полная сборка архива одним текстом: все темы по порядку\n"
    "(служебные 00/01/02/03 — первыми). Обновляется при каждом коммите.\n"
)


def collect(root: Path, out: Path, exclude: set) -> list:
    """Все md-файлы архива в порядке чтения: служебные → группы → прочее.

    Служебные (00/01/02/03) первыми, затем группы в GROUP_ORDER и прочие папки
    по алфавиту, в конце — md-файлы корня. Внутри папки свод идёт первым,
    остальное по алфавиту, подпапки раскрываются на своём месте."""
    root, out = root.resolve(), out.resolve()
    skip = {".git", "scripts", out.name} | EXCLUDED_DIRS
    excl = {p.resolve() for p in exclude}

    root_files, root_dirs = [], []
    for p in root.iterdir():
        if p.is_dir():
            if p.name not in skip:
                root_dirs.append(p)
        elif not _is_archived(p.name) and p.resolve() not in excl:
            root_files.append(p)

    files = sorted((p for p in root_files if SERVICE_RE.match(p.name)),
                   key=lambda p: p.name)
    dirs = sorted(root_dirs, key=lambda p: (
        GROUP_ORDER.index(p.name) if p.name in GROUP_ORDER else len(GROUP_ORDER),
        sort_name(p.name)))
    for d in dirs:
        _tree(d, skip, files)
    files.extend(sorted((p for p in root_files if not SERVICE_RE.match(p.name)),
                        key=lambda p: sort_name(p.stem)))
    return files


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8").rstrip("\n") + "\n"


def head_for(readme: Path) -> str:
    """Ручная шапка README: всё выше маркера. Нет файла или маркера — шапка по умолчанию."""
    if readme.exists():
        lines = readme.read_text(encoding="utf-8").split("\n")
        for i, ln in enumerate(lines):
            if ln.strip() == MARKER:
                head = "\n".join(lines[:i]).rstrip()
                if head:
                    return head
                break
    return DEFAULT_HEAD.rstrip()


def glue(files: list, root: Path, title: str, note: str) -> str:
    head = (
        "<!-- Сгенерировано scripts/merge.py. Не редактировать — пересобери скриптом. -->\n"
        f"# {title}\n\n{note}\n"
    )
    parts = [head]
    for p in files:
        rel = p.relative_to(root)
        parts.append(f"---\n\n## {rel}\n\n{read(p)}")
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Склейка архива в один файл или по папкам.")
    ap.add_argument("--mode", choices=("groups", "all", "both"), default="both",
                    help="groups — по папкам, all — полная сборка в README.md, both — оба (по умолчанию)")
    ap.add_argument("--root", type=Path, default=None,
                    help="корень архива (по умолчанию — родитель папки scripts/)")
    ap.add_argument("--out", type=Path, default=None,
                    help="куда складывать групповые склейки (по умолчанию — Игнор/склейки/)")
    ap.add_argument("--dry-run", action="store_true",
                    help="только показать план, ничего не писать")
    args = ap.parse_args()

    root = (args.root or ROOT).resolve()
    out = (args.out or OUT_DIR).resolve()
    out.mkdir(parents=True, exist_ok=True)
    readme = root / README_NAME

    files = collect(root, out, exclude={readme})
    if not files:
        print("Нет md-файлов для склейки.", file=sys.stderr)
        return 1

    targets = []  # (куда писать, текст, сколько файлов)

    if args.mode in ("groups", "both"):
        by_dir = {}
        for p in files:
            parts = p.relative_to(root).parts
            if len(parts) >= 2:
                by_dir.setdefault(parts[0], []).append(p)

        for top in sorted(by_dir):
            # порядок уже задан collect(): свод первым, подпапки на своём месте
            gf = by_dir[top]
            text = glue(gf, root, f"Папка «{top}»",
                        f"Склейка папки «{top}»: {len(gf)} файл(ов). "
                        f"Служебные в корне (00/01/02/03) — только в «{README_NAME}».")
            targets.append((out / f"склейка-{top}.md", text, len(gf)))

    if args.mode in ("all", "both"):
        body = glue(files, root, "Архив целиком",
                    f"Все {len(files)} md-файлов архива; служебные (00/01/02/03) идут первыми.")
        text = head_for(readme) + "\n\n" + MARKER + "\n\n" + body
        targets.append((readme, text, len(files)))

    for dst, text, count in targets:
        prefix = "[dry-run] " if args.dry_run else ""
        print(f"{prefix}{dst} — {count} файл(ов), {len(text)} симв.")
        if not args.dry_run:
            dst.write_text(text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
