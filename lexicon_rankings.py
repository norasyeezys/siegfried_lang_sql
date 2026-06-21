#!/usr/bin/env python3
"""
Siegfried Lexicon — letter, category, and intersection rankings.

Usage:
    python lexicon_rankings.py                          # uses ./siegfried_lang.sqlite
    python lexicon_rankings.py path/to/siegfried_lang.sqlite
    python lexicon_rankings.py --top 30                 # show top 30 intersections
    python lexicon_rankings.py --letter h               # deep-dive one letter
    python lexicon_rankings.py --diag                   # show fill diagnostics too

Letter rule: vowel diacritics fold (A/Â/Ā/Ä all → A).
             Thorn (þ) and eth (ð) stay distinct from D and T.

Category rule: aggregate of `category` + `category2`.

Stdlib only. No pip install needed.
"""

import argparse
import sqlite3
import sys
import unicodedata
from collections import Counter


def first_letter(headword):
    """Fold vowel diacritics, preserve thorn and eth as their own letters."""
    if not headword:
        return None
    ch = headword[0].lower()
    if ch in ("þ", "ð"):
        return ch
    base = "".join(
        c for c in unicodedata.normalize("NFD", ch)
        if unicodedata.category(c) != "Mn"
    )
    return base[0] if base else ch


def load(db_path):
    """Pull headword + both category columns. Returns list of (letter, cat1, cat2)."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT headword, category, category2 FROM words")
    rows = []
    for hw, c1, c2 in cur.fetchall():
        L = first_letter(hw)
        c1 = c1.strip().lower() if c1 and c1.strip() else None
        c2 = c2.strip().lower() if c2 and c2.strip() else None
        rows.append((L, c1, c2, hw))
    con.close()
    return rows


def tally(rows):
    letters = Counter()
    cats = Counter()
    cells = Counter()
    for L, c1, c2, _ in rows:
        if L:
            letters[L] += 1
        for c in (c1, c2):
            if c:
                cats[c] += 1
                if L:
                    cells[(L, c)] += 1
    return letters, cats, cells


def print_letters(letters, total):
    print("=== LETTER RANKING ===")
    print(f"  (þ/ð kept distinct; vowel diacritics folded — total {total})")
    print()
    for L, n in letters.most_common():
        bar = "█" * max(1, int(n / max(letters.values()) * 40))
        print(f"  {L.upper():>3}  {n:>4}  {bar}")
    print()


def print_cats(cats):
    print("=== CATEGORY RANKING (aggregate of category + category2) ===")
    print()
    total = sum(cats.values())
    maxn = max(cats.values()) if cats else 1
    for c, n in cats.most_common():
        bar = "█" * max(1, int(n / maxn * 40))
        print(f"  {n:>4}  {c:<22}  {bar}")
    print(f"  ----")
    print(f"  {total:>4}  total tags assigned across {len(cats)} categories")
    print()


def print_cells(cells, letters, cats, top_n):
    print(f"=== TOP {top_n} LETTER × CATEGORY INTERSECTIONS ===")
    print()
    for (L, cat), n in cells.most_common(top_n):
        pct_letter = n / letters[L] * 100
        pct_cat = n / cats[cat] * 100
        print(
            f"  {n:>3}  {L.upper():<2} × {cat:<22}  "
            f"({pct_letter:>4.1f}% of {L.upper()}-block, {pct_cat:>4.1f}% of {cat})"
        )
    print()


def print_letter_deep(letter, rows, cells, letters):
    L = letter.lower()
    if L not in letters:
        print(f"No entries found for letter '{letter.upper()}'.")
        return
    print(f"=== {letter.upper()}-BLOCK DEEP DIVE ({letters[L]} entries) ===")
    print()
    block_cats = sorted(
        [(cat, n) for (k, cat), n in cells.items() if k == L],
        key=lambda x: -x[1],
    )
    tagged = sum(n for _, n in block_cats)
    for cat, n in block_cats:
        print(f"  {n:>3}  {cat}")
    print(f"  ---")
    print(f"  {tagged} tags across {len(block_cats)} categories")
    print()
    # Headword list
    headwords = sorted(hw for L_row, _, _, hw in rows if L_row == L)
    print(f"=== {letter.upper()}-BLOCK HEADWORDS ===")
    print()
    cols = 6
    for i in range(0, len(headwords), cols):
        chunk = headwords[i:i + cols]
        print("  " + "  ".join(f"{w:<14}" for w in chunk))
    print()


def print_diag(rows):
    print("=== FILL DIAGNOSTICS ===")
    print()
    n = len(rows)
    c1_filled = sum(1 for _, c1, _, _ in rows if c1)
    c2_filled = sum(1 for _, _, c2, _ in rows if c2)
    both = sum(1 for _, c1, c2, _ in rows if c1 and c2)
    neither = sum(1 for _, c1, c2, _ in rows if not c1 and not c2)
    print(f"  primary category filled: {c1_filled}/{n}")
    print(f"  category2 filled:        {c2_filled}/{n}")
    print(f"  both filled:             {both}/{n}")
    print(f"  neither filled:          {neither}/{n}")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "db", nargs="?", default="siegfried_lang.sqlite",
        help="path to the lexicon sqlite file (default: siegfried_lang.sqlite)"
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="how many letter × category intersections to show (default 20)"
    )
    parser.add_argument(
        "--letter", type=str, default=None,
        help="deep-dive one letter (shows category breakdown + headword list)"
    )
    parser.add_argument(
        "--diag", action="store_true",
        help="also print fill diagnostics (uncategorized counts)"
    )
    args = parser.parse_args()

    try:
        rows = load(args.db)
    except sqlite3.OperationalError as e:
        print(f"Could not open {args.db}: {e}", file=sys.stderr)
        sys.exit(1)

    total = len(rows)
    letters, cats, cells = tally(rows)

    print()
    print(f"TOTAL ENTRIES: {total}")
    print()
    print_letters(letters, total)
    print_cats(cats)
    print_cells(cells, letters, cats, args.top)

    if args.letter:
        print_letter_deep(args.letter, rows, cells, letters)

    if args.diag:
        print_diag(rows)


if __name__ == "__main__":
    main()
