#!/usr/bin/env python3
"""
Generate a multi-page static site from siegfried_lang.sqlite.

    python3 generate_lexicon_site.py [db_path] [output_dir]

Defaults: siegfried_lang.sqlite -> site/

Layout produced:
    index.html          — landing page with links to the three sections
    phonemes.html       — phoneme inventory
    words.html          — letter grid
    words-<L>.html      — one page per letter (A collects a/ā/â, etc.)
    sentences.html      — all sentences, every word hyperlinked
    w-<N>.html          — per-word page. N is assigned in alphabetical order
                          across the whole lexicon (independent of DB id).
    style.css           — shared minimalist stylesheet.
"""
import sqlite3
import html
import re
import sys
import unicodedata
from pathlib import Path
from datetime import datetime


# ---------- Ripuarian alphabet ----------
# Order fixed by hand. Short and long vowels share a bucket
# (A collects a/ā/â, E collects e/ē/ê, etc.). Þ sits between T and U.
LETTERS = [
    ('A', 'A Â/Ā'),
    ('B', 'B'),
    ('D', 'D'),
    ('E', 'E Ê/Ē'),
    ('F', 'F'),
    ('G', 'G'),
    ('H', 'H'),
    ('I', 'I Î/Ī'),
    ('J', 'J'),
    ('K', 'K'),
    ('L', 'L'),
    ('M', 'M'),
    ('N', 'N'),
    ('O', 'O Ô/Ō'),
    ('P', 'P'),
    ('R', 'R'),
    ('S', 'S'),
    ('T', 'T'),
    ('Þ', 'Þ'),
    ('U', 'U Û/Ū'),
    ('W', 'W'),
]
LETTER_ORDER = {L: i for i, (L, _) in enumerate(LETTERS)}


def strip_marks(s):
    """Drop combining marks — ā→a, ê→e, etc. Þ has no marks so is unchanged."""
    return ''.join(ch for ch in unicodedata.normalize('NFD', s)
                   if unicodedata.category(ch) != 'Mn')


def bucket_letter(headword):
    """Return the letter bucket ('A', 'Þ', ...) for a headword."""
    if not headword:
        return None
    first = strip_marks(headword)[0].upper()
    if first not in LETTER_ORDER:
        # any headword that starts with something outside the alphabet ends up
        # in a catch-all bucket at the end — nothing in the current db, but
        # keeps future imports from crashing
        return '?'
    return first


def sort_key(headword):
    """
    Custom collation: first letter by LETTER_ORDER, then rest by stripped
    lowercase, with diacritic-bearing chars sorting AFTER their bare form
    at the same position (so 'a' < 'ā' < 'â' — deterministic, stable).
    """
    if not headword:
        return (999,)
    stripped = strip_marks(headword).lower()
    key = []
    for i, ch in enumerate(headword):
        base = strip_marks(ch).lower()
        primary = LETTER_ORDER.get(base.upper(), 99)
        # secondary: was this character originally diacritic-bearing
        secondary = 0 if ch == base else 1
        key.append((primary, secondary, ch))
    return tuple(key)


# ---------- paradigm-column declarations (same as single-file generator) ----------

PERSON_ROWS = [
    ('1sg', '1sg'), ('2sg', '2sg'), ('3sg', '3sg'),
    ('1pl', '1pl'), ('2pl', '2pl'), ('3pl', '3pl'),
]
MOOD_TENSE_COLS = [
    ('pres',      'pres'),
    ('pres sbjv', 'pres_sbjv'),
    ('past',      'past'),
    ('past sbjv', 'past_sbjv'),
]
ADJ_ROWS = [('nom', 'nom'), ('acc', 'acc')]
ADJ_COLS = [('masc', 'masc'), ('fem', 'fem'), ('neut', 'neut'), ('pl', 'pl')]


# ---------- data loading ----------

def load_words(conn):
    cur = conn.execute("SELECT * FROM v_word_card")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def load_sentences(conn):
    cur = conn.execute(
        "SELECT id, frankish, english, source FROM sentences ORDER BY id"
    )
    return [dict(id=r[0], frankish=r[1], english=r[2], source=r[3])
            for r in cur.fetchall()]


def load_sentence_words(conn):
    """Return {sentence_id: [(position, db_word_id, surface_form), ...]} ordered by position."""
    cur = conn.execute("""
        SELECT sentence_id, position, word_id, surface_form
        FROM sentence_words
        ORDER BY sentence_id, position
    """)
    out = {}
    for sid, pos, wid, surf in cur.fetchall():
        out.setdefault(sid, []).append((pos, wid, surf))
    return out


def load_phonemes(conn):
    cur = conn.execute(
        "SELECT symbol, type, description, latin, runes, example_word, notes "
        "FROM phonemes ORDER BY type, id"
    )
    return cur.fetchall()


# ---------- id assignment ----------

def assign_new_ids(words):
    """Sort by headword under the Ripuarian collation, then hand out sequential
    ids starting at 1. Sigifrið has db-id 1 but almost certainly does NOT get
    new-id 1 — 'sigifrīþ' lives deep in the S bucket."""
    ordered = sorted(words, key=lambda w: sort_key(w.get('headword') or ''))
    db_to_new = {}
    new_to_word = {}
    for i, w in enumerate(ordered, start=1):
        w['new_id'] = i
        w['filename'] = f'w-{i}.html'
        db_to_new[w['id']] = i
        new_to_word[i] = w
    return ordered, db_to_new, new_to_word


# ---------- html helpers ----------

def esc(v):
    if v is None or v == '':
        return ''
    return html.escape(str(v))


def link_to_word(w):
    """Anchor to a word page, showing its headword."""
    return f'<a class="w" href="{w["filename"]}">{esc(w["headword"])}</a>'


# ---------- shared page shell ----------

CSS = """\
:root {
  --text: #1a1a1a;
  --muted: #6a6a6a;
  --line: #d8d8d8;
  --bg: #ffffff;
  --link: #1b4a8a;
  --link-hover: #0d2f5c;
  --accent: #7a2b0a;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  color: var(--text);
  background: var(--bg);
}
.wrap {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
}
nav.top {
  display: flex;
  gap: 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--line);
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
}
nav.top a { color: var(--muted); text-decoration: none; }
nav.top a:hover { color: var(--text); }
nav.top a.here { color: var(--text); font-weight: 600; }
h1 { font-size: 1.6rem; margin: 0 0 0.25rem; font-weight: 600; }
h2 { font-size: 1.15rem; margin: 1.75rem 0 0.5rem; font-weight: 600; }
h3 { font-size: 1rem; margin: 1.25rem 0 0.4rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.72rem; }
.sub { color: var(--muted); font-size: 0.9rem; margin-bottom: 1.75rem; }
a { color: var(--link); text-decoration: none; }
a:hover { color: var(--link-hover); text-decoration: underline; }
a.w { color: var(--link); }
.footer {
  margin-top: 3rem; padding-top: 0.75rem;
  border-top: 1px solid var(--line);
  color: var(--muted); font-size: 0.78rem;
}

/* --- landing page --- */
.big-links { list-style: none; padding: 0; margin: 1.5rem 0; }
.big-links li { margin: 0.6rem 0; }
.big-links a { font-size: 1.1rem; }
.big-links .desc { color: var(--muted); font-size: 0.85rem; margin-left: 0.5rem; }

/* --- letter grid --- */
.letter-grid {
  display: flex; flex-wrap: wrap; gap: 0.35rem;
  margin: 1rem 0 2rem;
}
.letter-grid a {
  display: inline-block;
  min-width: 2.6rem;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--line);
  text-align: center;
  color: var(--text);
  font-weight: 500;
}
.letter-grid a:hover { border-color: var(--text); text-decoration: none; background: #f4f4f4; }
.letter-grid a.empty { color: var(--line); pointer-events: none; }

/* --- word list under a letter --- */
.word-list { column-width: 12rem; column-gap: 1.5rem; margin: 0; padding: 0; list-style: none; }
.word-list li { padding: 0.12rem 0; break-inside: avoid; }
.word-list .gloss { color: var(--muted); font-size: 0.82rem; margin-left: 0.3rem; }

/* --- word page --- */
.headword {
  font-size: 2rem; font-weight: 600; color: var(--accent);
  margin: 0.25rem 0 0.1rem;
}
.ipa { font-style: italic; color: var(--muted); }
.meta-row {
  display: flex; gap: 1.2rem; flex-wrap: wrap;
  font-size: 0.75rem; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.08em;
  margin-top: 0.4rem;
}
.meta-row .pill {
  padding: 0.05rem 0.5rem; border: 1px solid var(--line);
  border-radius: 2px; text-transform: none; letter-spacing: 0;
  font-size: 0.72rem;
}
.english {
  font-style: italic; margin: 1rem 0 0;
  padding-top: 0.75rem; border-top: 1px solid var(--line);
}

/* case grid */
.cases { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 0.5rem; }
.case-col-header { text-transform: uppercase; letter-spacing: 0.08em;
  font-size: 0.68rem; color: var(--muted);
  border-bottom: 1px solid var(--line); padding-bottom: 0.2rem; margin-bottom: 0.3rem; }
.case-row { display: grid; grid-template-columns: 3rem 1fr; gap: 0.5rem; padding: 0.1rem 0; }
.case-label { color: var(--muted); font-size: 0.7rem;
  text-transform: uppercase; letter-spacing: 0.06em; align-self: center; }

/* non-finite forms */
.nonfinite { display: flex; flex-wrap: wrap; gap: 0.4rem 1.2rem;
  margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed var(--line);
  font-size: 0.9rem; }
.nf-item { display: inline-flex; gap: 0.3rem; align-items: baseline; }
.nf-label { color: var(--muted); font-size: 0.62rem;
  text-transform: uppercase; letter-spacing: 0.08em; }

/* paradigm & adjective tables */
table.paradigm, table.adj-table {
  width: 100%; border-collapse: collapse; font-size: 0.88rem;
  margin-top: 0.5rem;
}
table.paradigm th, table.paradigm td,
table.adj-table th, table.adj-table td {
  padding: 0.2rem 0.5rem 0.2rem 0;
  text-align: left; vertical-align: baseline;
}
table.paradigm thead th, table.adj-table thead th {
  text-transform: uppercase; letter-spacing: 0.08em;
  font-size: 0.6rem; color: var(--muted);
  border-bottom: 1px solid var(--line); font-weight: normal;
  padding-bottom: 0.35rem;
}
table.paradigm tbody th, table.adj-table tbody th {
  text-transform: uppercase; letter-spacing: 0.06em;
  font-size: 0.65rem; color: var(--muted); font-weight: normal;
  padding-right: 0.7rem;
}
table.paradigm td.empty, table.adj-table td.empty { color: var(--line); }
.paradigm-wrap, .adj-wrap { margin-top: 0.75rem; padding-top: 0.5rem;
  border-top: 1px dashed var(--line); overflow-x: auto; }

/* cognates */
.cognates { display: flex; flex-wrap: wrap; gap: 0.5rem 1.1rem;
  margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px solid var(--line);
  font-size: 0.9rem; }
.cog-label { color: var(--muted); font-size: 0.65rem;
  text-transform: uppercase; letter-spacing: 0.06em; margin-right: 0.25rem; }

/* examples */
.examples { margin-top: 1rem; padding-top: 0.75rem;
  border-top: 1px solid var(--line); }
.examples .lbl { color: var(--muted); font-size: 0.7rem;
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.4rem; }
.example { padding: 0.25rem 0; }
.example .frk { font-style: italic; }
.example .eng { color: var(--muted); font-size: 0.85rem; margin-top: 0.1rem; }

/* sentences page */
.sentence-list { list-style: none; padding: 0; margin: 0.5rem 0; }
.sentence-list li { padding: 0.55rem 0; border-bottom: 1px dotted var(--line); }
.sentence-list .frk { font-style: italic; }
.sentence-list .eng { color: var(--muted); font-size: 0.88rem; margin-top: 0.15rem; }
.sentence-list .src { color: var(--muted); font-size: 0.72rem; margin-top: 0.1rem;
  text-transform: uppercase; letter-spacing: 0.06em; }

/* phonemes page */
table.phonemes { width: 100%; border-collapse: collapse; font-size: 0.9rem;
  margin-top: 0.5rem; }
table.phonemes th, table.phonemes td {
  padding: 0.35rem 0.6rem 0.35rem 0; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--line);
}
table.phonemes thead th {
  text-transform: uppercase; letter-spacing: 0.08em;
  font-size: 0.65rem; color: var(--muted); font-weight: normal;
  border-bottom: 1px solid var(--text);
}
table.phonemes .sym { font-family: "Charis SIL", "Doulos SIL", serif;
  font-size: 1.05rem; }
table.phonemes .rune { font-size: 1.1rem; }

.notes { color: var(--muted); font-size: 0.85rem; margin-top: 0.5rem; font-style: italic; }
.source { color: var(--muted); font-size: 0.72rem; margin-top: 0.5rem;
  text-transform: uppercase; letter-spacing: 0.06em; }
"""


def page_shell(title, current, body):
    """Wrap body in the standard nav + wrapper. current is one of:
       'home' | 'phonemes' | 'words' | 'sentences' | '' """
    def cls(sec):
        return ' class="here"' if current == sec else ''
    nav = (
        '<nav class="top">'
        f'<a href="index.html"{cls("home")}>Home</a>'
        f'<a href="phonemes.html"{cls("phonemes")}>Phonemes</a>'
        f'<a href="words.html"{cls("words")}>Words</a>'
        f'<a href="sentences.html"{cls("sentences")}>Sentences</a>'
        '</nav>'
    )
    return (
        '<!DOCTYPE html>\n'
        f'<html lang="en"><head><meta charset="UTF-8"><title>{esc(title)}</title>'
        '<link rel="stylesheet" href="style.css"></head><body>'
        f'<div class="wrap">{nav}{body}'
        f'<div class="footer">generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>'
        '</div></body></html>\n'
    )


# ---------- word page renderers (adapted from the single-file generator) ----------

def render_case_grid(w):
    sg = [('nom', w.get('nom_sg')), ('gen', w.get('gen_sg')),
          ('dat', w.get('dat_sg')), ('acc', w.get('acc_sg')),
          ('instr', w.get('instr_sg'))]
    pl = [('nom', w.get('nom_pl')), ('gen', w.get('gen_pl')),
          ('dat', w.get('dat_pl')), ('acc', w.get('acc_pl')),
          ('instr', w.get('instr_pl'))]
    sg = [(l, v) for l, v in sg if v]
    pl = [(l, v) for l, v in pl if v]
    if not sg and not pl:
        return ''
    parts = ['<div class="cases">']
    for col_label, col in (('singular', sg), ('plural', pl)):
        if col:
            parts.append('<div>')
            parts.append(f'<div class="case-col-header">{col_label}</div>')
            for l, v in col:
                parts.append(
                    f'<div class="case-row"><span class="case-label">{l}</span>'
                    f'<span>{esc(v)}</span></div>'
                )
            parts.append('</div>')
    parts.append('</div>')
    return '\n'.join(parts)


def render_nonfinite(w):
    items = [
        ('inf',      w.get('infinitive')),
        ('imp sg',   w.get('imp_sg')),
        ('imp pl',   w.get('imp_pl')),
        ('past ptc', w.get('past_part')),
    ]
    items = [(l, v) for l, v in items if v]
    if not items:
        return ''
    spans = ''.join(
        f'<span class="nf-item"><span class="nf-label">{l}</span>{esc(v)}</span>'
        for l, v in items
    )
    return f'<div class="nonfinite">{spans}</div>'


def render_paradigm(w):
    grid = {}
    for _, row_key in PERSON_ROWS:
        grid[row_key] = {}
        for _, col_prefix in MOOD_TENSE_COLS:
            grid[row_key][col_prefix] = w.get(f'{col_prefix}_{row_key}') or ''
    active_cols = [(cl, cp) for cl, cp in MOOD_TENSE_COLS
                   if any(grid[rk][cp] for _, rk in PERSON_ROWS)]
    if not active_cols:
        return ''
    active_rows = [(rl, rk) for rl, rk in PERSON_ROWS
                   if any(grid[rk][cp] for _, cp in active_cols)]
    if not active_rows:
        return ''
    out = ['<div class="paradigm-wrap"><table class="paradigm">',
           '<thead><tr><th></th>']
    for cl, _ in active_cols:
        out.append(f'<th>{esc(cl)}</th>')
    out.append('</tr></thead><tbody>')
    for rl, rk in active_rows:
        out.append('<tr>')
        out.append(f'<th>{esc(rl)}</th>')
        for _, cp in active_cols:
            v = grid[rk][cp]
            out.append(f'<td>{esc(v)}</td>' if v else '<td class="empty">—</td>')
        out.append('</tr>')
    out.append('</tbody></table></div>')
    return '\n'.join(out)


def render_adj(w):
    grid = {}
    for _, rk in ADJ_ROWS:
        grid[rk] = {}
        for _, ck in ADJ_COLS:
            grid[rk][ck] = w.get(f'adj_{ck}_{rk}') or ''
    active_cols = [(cl, ck) for cl, ck in ADJ_COLS
                   if any(grid[rk][ck] for _, rk in ADJ_ROWS)]
    if not active_cols:
        return ''
    active_rows = [(rl, rk) for rl, rk in ADJ_ROWS
                   if any(grid[rk][ck] for _, ck in active_cols)]
    if not active_rows:
        return ''
    out = ['<div class="adj-wrap"><table class="adj-table">',
           '<thead><tr><th></th>']
    for cl, _ in active_cols:
        out.append(f'<th>{esc(cl)}</th>')
    out.append('</tr></thead><tbody>')
    for rl, rk in active_rows:
        out.append('<tr>')
        out.append(f'<th>{esc(rl)}</th>')
        for _, ck in active_cols:
            v = grid[rk][ck]
            out.append(f'<td>{esc(v)}</td>' if v else '<td class="empty">—</td>')
        out.append('</tr>')
    out.append('</tbody></table></div>')
    return '\n'.join(out)


def render_cognates(w):
    cogs = [
        ('OHG',    w.get('old_high_german')),
        ('OE',     w.get('old_english')),
        ('ON',     w.get('old_norse')),
        ('Gothic', w.get('gothic')),
    ]
    cogs = [(l, v) for l, v in cogs if v]
    if not cogs:
        return ''
    spans = ''.join(
        f'<span><span class="cog-label">{l}</span>{esc(v)}</span>'
        for l, v in cogs
    )
    return f'<div class="cognates">{spans}</div>'


# ---------- sentence tokenizer with word links ----------

_WORD_RE = re.compile(r'(\w+|\W+)', re.UNICODE)


def render_sentence_frk(sentence_text, sw_list, db_to_new, new_to_word):
    """
    Walk sentence_text token by token. Word-tokens get hyperlinked to
    w-<new_id>.html based on the sentence_words entries (ordered by position).
    """
    tokens = _WORD_RE.findall(sentence_text)
    # sentence_words already ordered by position
    sw_iter = iter(sw_list)
    out = []
    for tok in tokens:
        if re.match(r'\w+', tok, re.UNICODE):
            try:
                _pos, db_wid, _surface = next(sw_iter)
            except StopIteration:
                # more word-tokens than sentence_words entries — leave unlinked
                out.append(esc(tok))
                continue
            new_id = db_to_new.get(db_wid)
            if new_id is None:
                out.append(esc(tok))
            else:
                out.append(f'<a class="w" href="w-{new_id}.html">{esc(tok)}</a>')
        else:
            out.append(esc(tok))
    return ''.join(out)


def render_examples_for_word(w, sentences_by_id, sw_by_sid, db_to_new, new_to_word):
    """Sentences this word is used in, with every word in each sentence hyperlinked."""
    # collect distinct sentence ids where this word appears
    sids = []
    seen = set()
    for sid, sw_list in sw_by_sid.items():
        for _pos, db_wid, _surf in sw_list:
            if db_wid == w['id']:
                if sid not in seen:
                    seen.add(sid)
                    sids.append(sid)
                break
    if not sids:
        return ''
    sids.sort()
    parts = ['<div class="examples"><div class="lbl">used in</div>']
    for sid in sids:
        s = sentences_by_id.get(sid)
        if not s:
            continue
        frk = render_sentence_frk(s['frankish'], sw_by_sid.get(sid, []),
                                  db_to_new, new_to_word)
        parts.append('<div class="example">')
        parts.append(f'<div class="frk">{frk}</div>')
        if s.get('english'):
            parts.append(f'<div class="eng">{esc(s["english"])}</div>')
        parts.append('</div>')
    parts.append('</div>')
    return '\n'.join(parts)


# ---------- page builders ----------

def build_index(letter_counts):
    total_words = sum(letter_counts.values())
    body = (
        '<h1>Siegfried Lexicon</h1>'
        '<div class="sub">Reconstructed Old Ripuarian Frankish</div>'
        '<ul class="big-links">'
        '<li><a href="phonemes.html">Phonemes</a>'
        '<span class="desc">— sound inventory</span></li>'
        f'<li><a href="words.html">Words</a>'
        f'<span class="desc">— {total_words} entries across {sum(1 for c in letter_counts.values() if c)} letters</span></li>'
        '<li><a href="sentences.html">Sentences</a>'
        '<span class="desc">— attested and reconstructed passages</span></li>'
        '</ul>'
    )
    return page_shell('Siegfried Lexicon', 'home', body)


def build_phonemes_page(rows):
    vowels = [r for r in rows if (r[1] or '').lower() == 'vowel']
    consonants = [r for r in rows if (r[1] or '').lower() == 'consonant']
    other = [r for r in rows
             if (r[1] or '').lower() not in ('vowel', 'consonant')]

    def render_table(title, subset):
        if not subset:
            return ''
        head = (
            '<thead><tr>'
            '<th>Symbol</th><th>Latin</th><th>Rune</th>'
            '<th>Description</th><th>Example</th><th>Notes</th>'
            '</tr></thead>'
        )
        body_rows = []
        for symbol, _type, desc, latin, rune, ex, notes in subset:
            body_rows.append(
                '<tr>'
                f'<td class="sym">/{esc(symbol)}/</td>'
                f'<td>{esc(latin)}</td>'
                f'<td class="rune">{esc(rune)}</td>'
                f'<td>{esc(desc)}</td>'
                f'<td>{esc(ex)}</td>'
                f'<td>{esc(notes)}</td>'
                '</tr>'
            )
        return (
            f'<h2>{esc(title)}</h2>'
            f'<table class="phonemes">{head}<tbody>{"".join(body_rows)}</tbody></table>'
        )

    body = '<h1>Phonemes</h1>'
    body += render_table('Vowels', vowels)
    body += render_table('Consonants', consonants)
    if other:
        body += render_table('Other', other)
    return page_shell('Phonemes', 'phonemes', body)


def build_letter_grid_page(letter_counts):
    """words.html — grid of letters, each linking to its own page."""
    body = '<h1>Words</h1><div class="sub">Choose a letter.</div>'
    body += '<div class="letter-grid">'
    for letter, label in LETTERS:
        n = letter_counts.get(letter, 0)
        if n:
            body += (
                f'<a href="words-{letter}.html" '
                f'title="{esc(label)} — {n} entr' + ('y' if n == 1 else 'ies') + '">'
                f'{esc(label)}</a>'
            )
        else:
            body += f'<a class="empty" title="no entries">{esc(label)}</a>'
    body += '</div>'
    return page_shell('Words', 'words', body)


def build_letter_page(letter, label, words_here, letter_counts):
    """words-<L>.html — list of words for this letter, with letter nav on top."""
    if not words_here:
        body = f'<h1>{esc(label)}</h1><div class="sub">No entries.</div>'
        return page_shell(f'{label}', 'words', body)
    body = f'<h1>{esc(label)}</h1>'
    # in-page letter nav so you can jump between letters
    body += '<div class="letter-grid">'
    for l, lab in LETTERS:
        n = letter_counts.get(l, 0)
        if l == letter:
            body += f'<a class="here" style="border-color: var(--text);">{esc(lab)}</a>'
        elif n:
            body += f'<a href="words-{l}.html">{esc(lab)}</a>'
        else:
            body += f'<a class="empty">{esc(lab)}</a>'
    body += '</div>'
    body += f'<div class="sub">{len(words_here)} entr' + ('y' if len(words_here) == 1 else 'ies') + '</div>'
    body += '<ul class="word-list">'
    for w in words_here:
        gloss = w.get('english') or ''
        if len(gloss) > 45:
            gloss = gloss[:42] + '…'
        pos = w.get('pos') or ''
        body += (
            f'<li>{link_to_word(w)} '
            f'<span class="gloss">'
            + (esc(pos) + ' · ' if pos else '')
            + f'{esc(gloss)}</span></li>'
        )
    body += '</ul>'
    return page_shell(label, 'words', body)


def build_word_page(w, sentences_by_id, sw_by_sid, db_to_new, new_to_word):
    body = f'<h1 class="headword">{esc(w["headword"])}</h1>'
    if w.get('ipa'):
        body += f'<div class="ipa">/{esc(w["ipa"])}/</div>'
    # meta row: pos, gender/class, categories
    meta_parts = []
    if w.get('pos'):
        meta_parts.append(esc(w['pos']))
    if w.get('gender_class'):
        label = 'gender' if (w.get('pos') or '').lower() in ('noun', 'name') else 'class'
        meta_parts.append(f'{label}: {esc(w["gender_class"])}')
    for cat_key in ('category', 'category2'):
        v = (w.get(cat_key) or '').strip()
        if v:
            meta_parts.append(f'<span class="pill">{esc(v)}</span>')
    if meta_parts:
        body += '<div class="meta-row">' + ' · '.join(meta_parts) + '</div>'

    # forms
    cg  = render_case_grid(w)
    nf  = render_nonfinite(w)
    par = render_paradigm(w)
    adj = render_adj(w)
    if cg:  body += cg
    if nf:  body += nf
    if par: body += par
    if adj: body += adj

    # english gloss
    if w.get('english'):
        body += f'<div class="english">{esc(w["english"])}</div>'

    # cognates
    cogs = render_cognates(w)
    if cogs:
        body += cogs

    # examples
    body += render_examples_for_word(w, sentences_by_id, sw_by_sid,
                                     db_to_new, new_to_word)

    # notes, source
    if w.get('word_notes'):
        body += f'<div class="notes">{esc(w["word_notes"])}</div>'
    if w.get('source'):
        body += f'<div class="source">{esc(w["source"])}</div>'

    return page_shell(w['headword'], '', body)


def build_sentences_page(sentences, sw_by_sid, db_to_new, new_to_word):
    body = f'<h1>Sentences</h1><div class="sub">{len(sentences)} entries. Every word links to its lexicon page.</div>'
    body += '<ul class="sentence-list">'
    for s in sentences:
        frk = render_sentence_frk(s['frankish'], sw_by_sid.get(s['id'], []),
                                  db_to_new, new_to_word)
        body += '<li>'
        body += f'<div class="frk">{frk}</div>'
        if s.get('english'):
            body += f'<div class="eng">{esc(s["english"])}</div>'
        if s.get('source'):
            body += f'<div class="src">{esc(s["source"])}</div>'
        body += '</li>'
    body += '</ul>'
    return page_shell('Sentences', 'sentences', body)


# ---------- main ----------

def main():
    db_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'siegfried_lang.sqlite')
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else 'site')
    if not db_path.exists():
        print(f'db not found: {db_path}', file=sys.stderr)
        sys.exit(1)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    words = load_words(conn)
    sentences = load_sentences(conn)
    sw_by_sid = load_sentence_words(conn)
    phonemes = load_phonemes(conn)
    conn.close()

    # assign new sequential ids by alphabetical order
    ordered, db_to_new, new_to_word = assign_new_ids(words)

    # bucket by letter
    by_letter = {L: [] for L, _ in LETTERS}
    misc = []
    for w in ordered:
        L = bucket_letter(w.get('headword') or '')
        if L in by_letter:
            by_letter[L].append(w)
        else:
            misc.append(w)
    letter_counts = {L: len(by_letter[L]) for L, _ in LETTERS}

    # write files
    (out_dir / 'style.css').write_text(CSS, encoding='utf-8')
    (out_dir / 'index.html').write_text(build_index(letter_counts), encoding='utf-8')
    (out_dir / 'phonemes.html').write_text(build_phonemes_page(phonemes), encoding='utf-8')
    (out_dir / 'words.html').write_text(build_letter_grid_page(letter_counts), encoding='utf-8')

    sentences_by_id = {s['id']: s for s in sentences}

    for letter, label in LETTERS:
        page = build_letter_page(letter, label, by_letter[letter], letter_counts)
        (out_dir / f'words-{letter}.html').write_text(page, encoding='utf-8')

    for w in ordered:
        page = build_word_page(w, sentences_by_id, sw_by_sid, db_to_new, new_to_word)
        (out_dir / w['filename']).write_text(page, encoding='utf-8')

    sentences_page = build_sentences_page(sentences, sw_by_sid, db_to_new, new_to_word)
    (out_dir / 'sentences.html').write_text(sentences_page, encoding='utf-8')

    total_files = (
        4                              # index, phonemes, words, sentences
        + len(LETTERS)                 # per-letter pages
        + len(ordered)                 # per-word pages
        + 1                            # style.css
    )
    print(f'wrote {total_files} files to {out_dir}/')
    print(f'  {len(ordered)} word pages, {len(sentences)} sentences, {len(phonemes)} phonemes')
    print(f'  sigifrīþ (db id {[w["id"] for w in ordered if (w.get("headword") or "").lower().startswith("sigifr")][:3]}) → new ids '
          f'{[w["new_id"] for w in ordered if (w.get("headword") or "").lower().startswith("sigifr")][:5]}')


if __name__ == '__main__':
    main()
