#!/usr/bin/env python3
"""Verify the fixed post-copy reference against owner-supplied Git sources."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "skills/content-candidate-generator/references/post-copy-style.md"

SOURCES = {
    "natal": (
        "e815d1acf11b78a2c5c40c4ad73f986e3d346792",
        "natal_landing/index.html",
        "b6dea7b8fec506edb087d5063c7d9ebfb47bc03051317a59ac73d197d7c584e2",
    ),
    "sesh_landing": (
        "e815d1acf11b78a2c5c40c4ad73f986e3d346792",
        "sesh/index.html",
        "8dd522bbee2e3f838f98ecec31c2e89ff49692f3564b54070638df6cd077f245",
    ),
    "sesh_posts": (
        "e815d1acf11b78a2c5c40c4ad73f986e3d346792",
        "sesh/instagram-ad-poster-scripts.md",
        "69ea264f1c7bcf7ed62c495a3d8da5f91ed03f3a2ff3104ea595fd0c717f9efc",
    ),
    "ofc": (
        "73062eee4c4af4ec5c876fa2c4e3645325b4659f",
        "components/LandingPage.tsx",
        "599bfca6e21a065f16688e5a9a0a50b76fbe2d99c387b5bdf1383ea5efd28dce",
    ),
    "sober_app": (
        "7794e2eb63b800cf52794880282ede176f18071b",
        "src/App.tsx",
        "8b9000417f764a85ce649a5e6d8ccb52de732d7e460dceabb75188c51c5bbc10",
    ),
    "sober_modal": (
        "7794e2eb63b800cf52794880282ede176f18071b",
        "src/components/SkipDrinkModal.tsx",
        "3e863e9e9276f77dfece6afa269768efad15df15a741d353aa5f4e03c1425d8a",
    ),
}

ANCHORS = (
    ("natal", "Система, що повертає клієнтів. Поки ви займаєтесь роботою.", ("Система, що повертає клієнтів. Поки ви займаєтесь роботою.",)),
    ("natal", "Вона не повернулась. Natal знав це за тиждень до того.", ("Вона не повернулась. Natal знав це за тиждень до того.",)),
    ("natal", "О 23:00 клієнт вже записаний. Без вас.", ("О 23:00 клієнт вже записаний. Без вас.",)),
    ("natal", "Три точки — один дашборд. Нуль дзвінків між ними.", ("Три точки — один дашборд. Нуль дзвінків між ними.",)),
    ("natal", "Скільки ви заробили — і скільки могли б.", ("Скільки ви заробили — і скільки могли б.",)),
    ("sesh_posts", "Тобі треба просто прийти.", ("Тобі треба просто прийти.",)),
    ("sesh_posts", "Людей, формат і місце підберемо ми.", ("Людей, формат і місце підберемо ми.",)),
    ("sesh_posts", "5 незнайомців. 1 стіл.", ("5 незнайомців. 1 стіл.",)),
    ("sesh_posts", "Без свайпів і чатів.", ("Без свайпів і чатів.",)),
    ("sesh_posts", "Не треба вигадувати ідеальне біо, вести довгі переписки або чекати, поки хтось організує вечір. Sesh збирає 5 людей за одним столом. Ти бронюєш місце в Telegram і приходиш.", ("Не треба вигадувати ідеальне біо, вести довгі переписки або чекати, поки хтось організує вечір. Sesh збирає 5 людей за одним столом. Ти бронюєш місце в Telegram і приходиш.",)),
    ("sesh_landing", "300 грн · повернемо якщо не зберемось", ("300 грн · повернемо якщо не зберемось",)),
    ("ofc", "Не соцмережа. Не застосунок для знайомств.", ("Не соцмережа. Не застосунок для знайомств.",)),
    ("ofc", "Позначаєтесь відкритими до кави. Без імен, фото чи точної локації.", ("Позначаєтесь відкритими до кави. Без імен, фото чи точної локації.",)),
    ("ofc", "Лише після обопільної згоди відкривається чат і контакти.", ("Лише після обопільної згоди відкривається чат і контакти.",)),
    ("ofc", "Ідея з’явилася дуже просто. Одного разу я намагався домовитися з колегою піти на каву. Наші графіки не збіглися. Я написав іншому — знову не вийшло. Вже в кафе, дивлячись що більшість людей сидять самі: xтось працює, хтось читає, хтось просто п’є каву. І я подумав: а чому лише колеги? Тут багато цікавих людей, було б добре їм усім відправити повідомлення, що я відкритий до нетворкінгу.", ("Ідея з’явилася дуже просто. Одного разу я намагався домовитися з колегою піти на каву. Наші графіки не збіглися. Я написав іншому — знову не вийшло. Вже в кафе, дивлячись що більшість людей сидять самі: xтось працює, хтось читає, хтось просто п’є каву. І я подумав: а чому лише колеги? Тут багато цікавих людей, було б добре їм усім відправити повідомлення, що я відкритий до нетворкінгу.",)),
    ("ofc", "Без планування. Без незручних підходів. За інтересами. І тільки за взаємною згодою.", ("Без планування. Без незручних підходів. За інтересами. І тільки за взаємною згодою.",)),
    ("sober_app", "Your first sober win starts here", ("Your first sober win", "starts here")),
    ("sober_app", "Every skip adds up: calories avoided, money saved, energy regained.", ("Every skip adds up: calories avoided, money saved, energy regained.",)),
    ("sober_app", "Track Your Wins, Not Your Slips", ("Track Your Wins, Not Your Slips",)),
    ("sober_app", "You don't just count drinks consumed (that's depressing). You mark the ones you could have had but didn't. This flips the frame from loss → gain.", ("You don't just count drinks consumed", "(that's depressing)", "You mark the ones you", "could have had but didn't", "This flips the frame from loss → gain.")),
    ("sober_modal", "Amazing Choice! Here's what you just gained by skipping:", ("Amazing Choice!", "Here's what you just gained by skipping:")),
)


def git_blob(repository: Path, commit: str, source_path: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repository), "show", f"{commit}:{source_path}"],
    )


def main() -> int:
    projects = ROOT.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--natal-repo", type=Path, default=projects / "natal")
    parser.add_argument("--ofc-repo", type=Path, default=projects / "ofc_landing")
    parser.add_argument("--soberwins-repo", type=Path, default=projects / "soberwins")
    args = parser.parse_args()
    repositories = {
        "natal": args.natal_repo, "sesh_landing": args.natal_repo,
        "sesh_posts": args.natal_repo, "ofc": args.ofc_repo,
        "sober_app": args.soberwins_repo, "sober_modal": args.soberwins_repo,
    }
    blobs: dict[str, str] = {}
    for key, (commit, source_path, expected_digest) in SOURCES.items():
        raw = git_blob(repositories[key], commit, source_path)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_digest:
            raise RuntimeError(f"source digest mismatch: {key}")
        blobs[key] = raw.decode("utf-8")

    reference = REFERENCE.read_text(encoding="utf-8")
    declared = REFERENCE.with_suffix(".sha256").read_text(encoding="utf-8").strip()
    if hashlib.sha256(reference.encode()).hexdigest() != declared:
        raise RuntimeError("post-copy-style reference digest mismatch")
    for source_key, anchor, source_parts in ANCHORS:
        if anchor not in reference:
            raise RuntimeError(f"reference is missing anchor: {anchor}")
        if any(part not in blobs[source_key] for part in source_parts):
            raise RuntimeError(f"pinned source is missing anchor: {anchor}")
    print(f"Verified {len(ANCHORS)} post-copy anchors across {len(SOURCES)} pinned source files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
