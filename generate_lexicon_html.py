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
  grid-template-columns: repeat(auto-fill, minmax(370px, 1fr));
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
.verb-parts { display: flex; flex-direction: column; gap: 0.2rem; }
.part-row { display: grid; grid-template-columns: 6rem 1fr; gap: 0.5rem; }
.part-label {
  text-transform: uppercase; letter-spacing: 0.06em;
  font-size: 0.7rem; color: var(--muted); align-self: center;
}
.adj-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
  padding-top: 0.2rem;
  border-top: 1px dashed var(--border);
  padding-top: 0.5rem;
}
.adj-col {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.1rem;
}
.adj-label {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.6rem;
  color: var(--muted);
}
.adj-val {
  font-family: inherit;
  font-size: 0.95rem;
}
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
    const cardCat = card.getAttribute('data-category') || '';
    const matchText = !q || data.includes(q);
    const matchCat = !cat || cardCat === cat;
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
    <input type="text" id="search" class="search" placeholder="filter by headword, meaning, part of speech, or cognate...">
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


def get_words(conn):
    cur = conn.execute("SELECT * FROM v_word_card ORDER BY headword;")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_examples_for_word(conn, word_id):
    """Pull example sentences this word appears in."""
    try:
        cur = conn.execute("""
            SELECT s.frankish, s.english, sw.surface_form
            FROM sentences s
            JOIN sentence_words sw ON sw.sentence_id = s.id
            WHERE sw.word_id = ?
            ORDER BY s.id, sw.position;
        """, (word_id,))
        return cur.fetchall()
    except sqlite3.OperationalError:
        return []


def esc(v):
    if v is None or v == '':
        return ''
    return html.escape(str(v))


def render_gender_class(w):
    """Render gender_class with conditional label: 'gender' for nouns/names, 'class' for everything else."""
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
    cat = w.get('category')
    if not cat:
        return ''
    return f'<span class="category-pill">{esc(cat)}</span>'


def render_case_grid(w):
    sg = [('nom', w.get('nom_sg')), ('gen', w.get('gen_sg')),
          ('dat', w.get('dat_sg')), ('acc', w.get('acc_sg')),
          ('instr', w.get('instr_sg') if 'instr_sg' in w else None)]
    pl = [('nom', w.get('nom_pl')), ('gen', w.get('gen_pl')),
          ('dat', w.get('dat_pl')), ('acc', w.get('acc_pl')),
          ('instr', w.get('instr_pl') if 'instr_pl' in w else None)]
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


def render_verb_parts(w):
    parts = [
        ('infinitive', w.get('infinitive')),
        ('pres 1sg', w.get('pres_1sg')),
        ('pres 2sg', w.get('pres_2sg')),
        ('pres 3sg', w.get('pres_3sg')),
        ('past 3sg', w.get('past_3sg')),
        ('past 3pl', w.get('past_3pl')),
        ('past part', w.get('past_part')),
    ]
    parts = [(l, v) for l, v in parts if v]
    if not parts:
        return ''
    out = ['<div class="verb-parts">']
    for l, v in parts:
        out.append(f'  <div class="part-row"><span class="part-label">{l}</span><span class="case-val">{esc(v)}</span></div>')
    out.append('</div>')
    return '\n'.join(out)


def render_adj_forms(w):
    """Render the four adjective/number agreement forms as a horizontal grid."""
    forms = [
        ('masc', w.get('adj_masc')),
        ('fem', w.get('adj_fem')),
        ('neut', w.get('adj_neut')),
        ('pl', w.get('adj_pl')),
    ]
    forms = [(l, v) for l, v in forms if v]
    if not forms:
        return ''
    out = ['<div class="adj-grid">']
    for l, v in forms:
        out.append(f'  <div class="adj-col">')
        out.append(f'    <div class="adj-label">{l}</div>')
        out.append(f'    <div class="adj-val">{esc(v)}</div>')
        out.append(f'  </div>')
    out.append('</div>')
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
    for frk, eng, surface in examples:
        out.append(f'  <div class="example">')
        out.append(f'    <div class="example-frk">{esc(frk)}</div>')
        if eng:
            out.append(f'    <div class="example-eng">{esc(eng)}</div>')
        out.append(f'  </div>')
    out.append('</div>')
    return '\n'.join(out)


def render_word(w, examples):
    search_text = ' '.join(filter(None, [
        w.get('headword'), w.get('english'), w.get('pos'), w.get('gender_class'),
        w.get('category'),
        w.get('old_high_german'), w.get('old_english'),
        w.get('old_norse'), w.get('gothic'),
    ])).lower()

    cat_attr = esc(w.get('category') or '')
    pieces = [
        f'<article class="word-card" '
        f'data-search="{esc(search_text)}" '
        f'data-category="{cat_attr}">'
    ]
    pieces.append('  <header>')
    pieces.append(f'    <h2 class="headword">{esc(w["headword"])}</h2>')
    if w.get('ipa'):
        pieces.append(f'    <div class="ipa">{esc(w["ipa"])}</div>')

    # pos, gender_class, category share the header_meta row
    pos_html = f'<span class="pos">{esc(w["pos"])}</span>' if w.get('pos') else ''
    gc_html = render_gender_class(w)
    cat_html = render_category(w)
    if pos_html or gc_html or cat_html:
        pieces.append(f'    <div class="header-meta">{pos_html}{gc_html}{cat_html}</div>')

    pieces.append('  </header>')

    cg = render_case_grid(w)
    if cg: pieces.append(cg)
    vp = render_verb_parts(w)
    if vp: pieces.append(vp)
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
    """Build the dropdown filter from distinct non-empty categories present in the data."""
    cats = sorted({(w.get('category') or '').strip() for w in words if (w.get('category') or '').strip()})
    if not cats:
        return ''  # no categories yet, omit the dropdown entirely
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
    n_cats = len({(w.get('category') or '').strip() for w in words if (w.get('category') or '').strip()})
    print(f"wrote {out_path} with {len(words)} word cards, {n_cats} categories")


if __name__ == '__main__':
    main()
