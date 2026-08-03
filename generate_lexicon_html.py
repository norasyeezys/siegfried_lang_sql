#!/usr/bin/env python3
"""
Generate a static HTML lexicon view from siegfried_lang.sqlite.
Stdlib only. Run:
    python3 generate_lexicon_html.py [db_path] [output_html_path]
Defaults: siegfried_lang.sqlite -> siegfried_lexicon.html
"""
import sqlite3
import html
import sys
from pathlib import Path
from datetime import datetime


CSS = """
:root {
  --bg: #f4ecdb;
  --card: #fbf6e8;
  --text: #2a1d11;
  --muted: #7d6648;
  --accent: #5c2c10;
  --border: #d8c8a8;
  --hover: #efe5cd;
  --pill-bg: #e8dcb8;
}
* { box-sizing: border-box; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: Georgia, 'Cardo', 'EB Garamond', 'Palatino Linotype', serif;
  margin: 0;
  padding: 2rem 1.5rem;
  line-height: 1.5;
}
.container { max-width: 1280px; margin: 0 auto; }
header.page-header {
  border-bottom: 2px solid var(--border);
  margin-bottom: 1.75rem;
  padding-bottom: 1rem;
}
h1 { margin: 0 0 0.25rem; font-size: 2.5rem; color: var(--accent); letter-spacing: 0.01em; }
.subtitle { color: var(--muted); font-style: italic; font-size: 1rem; }
.search-row {
  display: flex; gap: 0.75rem; margin-bottom: 1.5rem; align-items: center;
  flex-wrap: wrap;
}
.search {
  flex: 1;
  min-width: 240px;
  padding: 0.7rem 1rem;
  font-size: 1rem;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text);
  border-radius: 4px;
  font-family: inherit;
}
.search:focus { outline: none; border-color: var(--accent); }
.cat-filter {
  padding: 0.7rem 1rem;
  font-size: 0.95rem;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text);
  border-radius: 4px;
  font-family: inherit;
  cursor: pointer;
  min-width: 180px;
}
.cat-filter:focus { outline: none; border-color: var(--accent); }
.count {
  color: var(--muted);
  font-size: 0.85rem;
  font-style: italic;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(410px, 1fr));
  gap: 1.5rem;
}
.word-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 1.1rem 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  box-shadow: 0 1px 0 rgba(60, 30, 0, 0.04);
}
.word-card > header {
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.headword {
  margin: 0;
  font-size: 1.8rem;
  color: var(--accent);
  line-height: 1.1;
}
.ipa {
  font-style: italic;
  color: var(--muted);
  font-size: 1.02rem;
}
.header-meta {
  display: flex;
  gap: 0.9rem;
  align-items: baseline;
  margin-top: 0.15rem;
  flex-wrap: wrap;
}
.pos {
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.68rem;
  color: var(--muted);
}
.gender-class {
  display: inline-flex;
  align-items: baseline;
  gap: 0.35rem;
  font-size: 0.68rem;
  color: var(--muted);
  letter-spacing: 0.08em;
}
.gc-label {
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  opacity: 0.75;
}
.gc-val {
  text-transform: uppercase;
  letter-spacing: 0.12em;
}
.category-pill {
  display: inline-block;
  padding: 0.12rem 0.55rem;
  background: var(--pill-bg);
  color: var(--accent);
  font-size: 0.7rem;
  border-radius: 10px;
  font-style: italic;
  letter-spacing: 0.02em;
}
.category-pills { display: inline-flex; gap: 0.3rem; flex-wrap: wrap; }
.cases { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.case-col-header {
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 0.65rem;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.2rem;
  margin-bottom: 0.35rem;
}
.case-row {
  display: grid;
  grid-template-columns: 3.2rem 1fr;
  gap: 0.5rem;
  padding: 0.1rem 0;
  font-size: 0.95rem;
}
.case-label {
  color: var(--muted);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  align-self: center;
}
.case-val { font-family: inherit; }

/* --- non-finite verb forms (infinitive, imperatives, past participle) --- */
.nonfinite {
  display: flex; flex-wrap: wrap; gap: 0.4rem 1.1rem;
  padding-top: 0.4rem;
  border-top: 1px dashed var(--border);
  font-size: 0.9rem;
}
.nonfinite-item { display: inline-flex; gap: 0.35rem; align-items: baseline; }
.nf-label {
  color: var(--muted); font-size: 0.62rem;
  text-transform: uppercase; letter-spacing: 0.08em;
}

/* --- verb paradigm grid: rows = person/num, columns = mood/tense --- */
.paradigm-wrap {
  padding-top: 0.5rem;
  border-top: 1px dashed var(--border);
  overflow-x: auto;
}
table.paradigm {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
table.paradigm th, table.paradigm td {
  padding: 0.2rem 0.5rem 0.2rem 0;
  text-align: left;
  vertical-align: baseline;
}
table.paradigm thead th {
  text-transform: uppercase; letter-spacing: 0.08em;
  font-size: 0.6rem; color: var(--muted);
  border-bottom: 1px solid var(--border);
  font-weight: normal;
  padding-bottom: 0.35rem;
}
table.paradigm tbody th {
  text-transform: uppercase; letter-spacing: 0.06em;
  font-size: 0.65rem; color: var(--muted);
  font-weight: normal;
  padding-right: 0.7rem;
  width: 2.6rem;
}
table.paradigm td.empty-cell { color: var(--border); }

/* --- adjective grid: rows = case, columns = gender/number --- */
.adj-wrap {
  padding-top: 0.5rem;
  border-top: 1px dashed var(--border);
  overflow-x: auto;
}
table.adj-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
table.adj-table th, table.adj-table td {
  padding: 0.2rem 0.5rem 0.2rem 0;
  text-align: left;
}
table.adj-table thead th {
  text-transform: uppercase; letter-spacing: 0.08em;
  font-size: 0.6rem; color: var(--muted);
  border-bottom: 1px solid var(--border);
  font-weight: normal;
  padding-bottom: 0.35rem;
}
table.adj-table tbody th {
  text-transform: uppercase; letter-spacing: 0.06em;
  font-size: 0.65rem; color: var(--muted);
  font-weight: normal;
  padding-right: 0.6rem;
  width: 2.4rem;
}
table.adj-table td.empty-cell { color: var(--border); }

.english {
  padding: 0.5rem 0 0.3rem;
  border-top: 1px dashed var(--border);
  font-style: italic;
  color: var(--text);
}
.cognates {
  display: flex; flex-wrap: wrap; gap: 0.6rem 1rem;
  padding-top: 0.5rem; border-top: 1px solid var(--border);
  font-size: 0.92rem;
}
.cognate { display: inline-flex; gap: 0.35rem; align-items: baseline; }
.cog-label {
  color: var(--muted);
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.source {
  font-size: 0.72rem;
  color: var(--muted);
  font-style: italic;
  margin-top: auto;
  padding-top: 0.5rem;
}
.notes {
  font-size: 0.85rem;
  color: var(--muted);
  font-style: italic;
}
.examples {
  border-top: 1px dashed var(--border);
  padding-top: 0.5rem;
  font-size: 0.88rem;
}
.examples-label {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.65rem;
  color: var(--muted);
  margin-bottom: 0.25rem;
}
.example { padding: 0.1rem 0; }
.example-frk { font-style: italic; }
.example-eng { color: var(--muted); font-size: 0.82rem; }
.meta {
  color: var(--muted); font-size: 0.82rem;
  margin-top: 2.5rem; text-align: center;
  border-top: 1px solid var(--border);
  padding-top: 1rem;
}
.hidden { display: none; }
.empty {
  text-align: center; color: var(--muted); font-style: italic;
  padding: 2rem; grid-column: 1 / -1;
}
"""

JS = """
const search = document.getElementById('search');
const catFilter = document.getElementById('cat-filter');
const cards = document.querySelectorAll('.word-card');
const countEl = document.getElementById('visible-count');
const totalCount = cards.length;

function updateCount(visible) {
  countEl.textContent = visible === totalCount
    ? `${totalCount} entries`
    : `${visible} of ${totalCount} entries`;
}

function applyFilters() {
  const q = search.value.trim().toLowerCase();
  const cat = catFilter ? catFilter.value : '';
  let visible = 0;
  cards.forEach(card => {
    const data = card.getAttribute('data-search');
    const cardCats = (card.getAttribute('data-categories') || '').split('|').filter(Boolean);
    const matchText = !q || data.includes(q);
    const matchCat = !cat || cardCats.includes(cat);
    const show = matchText && matchCat;
    card.classList.toggle('hidden', !show);
    if (show) visible++;
  });
  updateCount(visible);
}

search.addEventListener('input', applyFilters);
if (catFilter) catFilter.addEventListener('change', applyFilters);
"""

HTML_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Siegfried Lexicon</title>
<style>{css}</style>
</head>
<body>
<div class="container">
  <header class="page-header">
    <h1>Siegfried Lexicon</h1>
    <div class="subtitle">Reconstructed Old Ripuarian Frankish</div>
  </header>
  <div class="search-row">
    <input type="text" id="search" class="search" placeholder="filter by headword, meaning, part of speech, cognate, or paradigm cell...">
    {cat_select}
    <span class="count" id="visible-count">{count} entries</span>
  </div>
  <div class="grid" id="grid">
{cards}
  </div>
  <div class="meta">generated from siegfried_lang.sqlite at {timestamp}</div>
</div>
<script>{js}</script>
</body>
</html>
"""


# ---------- paradigm structure declarations ----------

# rows in the finite verb paradigm, ordered
PERSON_ROWS = [
    ('1sg', '1sg'),
    ('2sg', '2sg'),
    ('3sg', '3sg'),
    ('1pl', '1pl'),
    ('2pl', '2pl'),
    ('3pl', '3pl'),
]

# columns in the finite verb paradigm: (column label, column prefix)
# each cell is column_prefix + '_' + row_key -> words table column
MOOD_TENSE_COLS = [
    ('pres',       'pres'),
    ('pres sbjv',  'pres_sbjv'),
    ('past',       'past'),
    ('past sbjv',  'past_sbjv'),
]

# adjective grid: rows = case, columns = gender/number
ADJ_ROWS = [
    ('nom', 'nom'),
    ('acc', 'acc'),
]
ADJ_COLS = [
    ('masc', 'masc'),
    ('fem',  'fem'),
    ('neut', 'neut'),
    ('pl',   'pl'),
]


def get_words(conn):
    cur = conn.execute("SELECT * FROM v_word_card ORDER BY headword;")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_examples_for_word(conn, word_id):
    """Pull distinct sentences this word appears in.
    A word can occur multiple times in one sentence (e.g. 'sō ... sō ... sō ...'
    in a Merseburg-style charm formula); collapse those to one row per sentence
    instead of emitting the sentence once per occurrence."""
    try:
        cur = conn.execute("""
            SELECT s.frankish, s.english
            FROM sentences s
            WHERE s.id IN (
                SELECT sentence_id FROM sentence_words WHERE word_id = ?
            )
            ORDER BY s.id;
        """, (word_id,))
        return cur.fetchall()
    except sqlite3.OperationalError:
        return []


def esc(v):
    if v is None or v == '':
        return ''
    return html.escape(str(v))


def render_gender_class(w):
    """Conditional label: 'gender' for nouns/names, 'class' for everything else."""
    gc = w.get('gender_class')
    if not gc:
        return ''
    pos = (w.get('pos') or '').lower()
    label = 'gender' if pos in ('noun', 'name') else 'class'
    return (
        f'<span class="gender-class">'
        f'<span class="gc-label">{label}</span>'
        f'<span class="gc-val">{esc(gc)}</span>'
        f'</span>'
    )


def render_category(w):
    pills = []
    for key in ('category', 'category2'):
        v = (w.get(key) or '').strip()
        if v:
            pills.append(f'<span class="category-pill">{esc(v)}</span>')
    if not pills:
        return ''
    return f'<span class="category-pills">{"".join(pills)}</span>'


def render_case_grid(w):
    sg = [('nom', w.get('nom_sg')), ('gen', w.get('gen_sg')),
          ('dat', w.get('dat_sg')), ('acc', w.get('acc_sg')),
          ('instr', w.get('instr_sg'))]
    pl = [('nom', w.get('nom_pl')), ('gen', w.get('gen_pl')),
          ('dat', w.get('dat_pl')), ('acc', w.get('acc_pl')),
          ('instr', w.get('instr_pl'))]
    sg_has = [(l, v) for l, v in sg if v]
    pl_has = [(l, v) for l, v in pl if v]
    if not sg_has and not pl_has:
        return ''
    out = ['<div class="cases">']
    if sg_has:
        out.append('  <div>')
        out.append('    <div class="case-col-header">singular</div>')
        for l, v in sg_has:
            out.append(f'    <div class="case-row"><span class="case-label">{l}</span><span class="case-val">{esc(v)}</span></div>')
        out.append('  </div>')
    if pl_has:
        out.append('  <div>')
        out.append('    <div class="case-col-header">plural</div>')
        for l, v in pl_has:
            out.append(f'    <div class="case-row"><span class="case-label">{l}</span><span class="case-val">{esc(v)}</span></div>')
        out.append('  </div>')
    out.append('</div>')
    return '\n'.join(out)


def render_nonfinite(w):
    """Infinitive, imperative sg/pl, past participle — the non-paradigm-cell verb forms."""
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
        f'<span class="nonfinite-item"><span class="nf-label">{l}</span>{esc(v)}</span>'
        for l, v in items
    )
    return f'<div class="nonfinite">{spans}</div>'


def render_paradigm(w):
    """Grid: rows = person/number, cols = mood/tense. Drop columns and rows that are all-empty."""
    # collect values into a 2D dict: paradigm[row_key][col_prefix] = value
    paradigm = {}
    for row_label, row_key in PERSON_ROWS:
        paradigm[row_key] = {}
        for col_label, col_prefix in MOOD_TENSE_COLS:
            col_name = f'{col_prefix}_{row_key}'
            paradigm[row_key][col_prefix] = w.get(col_name) or ''

    # which columns have any content
    active_cols = []
    for col_label, col_prefix in MOOD_TENSE_COLS:
        if any(paradigm[row_key][col_prefix] for _, row_key in PERSON_ROWS):
            active_cols.append((col_label, col_prefix))
    if not active_cols:
        return ''

    # which rows have any content (within the active columns only)
    active_rows = []
    for row_label, row_key in PERSON_ROWS:
        if any(paradigm[row_key][col_prefix] for _, col_prefix in active_cols):
            active_rows.append((row_label, row_key))
    if not active_rows:
        return ''

    out = ['<div class="paradigm-wrap">', '<table class="paradigm">']
    out.append('  <thead><tr><th></th>')
    for col_label, _ in active_cols:
        out.append(f'    <th>{esc(col_label)}</th>')
    out.append('  </tr></thead>')
    out.append('  <tbody>')
    for row_label, row_key in active_rows:
        out.append('  <tr>')
        out.append(f'    <th>{esc(row_label)}</th>')
        for col_label, col_prefix in active_cols:
            val = paradigm[row_key][col_prefix]
            if val:
                out.append(f'    <td>{esc(val)}</td>')
            else:
                out.append('    <td class="empty-cell">—</td>')
        out.append('  </tr>')
    out.append('  </tbody>')
    out.append('</table></div>')
    return '\n'.join(out)


def render_adj_forms(w):
    """
    Adjective grid: rows = case (nom, acc), columns = gender/number (masc, fem, neut, pl).
    Actual schema columns are adj_<gender>_<case>, e.g. adj_masc_nom, adj_pl_acc.
    """
    grid = {}
    for row_label, row_key in ADJ_ROWS:
        grid[row_key] = {}
        for col_label, col_key in ADJ_COLS:
            col_name = f'adj_{col_key}_{row_key}'
            grid[row_key][col_key] = w.get(col_name) or ''

    # active columns
    active_cols = []
    for col_label, col_key in ADJ_COLS:
        if any(grid[row_key][col_key] for _, row_key in ADJ_ROWS):
            active_cols.append((col_label, col_key))
    if not active_cols:
        return ''

    # active rows
    active_rows = []
    for row_label, row_key in ADJ_ROWS:
        if any(grid[row_key][col_key] for _, col_key in active_cols):
            active_rows.append((row_label, row_key))
    if not active_rows:
        return ''

    out = ['<div class="adj-wrap">', '<table class="adj-table">']
    out.append('  <thead><tr><th></th>')
    for col_label, _ in active_cols:
        out.append(f'    <th>{esc(col_label)}</th>')
    out.append('  </tr></thead>')
    out.append('  <tbody>')
    for row_label, row_key in active_rows:
        out.append('  <tr>')
        out.append(f'    <th>{esc(row_label)}</th>')
        for col_label, col_key in active_cols:
            val = grid[row_key][col_key]
            if val:
                out.append(f'    <td>{esc(val)}</td>')
            else:
                out.append('    <td class="empty-cell">—</td>')
        out.append('  </tr>')
    out.append('  </tbody>')
    out.append('</table></div>')
    return '\n'.join(out)


def render_cognates(w):
    cogs = [
        ('OHG', w.get('old_high_german')),
        ('OE', w.get('old_english')),
        ('ON', w.get('old_norse')),
        ('Gothic', w.get('gothic')),
    ]
    cogs = [(l, v) for l, v in cogs if v]
    if not cogs:
        return ''
    spans = ''.join(
        f'<span class="cognate"><span class="cog-label">{l}</span>{esc(v)}</span>'
        for l, v in cogs
    )
    return f'<div class="cognates">{spans}</div>'


def render_examples(examples):
    if not examples:
        return ''
    out = ['<div class="examples">', '  <div class="examples-label">used in</div>']
    for frk, eng in examples:
        out.append(f'  <div class="example">')
        out.append(f'    <div class="example-frk">{esc(frk)}</div>')
        if eng:
            out.append(f'    <div class="example-eng">{esc(eng)}</div>')
        out.append(f'  </div>')
    out.append('</div>')
    return '\n'.join(out)


# ---------- search-text harvest: pull every displayed form into the filter index ----------

def harvest_search_text(w):
    """Everything a user might reasonably type to find this card, folded to lowercase."""
    parts = [
        w.get('headword'), w.get('english'), w.get('pos'), w.get('gender_class'),
        w.get('category'), w.get('category2'),
        w.get('old_high_german'), w.get('old_english'),
        w.get('old_norse'), w.get('gothic'),
        # noun case forms
        w.get('nom_sg'), w.get('gen_sg'), w.get('dat_sg'), w.get('acc_sg'), w.get('instr_sg'),
        w.get('nom_pl'), w.get('gen_pl'), w.get('dat_pl'), w.get('acc_pl'), w.get('instr_pl'),
        # non-finite verb forms
        w.get('infinitive'), w.get('imp_sg'), w.get('imp_pl'), w.get('past_part'),
    ]
    # finite paradigm cells
    for _, row_key in PERSON_ROWS:
        for _, col_prefix in MOOD_TENSE_COLS:
            parts.append(w.get(f'{col_prefix}_{row_key}'))
    # adjective forms
    for _, row_key in ADJ_ROWS:
        for _, col_key in ADJ_COLS:
            parts.append(w.get(f'adj_{col_key}_{row_key}'))
    return ' '.join(p for p in parts if p).lower()


def render_word(w, examples):
    search_text = harvest_search_text(w)
    cats_attr = '|'.join(filter(None, [
        (w.get('category') or '').strip(),
        (w.get('category2') or '').strip(),
    ]))
    pieces = [
        f'<article class="word-card" '
        f'data-search="{esc(search_text)}" '
        f'data-categories="{esc(cats_attr)}">'
    ]
    pieces.append('  <header>')
    pieces.append(f'    <h2 class="headword">{esc(w["headword"])}</h2>')
    if w.get('ipa'):
        pieces.append(f'    <div class="ipa">{esc(w["ipa"])}</div>')

    pos_html = f'<span class="pos">{esc(w["pos"])}</span>' if w.get('pos') else ''
    gc_html = render_gender_class(w)
    cat_html = render_category(w)
    if pos_html or gc_html or cat_html:
        pieces.append(f'    <div class="header-meta">{pos_html}{gc_html}{cat_html}</div>')
    pieces.append('  </header>')

    cg = render_case_grid(w)
    if cg: pieces.append(cg)

    nf = render_nonfinite(w)
    if nf: pieces.append(nf)

    par = render_paradigm(w)
    if par: pieces.append(par)

    adj = render_adj_forms(w)
    if adj: pieces.append(adj)

    if w.get('english'):
        pieces.append(f'  <div class="english">{esc(w["english"])}</div>')
    cogs = render_cognates(w)
    if cogs: pieces.append(cogs)
    ex = render_examples(examples)
    if ex: pieces.append(ex)
    if w.get('word_notes'):
        pieces.append(f'  <div class="notes">{esc(w["word_notes"])}</div>')
    if w.get('source'):
        pieces.append(f'  <div class="source">{esc(w["source"])}</div>')
    pieces.append('</article>')
    return '\n'.join(pieces)


def build_category_select(words):
    """Dropdown filter built from distinct non-empty categories across both columns."""
    cats = set()
    for w in words:
        for key in ('category', 'category2'):
            v = (w.get(key) or '').strip()
            if v:
                cats.add(v)
    cats = sorted(cats)
    if not cats:
        return ''
    opts = ['<option value="">all categories</option>']
    for c in cats:
        opts.append(f'<option value="{esc(c)}">{esc(c)}</option>')
    return f'<select id="cat-filter" class="cat-filter">{"".join(opts)}</select>'


def main():
    db_path = Path(sys.argv[1] if len(sys.argv) > 1 else 'siegfried_lang.sqlite')
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else 'siegfried_lexicon.html')
    if not db_path.exists():
        print(f"db not found: {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    words = get_words(conn)
    cards = []
    for w in words:
        examples = get_examples_for_word(conn, w['id'])
        cards.append(render_word(w, examples))
    cat_select = build_category_select(words)
    conn.close()
    if not cards:
        cards_html = '<div class="empty">no words yet</div>'
    else:
        cards_html = '\n'.join(cards)
    out = HTML_SHELL.format(
        css=CSS, js=JS,
        count=len(words),
        cards=cards_html,
        cat_select=cat_select,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    out_path.write_text(out, encoding='utf-8')
    cats = set()
    for w in words:
        for key in ('category', 'category2'):
            v = (w.get(key) or '').strip()
            if v:
                cats.add(v)
    print(f"wrote {out_path} with {len(words)} word cards, {len(cats)} categories")


if __name__ == '__main__':
    main()
