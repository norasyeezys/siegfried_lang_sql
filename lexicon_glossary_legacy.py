#!/usr/bin/env python3
"""
Siegfried Lexicon — raw glossary dump.

Writes a plain text file with headword + English definition, one per line.
No conjugations. No notes. No source. No category. Just the word and its meaning.

Usage:
    python lexicon_glossary.py                              # ./siegfried_lang.sqlite -> ./glossary.txt
    python lexicon_glossary.py path/to/db.sqlite            # custom DB path
    python lexicon_glossary.py --out my_glossary.txt        # custom output path
    python lexicon_glossary.py --grouped                    # group by first letter with headers
    python lexicon_glossary.py --sep " :: "                 # custom separator (default " — ")
    python lexicon_glossary.py --pos                        # include part of speech
    python lexicon_glossary.py --ipa                        # include IPA pronunciation
    python lexicon_glossary.py --gender                     # include gender/class
    python lexicon_glossary.py --pos --ipa --gender         # everything (full dictionary line)

Stdlib only.
"""

import argparse
import sqlite3
import sys
import unicodedata


def sort_key(headword):
    """Sort headwords with vowel diacritics folded so â/ā sit with a,
    but þ/ð keep their own positions at the end."""
    if not headword:
        return ("\uffff",)
    out = []
    for ch in headword.lower():
        if ch in ("þ", "ð"):
            out.append(ch)
        else:
            decomp = unicodedata.normalize("NFD", ch)
            base = "".join(c for c in decomp if unicodedata.category(c) != "Mn")
            out.append(base or ch)
    return tuple(out)


def first_letter(headword):
    """Same folding rule as the rankings script."""
    if not headword:
        return None
    ch = headword[0].lower()
    if ch in ("þ", "ð"):
        return ch
    base = "".join(
        c for c in unicodedata.normalize("NFD", ch)
        if unicodedata.category(c) != "Mn"
    )
    if base:
        return base[0]
    else:
        return ch


def load(db_path):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("""
        SELECT w.headword, w.pos, w.ipa, w.gender_class, t.english
        FROM words w
        LEFT JOIN translations t ON t.word_id = w.id
    """)
    rows = cur.fetchall()
    con.close()
    return rows


def format_line(headword, pos, ipa, gender_class, english, sep,
                include_pos, include_ipa, include_gender):
    english = (english or "").strip() or "(no definition)"
    parts = [headword]

    # IPA goes right after headword, already wrapped in slashes in the DB
    if include_ipa and ipa and ipa.strip():
        parts.append(ipa.strip())

    # pos and gender_class merge into a single parenthesized group
    paren_bits = []
    if include_pos and pos and pos.strip():
        paren_bits.append(pos.strip())
    if include_gender and gender_class and gender_class.strip():
        paren_bits.append(gender_class.strip())
    if paren_bits:
        parts.append("(" + ", ".join(paren_bits) + ")")

    return " ".join(parts) + sep + english


def write_flat(rows, out_path, sep, include_pos, include_ipa, include_gender):
    rows_sorted = sorted(rows, key=lambda r: sort_key(r[0]))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Siegfried Lexicon \u2014 {} entries\n".format(len(rows_sorted)))
        f.write("# headword" + sep + "english\n")
        f.write("\n")
        for hw, pos, ipa, gc, eng in rows_sorted:
            f.write(format_line(hw, pos, ipa, gc, eng, sep,
                                include_pos, include_ipa, include_gender) + "\n")


def write_grouped(rows, out_path, sep, include_pos, include_ipa, include_gender):
    rows_sorted = sorted(rows, key=lambda r: sort_key(r[0]))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Siegfried Lexicon - " + str(len(rows_sorted)) + " entries\n")
        f.write("# headword" + sep + "english (grouped by first letter)\n")
        f.write("\n")
        current_letter = None
        for hw, pos, ipa, gc, eng in rows_sorted:
            L = first_letter(hw)
            if L != current_letter:
                if current_letter is not None:
                    f.write("\n")
                f.write("--- " + L.upper() + " ---\n\n")
                current_letter = L
            f.write(format_line(hw, pos, ipa, gc, eng, sep,
                                include_pos, include_ipa, include_gender) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "db", nargs="?", default="siegfried_lang.sqlite",
        help="path to the lexicon sqlite file (default: siegfried_lang.sqlite)"
    )
    parser.add_argument(
        "--out", default="glossary.txt",
        help="output text file path (default: glossary.txt)"
    )
    parser.add_argument(
        "--grouped", action="store_true",
        help="group entries under letter headers (--- A ---, --- B ---, etc.)"
    )
    parser.add_argument(
        "--sep", default=" — ",
        help="separator between headword and definition (default: ' — ')"
    )
    parser.add_argument(
        "--pos", action="store_true",
        help="include part of speech (noun, verb, adjective, etc.)"
    )
    parser.add_argument(
        "--ipa", action="store_true",
        help="include IPA pronunciation (between headword and definition)"
    )
    parser.add_argument(
        "--gender", action="store_true",
        help="include gender/class (masc, fem, neut, etc.)"
    )
    args = parser.parse_args()

    try:
        rows = load(args.db)
    except sqlite3.OperationalError as e:
        sys.stderr.write("Could not open " + str(args.db) + ": " + str(e) + "\n")
        sys.exit(1)

    if args.grouped:
        write_grouped(rows, args.out, args.sep, args.pos, args.ipa, args.gender)
    else:
        write_flat(rows, args.out, args.sep, args.pos, args.ipa, args.gender)

    sys.stdout.write("Wrote {} entries to {}\n".format(len(rows), args.out))


if __name__ == "__main__":
    main()
