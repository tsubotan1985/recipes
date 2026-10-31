#!/usr/bin/env python3
"""レシピ Markdown → 静的サイト (docs/) ビルダー。

依存パッケージなし (python3 stdlib のみ)。

  python3 tools/build_site.py            # docs/ を生成
  python3 tools/build_site.py --serve    # 生成して http://localhost:8080 で確認

各レシピ .md の冒頭に次の HTML コメントでメタ情報を書ける (GitHub 上では非表示):

<!--
category: 中華
servings: 2人分
tags: 中華, 炒め物, カシューナッツ
summary: 一覧カードに出す短い説明 (省略時は本文冒頭)
-->
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
RECDIR = DOCS / "r"

CATEGORY_ORDER = ["和食", "中華", "洋食", "麺", "その他"]
CATEGORY_MARK = {"和食": "🍚", "中華": "🥢", "洋食": "🍷", "麺": "🍜", "その他": "🍳"}

BULLET_RE = re.compile(r"^(\s*)[-*]\s+(.*)$")
ORDERED_RE = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
H_RE = re.compile(r"^(#{1,4})\s+(.*)$")


# ---------------------------------------------------------------- utilities


def inline(text: str) -> str:
    """行内 Markdown (bold / link / code) → HTML。エスケープが先。"""
    s = html.escape(text.strip(), quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        s,
    )
    return s


def strip_number(title: str) -> str:
    return re.sub(r"^\s*(?:[0-9０-９]+|[A-Z])\s*[.．、)]\s*", "", title).strip()


def split_meta(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r"\A\ufeff?\s*<!--(.*?)-->\s*", text, re.S)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip()
    return meta, text[m.end():]


def blocks_html(lines: list[str], *, in_step: bool = False) -> str:
    """段落 / 箇条書き / 引用 / ※注記 の混在ブロックを HTML にする。"""
    out: list[str] = []
    para: list[str] = []
    lst: str | None = None  # 'ul' | 'ol'

    def flush_para() -> None:
        nonlocal para
        if not para:
            return
        body = "<br>".join(inline(x) for x in para if x.strip())
        if body:
            cls = ' class="note"' if para[0].lstrip().startswith(("※", "＊")) else ""
            out.append(f"<p{cls}>{body}</p>")
        para = []

    def flush_list() -> None:
        nonlocal lst
        if lst:
            out.append(f"</{lst}>")
            lst = None

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            flush_list()
            continue
        if line.lstrip().startswith("> "):
            flush_para()
            flush_list()
            quote = [line.lstrip()[2:]]
            out.append(f'<aside class="callout">{inline(" ".join(quote))}</aside>')
            continue
        if re.fullmatch(r"\s*(-{3,}|\*{3,})\s*", line):
            flush_para()
            flush_list()
            continue
        b = BULLET_RE.match(line)
        o = ORDERED_RE.match(line)
        m_li = b or o
        if m_li:
            flush_para()
            indent = len(m_li.group(1))
            kind = "ul" if b else "ol"
            if indent >= 2 and lst:
                out.append("<li class=\"sub\">" + inline(m_li.group(2)) + "</li>")
                continue
            if lst != kind:
                flush_list()
                out.append(f'<{kind} class="mini">')
                lst = kind
            out.append("<li>" + inline(m_li.group(2)) + "</li>")
            continue
        if line.lstrip().startswith(("**【", "**")):
            if line.lstrip().endswith("】**") or re.fullmatch(r"\s*\*\*.+\*\*\s*", line):
                flush_para()
                flush_list()
                out.append(f'<p class="subhead">{inline(line)}</p>')
                continue
        flush_list()
        para.append(line.strip())
    flush_para()
    flush_list()
    return "\n".join(out)


# ------------------------------------------------------------------ parsing


def parse_ingredient(text: str) -> dict[str, str]:
    item = {"name": "", "amount": "", "note": ""}
    m = re.match(r"^\*\*(.+?)\*\*(.*)$", text)
    if m:
        item["name"] = m.group(1).strip()
        rest = m.group(2)
    else:
        rest = text
    m2 = re.match(r"^\s*[:：]\s*(.*)$", rest)
    if m2:
        amount = m2.group(1)
    else:
        m3 = re.match(r"^(.*?)\s*[:：]\s*(.*)$", rest)
        if m3:
            item["name"] = (item["name"] + m3.group(1)).strip()
            amount = m3.group(2)
        else:
            amount = rest
    amount = amount.strip()
    m4 = re.match(r"^(.*?)\s*[（(]\s*(.+?)\s*[）)]\s*$", amount)
    if m4 and m4.group(1).strip():
        amount, item["note"] = m4.group(1).strip(), m4.group(2).strip()
    item["amount"] = amount
    return item


def parse_materials(lines: list[str]) -> tuple[list[dict], list[str]]:
    groups: list[dict] = [{"name": "", "items": []}]
    notes: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or re.fullmatch(r"\s*-{3,}\s*", line):
            continue
        h = H_RE.match(line)
        if h:
            groups.append({"name": h.group(2).strip(), "items": []})
            continue
        b = BULLET_RE.match(line)
        if b:
            body = b.group(2).strip()
            if body.startswith("※"):
                notes.append(body)
                continue
            groups[-1]["items"].append(parse_ingredient(body))
            continue
        if groups[-1]["items"]:
            groups[-1]["items"][-1]["note"] = (
                groups[-1]["items"][-1]["note"] + " " + line.strip()
            ).strip()
    return [g for g in groups if g["items"]], notes


def parse_steps(lines: list[str]) -> list[dict]:
    steps: list[dict] = []
    cur: dict | None = None
    ordered_style = any(ORDERED_RE.match(l) for l in lines) and not any(
        H_RE.match(l) and H_RE.match(l).group(1) == "###" for l in lines
    )
    for raw in lines:
        line = raw.rstrip()
        h = H_RE.match(line)
        if h and len(h.group(1)) == 3:
            cur = {"title": strip_number(h.group(2)), "lines": []}
            steps.append(cur)
            continue
        if ordered_style:
            o = ORDERED_RE.match(line)
            if o:
                cur = {"title": strip_number(o.group(2)), "lines": []}
                steps.append(cur)
                continue
            if cur is not None:
                cur["lines"].append(line)
                continue
        if cur is None:
            if not line.strip():
                continue
            cur = {"title": "", "lines": []}
            steps.append(cur)
        cur["lines"].append(line)
    for s in steps:
        s["title"] = s["title"].replace("**", "").strip()
        s["html"] = blocks_html(s["lines"])
        del s["lines"]
    return [s for s in steps if s["html"] or s["title"]]


def kv_items(lines: list[str]) -> list[dict[str, str]]:
    items = []
    for raw in lines:
        b = BULLET_RE.match(raw)
        if not b:
            continue
        body = b.group(2).strip()
        m = re.match(r"^\*\*(.+?)\*\*\s*[:：]\s*(.*)$", body)
        if m:
            items.append({"k": m.group(1).strip(), "v": m.group(2).strip()})
        else:
            items.append({"k": "", "v": body})
    return items


SECTION_KINDS = (
    ("材料", "materials"),
    ("手順", "steps"),
    ("作り方", "steps"),
    ("調理手順", "steps"),
    ("特徴", "features"),
    ("コンセプト", "features"),
    ("ポイント", "tips"),
    ("コツ", "tips"),
    ("おすすめの食べ方", "tips"),
    ("備考", "notes"),
    ("メモ", "notes"),
)


def read_recipe(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta, body = split_meta(text)
    lines = body.splitlines()

    title = ""
    lead: list[str] = []
    sections: list[dict] = []
    cur: dict | None = None
    in_lead = True

    for raw in lines:
        line = raw.rstrip()
        h = H_RE.match(line)
        if h and len(h.group(1)) == 1 and not title:
            title = h.group(2).strip().replace("**", "")
            continue
        if h and len(h.group(1)) == 2:
            in_lead = False
            cur = {"title": h.group(2).strip(), "lines": []}
            sections.append(cur)
            continue
        if in_lead:
            lead.append(line)
            continue
        if cur is not None:
            cur["lines"].append(line)

    parsed: list[dict] = []
    for sec in sections:
        kind = "extra"
        for key, k in SECTION_KINDS:
            if key in sec["title"]:
                kind = k
                break
        entry = {"title": sec["title"], "kind": kind, "sections": sec["lines"]}
        if kind == "materials":
            entry["groups"], entry["notes"] = parse_materials(sec["lines"])
        elif kind == "steps":
            entry["steps"] = parse_steps(sec["lines"])
        elif kind in ("features", "tips"):
            entry["items"] = kv_items(sec["lines"])
            entry["html"] = blocks_html(sec["lines"]) if not entry["items"] else ""
        else:
            entry["html"] = blocks_html(sec["lines"])
        parsed.append(entry)

    return {
        "slug": re.sub(r"[^a-z0-9-]+", "-", path.stem.lower()).strip("-"),
        "file": path.name,
        "title": title or meta.get("title", path.stem),
        "meta": meta,
        "lead": [l.strip() for l in lead if l.strip() and not re.fullmatch(r"-{3,}", l.strip())],
        "sections": parsed,
    }


# ----------------------------------------------------------------- rendering


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def page(title: str, desc: str, body: str, *, root: str, extra_head: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<link rel="stylesheet" href="{root}assets/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🍳</text></svg>">
{extra_head}</head>
<body>
{body}
<script src="{root}assets/app.js"></script>
</body>
</html>
"""


def render_index(recipes: list[dict]) -> str:
    cats = [c for c in CATEGORY_ORDER if any(r["category"] == c for r in recipes)]
    chips = ['<button class="chip is-active" data-filter="all">すべて<span class="chip-n">'
             f'{len(recipes)}</span></button>']
    for c in cats:
        n = sum(1 for r in recipes if r["category"] == c)
        chips.append(
            f'<button class="chip" data-filter="{esc(c)}">{CATEGORY_MARK.get(c, "")} {esc(c)}'
            f'<span class="chip-n">{n}</span></button>'
        )

    cards = []
    for i, r in enumerate(recipes, 1):
        tags = "".join(f'<span class="tag">#{esc(t)}</span>' for t in r["tags"])
        cards.append(
            f"""<li class="card" data-cat="{esc(r['category'])}" data-search="{esc(r['search'])}">
  <a class="card-link" href="r/{r['slug']}.html">
    <span class="card-head">
      <span class="card-no">{i:02d}</span>
      <span class="card-cat">{CATEGORY_MARK.get(r['category'], '')} {esc(r['category'])}</span>
    </span>
    <h2 class="card-title">{esc(r['title'])}</h2>
    <p class="card-desc">{esc(r['summary'])}</p>
    <span class="card-foot">
      <span class="card-serv">{esc(r['servings'])}</span>
      <span class="card-tags">{tags}</span>
    </span>
  </a>
</li>"""
        )

    body = f"""<header class="hero">
  <p class="kicker">RECIPES</p>
  <h1 class="hero-title">うちのレシピ</h1>
  <p class="hero-lede">日々のごはんの記録。作ってみて良かった料理を、材料と手順のかたちで残しています。</p>
  <div class="hero-meta"><span>{len(recipes)} 品</span><span>最終更新 <time>{esc(TODAY)}</time></span></div>
</header>

<div class="toolbar">
  <div class="search-wrap">
    <label class="visually-hidden" for="q">レシピを検索</label>
    <input id="q" class="search" type="search" placeholder="料理名・材料・タグで絞り込み" autocomplete="off">
  </div>
  <div class="chips">{''.join(chips)}</div>
</div>

<main>
  <ul class="cards" id="cards">
{chr(10).join(cards)}
  </ul>
  <p class="empty" id="empty" hidden>該当するレシピがありません。</p>
</main>

<footer class="site-foot">
  <p>レシピは <a href="https://github.com/tsubotan1985/recipes">GitHub</a> の Markdown が原本です。</p>
</footer>
"""
    return page("うちのレシピ", "家庭料理のレシピ集。材料と手順をまとめています。", body, root="")


def render_recipe(r: dict, prev: dict | None, nxt: dict | None) -> str:
    lead = "".join(f"<p>{inline(p)}</p>" for p in r["lead"])

    materials = ""
    for sec in r["sections"]:
        if sec["kind"] != "materials":
            continue
        for g in sec["groups"]:
            rows = []
            for it in g["items"]:
                note = f'<span class="ing-note">{inline(it["note"])}</span>' if it["note"] else ""
                rows.append(
                    f'<li class="ing"><label><input type="checkbox" class="ing-check">'
                    f'<span class="ing-name">{inline(it["name"])}</span>'
                    f'<span class="ing-amt">{inline(it["amount"])}</span>{note}</label></li>'
                )
            head = f'<h3 class="ing-group">{inline(g["name"])}</h3>' if g["name"] else ""
            materials += f'<div class="ing-block">{head}<ul class="ings">{"".join(rows)}</ul></div>'
        for n in sec.get("notes", []):
            materials += f'<p class="ing-xs">{inline(n)}</p>'

    steps_html = ""
    for sec in r["sections"]:
        if sec["kind"] != "steps":
            continue
        for i, s in enumerate(sec["steps"], 1):
            steps_html += f"""<li class="step">
  <span class="step-no">{i}</span>
  <div class="step-body">
    <h3 class="step-title">{inline(s['title'])}</h3>
    {s['html']}
  </div>
</li>"""

    extras = ""
    for sec in r["sections"]:
        if sec["kind"] in ("materials", "steps"):
            continue
        if sec["kind"] in ("features", "tips") and sec.get("items"):
            lis = "".join(
                f'<li><span class="kv-k">{inline(it["k"])}</span>'
                f'<span class="kv-v">{inline(it["v"])}</span></li>'
                for it in sec["items"]
            )
            extras += f"""<section class="panel">
  <h2 class="panel-title">{esc(sec['title'])}</h2>
  <ul class="kv">{lis}</ul>
</section>"""
        else:
            inner = sec.get("html", "")
            if not inner.strip():
                continue
            extras += f"""<section class="panel">
  <h2 class="panel-title">{esc(sec['title'])}</h2>
  <div class="prose">{inner}</div>
</section>"""

    nav = []
    if prev:
        nav.append(f'<a class="pn" href="{prev["slug"]}.html"><span>前</span>{esc(prev["title"])}</a>')
    if nxt:
        nav.append(f'<a class="pn pn-next" href="{nxt["slug"]}.html"><span>次</span>{esc(nxt["title"])}</a>')
    nav_html = f'<nav class="pager">{"".join(nav)}</nav>' if nav else ""

    tags = "".join(f'<span class="tag">#{esc(t)}</span>' for t in r["tags"])
    anchors = ""
    if materials:
        anchors += '<a href="#ingredients">材料</a>'
    if steps_html:
        anchors += '<a href="#steps">作り方</a>'
    if extras:
        anchors += '<a href="#notes">メモ</a>'

    body = f"""<nav class="topbar">
  <a class="back" href="../index.html">← レシピ一覧</a>
  <div class="topbar-anchors">{anchors}</div>
  <button class="print-btn" type="button" data-print>印刷</button>
</nav>

<header class="r-head">
  <p class="kicker">{CATEGORY_MARK.get(r['category'], '')} {esc(r['category'])} · {esc(r['servings'])}</p>
  <h1 class="r-title">{esc(r['title'])}</h1>
  <div class="r-lead">{lead}</div>
  <div class="r-tags">{tags}</div>
</header>

<main class="r-grid">
  <aside class="ing-col" id="ingredients">
    <h2 class="col-title">材料</h2>
    {materials or '<p class="muted">材料の記載がありません。</p>'}
  </aside>
  <section class="step-col" id="steps">
    <h2 class="col-title">作り方</h2>
    <ol class="steps">{steps_html or '<p class="muted">手順の記載がありません。</p>'}</ol>
  </section>
</main>

{extras.replace('<section class="panel">', '<section class="panel" id="notes">') if extras else ''}

{nav_html}

<footer class="site-foot">
  <p>原本: <a href="https://github.com/tsubotan1985/recipes/blob/main/{esc(r['file'].replace('−','-'))}">{esc(r['file'])}</a>
  　<a href="../index.html">レシピ一覧へ</a></p>
</footer>
"""
    desc = r["summary"]
    return page(f"{r['title']}｜うちのレシピ", desc, body, root="../")


# --------------------------------------------------------------------- main


def render_404(recipes: list[dict]) -> str:
    links = "".join(
        f'<li><a href="r/{r["slug"]}.html">{esc(r["title"])}</a></li>' for r in recipes[:7]
    )
    body = f"""<header class="hero">
  <p class="kicker">404</p>
  <h1 class="hero-title">ページが見つかりません</h1>
  <p class="hero-lede">お探しのレシピは移動したか、まだ書かれていないようです。</p>
</header>
<main>
  <ul class="cards"><li class="card" style="border-top-color:var(--accent)">
    <div class="card-link">
      <h2 class="card-title">レシピ一覧</h2>
      <ul class="mini">{links}</ul>
      <p><a class="back" href="index.html">← トップへ戻る</a></p>
    </div>
  </li></ul>
</main>
"""
    return page("ページが見つかりません｜うちのレシピ", "404", body, root="")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    args = ap.parse_args()

    global TODAY
    import datetime

    TODAY = datetime.date.today().isoformat()

    files = sorted(p for p in ROOT.glob("*.md") if p.name.lower() != "readme.md")
    if not files:
        print("レシピ .md が見つかりません", file=sys.stderr)
        return 1

    recipes = [read_recipe(p) for p in files]
    for r in recipes:
        m = r["meta"]
        r["category"] = m.get("category", "その他")
        r["servings"] = m.get("servings", "")
        r["tags"] = [t.strip() for t in re.split(r"[,、/]", m.get("tags", "")) if t.strip()]
        first = r["lead"][0] if r["lead"] else ""
        r["summary"] = m.get("summary") or (first[:110] + ("…" if len(first) > 110 else ""))
        ing = " ".join(
            it["name"]
            for sec in r["sections"]
            if sec["kind"] == "materials"
            for g in sec["groups"]
            for it in g["items"]
        )
        r["search"] = " ".join([r["title"], r["category"], " ".join(r["tags"]), ing])

    recipes.sort(key=lambda r: (CATEGORY_ORDER.index(r["category"]) if r["category"] in CATEGORY_ORDER else 99, r["title"]))

    RECDIR.mkdir(parents=True, exist_ok=True)
    for old in RECDIR.glob("*.html"):
        old.unlink()
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    (DOCS / "index.html").write_text(render_index(recipes), encoding="utf-8")
    (DOCS / "404.html").write_text(render_404(recipes), encoding="utf-8")

    for i, r in enumerate(recipes):
        prev = recipes[i - 1] if i > 0 else None
        nxt = recipes[i + 1] if i < len(recipes) - 1 else None
        (RECDIR / f"{r['slug']}.html").write_text(render_recipe(r, prev, nxt), encoding="utf-8")

    # 元ファイル名の全角マイナス等でリンクが壊れないよう、実ファイル名を控える
    print(f"生成: {len(recipes)} レシピ → {DOCS.relative_to(ROOT)}/")
    for r in recipes:
        print(f"  {r['category']:2s} {r['slug']:24s} {r['title']}")

    if args.serve:
        import http.server
        import socketserver
        import functools

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
        with socketserver.TCPServer(("127.0.0.1", 8099), handler) as httpd:
            print("http://localhost:8099 で配信中 (Ctrl-C で終了)")
            httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
