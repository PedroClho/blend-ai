#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera docs/apresentacao-blend-ai.html a partir de docs/apresentacao-conteudo.md.

O CONTEUDO (textos) mora no .md; o VISUAL/CSS e fiel ao deck e mora aqui.
Fluxo: edite docs/apresentacao-conteudo.md e rode:

    python scripts/gera_slides.py

Marcacao simples aceita dentro dos textos do .md:
    **negrito**        -> <b>negrito</b>
    [palavra](brand)   -> destaque colorido (brand, bad, ok, brand-deep, drums, other, vocal, ink...)
    //                 -> quebra de linha (<br>)
Listas: campo terminado em ":" seguido de linhas "- ...". Colunas separadas por "|".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "docs" / "apresentacao-conteudo.md"
OUT = ROOT / "docs" / "apresentacao-blend-ai.html"

KNOWN_COLORS = {
    "brand", "brand-deep", "bad", "ok", "warn", "other", "drums", "bass",
    "vocal", "ink", "ink-soft", "ink-faint",
}

FOOT = ('<footer class="foot"><span class="wm">Blend<b>AI</b></span>'
        '<span class="microlabel">PAV · UFG</span></footer>')


# ── marcacao inline ─────────────────────────────────────────────────────────
def inline(s) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    # & literal -> &amp; (preserva entidades existentes &nbsp; &#8202; etc.)
    s = re.sub(r"&(?!#?\w+;)", "&amp;", s)

    def _col(m):
        txt, color = m.group(1), m.group(2)
        if color in KNOWN_COLORS:
            return f'<span style="color:var(--{color})">{txt}</span>'
        return m.group(0)

    s = re.sub(r"\[(.+?)\]\(([a-z-]+)\)", _col, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\s*//\s*", "<br>", s)
    return s


def pipe(s, n):
    parts = [x.strip() for x in str(s).split("|")]
    while len(parts) < n:
        parts.append("")
    return parts[:n]


def pipe2(s):
    return pipe(s, 2)


def pipe3(s):
    return pipe(s, 3)


# ── parser do .md ───────────────────────────────────────────────────────────
def parse(md: str) -> dict:
    slides: dict = {}
    cur = None
    listkey = None
    for raw in md.splitlines():
        line = raw.rstrip()
        m = re.match(r"^##\s*slide\s*(\d+)", line)
        if m:
            cur = {}
            slides["s" + m.group(1)] = cur
            listkey = None
            continue
        if cur is None:
            continue
        if listkey and line.lstrip().startswith("- "):
            cur[listkey].append(line.lstrip()[2:].strip())
            continue
        m = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2)
            if val == "":
                cur[key] = []
                listkey = key
            else:
                cur[key] = val
                listkey = None
            continue
        if line.strip() == "":
            listkey = None
    return slides


def g(d, k, default=""):
    return d.get(k, default)


# ── icones fixos do slide 5 ─────────────────────────────────────────────────
ICON_STEMS = '''<div style="display:flex; gap:5px; height:46px; align-items:flex-end; margin-bottom:18px">
            <span style="width:13px;height:70%;background:var(--vocal);border-radius:3px"></span>
            <span style="width:13px;height:100%;background:var(--drums);border-radius:3px"></span>
            <span style="width:13px;height:45%;background:var(--bass);border-radius:3px"></span>
            <span style="width:13px;height:85%;background:var(--other);border-radius:3px"></span>
          </div>'''

ICON_BEAT = '''<svg width="170" height="46" style="margin-bottom:18px" aria-hidden="true">
            <g stroke="var(--ink-soft)" stroke-width="2">
              <line x1="4" y1="14" x2="4" y2="42"/><line x1="26" y1="24" x2="26" y2="42"/>
              <line x1="48" y1="24" x2="48" y2="42"/><line x1="70" y1="24" x2="70" y2="42"/>
              <line x1="92" y1="14" x2="92" y2="42" stroke="var(--brand)"/><line x1="114" y1="24" x2="114" y2="42"/>
              <line x1="136" y1="24" x2="136" y2="42"/><line x1="158" y1="24" x2="158" y2="42"/>
            </g>
            <circle cx="4" cy="10" r="4" fill="var(--brand)"/><circle cx="92" cy="10" r="4" fill="var(--brand)"/>
          </svg>'''

ICON_CAMELOT = '''<svg width="58" height="58" viewBox="0 0 58 58" style="margin-bottom:10px" aria-hidden="true">
            <circle cx="29" cy="29" r="26" fill="none" stroke="var(--line)" stroke-width="2"/>
            <g fill="var(--ink-faint)">
              <circle cx="29" cy="6" r="2.4"/><circle cx="40.5" cy="9.1" r="2.4"/><circle cx="49" cy="17.5" r="2.4"/>
              <circle cx="52" cy="29" r="2.4"/><circle cx="49" cy="40.5" r="2.4"/><circle cx="40.5" cy="49" r="2.4"/>
              <circle cx="29" cy="52" r="2.4"/><circle cx="17.5" cy="49" r="2.4"/><circle cx="9" cy="40.5" r="2.4"/>
            </g>
            <g fill="var(--brand)">
              <circle cx="6" cy="29" r="3.4"/><circle cx="9" cy="17.5" r="3.4"/><circle cx="17.5" cy="9.1" r="3.4"/>
            </g>
            <text x="29" y="33" text-anchor="middle" font-family="var(--font-mono)" font-size="11" font-weight="600" fill="var(--ink)">8A</text>
          </svg>'''


# ── renderizadores por slide ────────────────────────────────────────────────
def s1(d):
    return f'''  <section class="slide" id="s1">
    <div class="body" style="justify-content:center">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h1 class="display anim d1">Blend<b>&#8202;AI</b></h1>
      <p class="lead anim d2" style="margin-top:26px; max-width:52ch">
        {inline(g(d,'lead'))}
      </p>
      <div class="anim d3" style="margin-top:38px; display:flex; gap:6px; max-width:600px; height:34px">
        <div class="seg" style="flex:3"></div>
        <div class="seg verso" style="flex:3"></div>
        <div class="seg build" style="flex:2.2"></div>
        <div class="seg drop" style="flex:3"></div>
        <div class="seg verso" style="flex:6"></div>
        <div class="seg build" style="flex:2.2"></div>
        <div class="seg drop" style="flex:3"></div>
        <div class="seg" style="flex:1.6"></div>
      </div>
    </div>
    <footer class="foot">
      <span class="wm">Blend<b>AI</b></span>
      <span class="microlabel">{inline(g(d,'rodape'))}</span>
    </footer>
  </section>
'''


def s2(d):
    chips = ""
    for it in g(d, "itens", []):
        cor, label, resto = pipe3(it)
        chips += (f'            <div class="chip" style="font-size:15px; padding:11px 16px">'
                  f'<span class="dot" style="background:var(--{cor})"></span>&nbsp;'
                  f'<b style="font-family:var(--font-sans)">{inline(label)}</b>&nbsp;{inline(resto)}</div>\n')
    return f'''  <section class="slide" id="s2">
    <div class="body">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h2 class="title anim d1">{inline(g(d,'titulo'))}</h2>
      <div style="display:flex; gap:54px; margin-top:34px; flex:1">
        <div class="anim d2" style="flex:1.05; display:flex; flex-direction:column; gap:20px">
          <p class="lead" style="max-width:none">
            {inline(g(d,'lead'))}
          </p>
          <div style="display:flex; flex-direction:column; gap:12px">
{chips}          </div>
        </div>
        <div class="anim d3" style="flex:.95; display:flex; align-items:center; justify-content:center; gap:18px">
          <div style="text-align:center">
            <div style="width:150px;height:150px;border-radius:18px;background:linear-gradient(135deg,#F3F0FF,#C4BBFD)"></div>
            <div class="microlabel" style="margin-top:10px; color:var(--vocal)">{inline(g(d,'labelA'))}</div>
          </div>
          <div style="font-family:var(--font-display);font-size:40px;color:var(--brand);font-weight:700">+</div>
          <div style="text-align:center">
            <div style="width:150px;height:150px;border-radius:18px;background:linear-gradient(135deg,#FFF7ED,#FDBA74)"></div>
            <div class="microlabel" style="margin-top:10px; color:var(--drums)">{inline(g(d,'labelB'))}</div>
          </div>
        </div>
      </div>
      <p class="lead anim d4" style="max-width:none; margin-bottom:26px">{inline(g(d,'fechamento'))}</p>
    </div>
    {FOOT}
  </section>
'''


def s3(d):
    return f'''  <section class="slide" id="s3">
    <div class="body">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h2 class="title anim d1">{inline(g(d,'titulo'))}</h2>
      <p class="lead anim d2" style="margin-top:22px; max-width:none">
        {inline(g(d,'lead'))}
      </p>
      <div class="card anim d3" style="margin-top:30px; padding:30px 34px">
        <div class="microlabel" style="margin-bottom:16px">{inline(g(d,'hipotese_label'))}</div>
        <p style="font-size:27px; line-height:1.4; color:var(--ink); font-weight:500; max-width:46ch">
          {inline(g(d,'hipotese'))}
        </p>
      </div>
      <p class="lead anim d4" style="max-width:none; margin-top:auto; margin-bottom:26px; font-size:19px">
        {inline(g(d,'fechamento'))}
      </p>
    </div>
    {FOOT}
  </section>
'''


def s4(d):
    an = ""
    for it in g(d, "nodes_analise", []):
        t, sub, tool = pipe3(it)
        subhtml = f"<span>{inline(sub)}</span>" if sub.strip() else ""
        an += (f'            <div class="node">{inline(t)}{subhtml}'
               f'<i class="microlabel">{inline(tool)}</i></div>\n')
    co = ""
    for it in g(d, "nodes_contrib", []):
        co += (f'            <div class="node star-node">'
               f'<span class="star" style="margin-bottom:8px">★</span>{inline(it)}</div>\n')
    st, ss, stool = pipe3(g(d, "node_sintese"))
    sthtml = f"<span>{inline(ss)}</span>" if ss.strip() else ""
    return f'''  <section class="slide" id="s4">
    <div class="body">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h2 class="title anim d1" style="font-size:42px">{inline(g(d,'titulo'))}</h2>

      <div class="anim d2" style="margin-top:38px; display:flex; align-items:stretch; gap:10px">
        <div style="flex:4; display:flex; flex-direction:column; gap:10px">
          <div class="microlabel" style="text-align:center">{inline(g(d,'grupo_analise'))}</div>
          <div style="display:flex; gap:10px">
{an}          </div>
        </div>
        <div style="display:flex;align-items:center;color:var(--ink-faint);font-size:22px">›</div>
        <div style="flex:2; display:flex; flex-direction:column; gap:10px">
          <div class="microlabel" style="text-align:center; color:var(--brand-deep)">{inline(g(d,'grupo_contrib'))}</div>
          <div style="display:flex; gap:10px">
{co}          </div>
        </div>
        <div style="display:flex;align-items:center;color:var(--ink-faint);font-size:22px">›</div>
        <div style="flex:1; display:flex; flex-direction:column; gap:10px">
          <div class="microlabel" style="text-align:center">{inline(g(d,'grupo_sintese'))}</div>
          <div class="node">{inline(st)}{sthtml}<i class="microlabel">{inline(stool)}</i></div>
        </div>
      </div>

      <p class="lead anim d3" style="max-width:none; margin-top:34px; font-size:19px">
        {inline(g(d,'fechamento'))}
      </p>
    </div>
    {FOOT}
  </section>
'''


def s5(d):
    icons = [ICON_STEMS, ICON_BEAT, ICON_CAMELOT]
    delays = ["d2", "d3", "d4"]
    cards = ""
    for i, it in enumerate(g(d, "conceitos", [])[:3]):
        t, texto = pipe2(it)
        cards += f'''        <div class="card anim {delays[i]}" style="flex:1; padding:26px 24px; display:flex; flex-direction:column">
          {icons[i]}
          <div style="font-family:var(--font-display);font-weight:700;font-size:21px;margin-bottom:10px">{inline(t)}</div>
          <p style="font-size:16px;line-height:1.45;color:var(--ink-soft)">{inline(texto)}</p>
        </div>
'''
    return f'''  <section class="slide" id="s5">
    <div class="body">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h2 class="title anim d1" style="font-size:42px">{inline(g(d,'titulo'))}</h2>
      <div style="display:flex; gap:22px; margin-top:38px; flex:1">
{cards}      </div>
    </div>
    {FOOT}
  </section>
'''


def _lanes6(a_break, a_drop, b_break, b_drop, good, tA, tB, guides):
    cls = "cmp good" if good else "cmp"
    return f'''          <div class="lanes">
            <div class="lane"><span class="trk-lab">{tA}</span>
              <div class="blk break" style="left:{a_break[0]}%;width:{a_break[1]}%">break</div>
              <div class="blk drop"  style="left:{a_drop[0]}%;width:{a_drop[1]}%">drop</div>
            </div>
            <div class="lane"><span class="trk-lab">{tB}</span>
              <div class="blk break" style="left:{b_break[0]}%;width:{b_break[1]}%">break</div>
              <div class="blk drop"  style="left:{b_drop[0]}%;width:{b_drop[1]}%">drop</div>
            </div>
{guides}          </div>'''


def s6(d):
    tA = inline(g(d, "trackA", "A · vocal"))
    tB = inline(g(d, "trackB", "B · base"))
    gb = inline(g(d, "guide_break", "break ↔ break"))
    gd = inline(g(d, "guide_drop", "drop ↔ drop"))
    # baseline: B deslocado -> fora de fase
    base_guides = (
        '            <div class="guide miss" style="left:24%"></div>\n'
        '            <div class="guide miss" style="left:70%"></div>\n'
        '            <span class="guide-lab" style="left:70%;color:var(--bad)">✗ fora de fase</span>\n'
    )
    base_lanes = _lanes6((14, 20), (58, 24), (28, 20), (72, 24), False, tA, tB, base_guides)
    # proposto: B alinhado -> as duas explodem juntas
    good_guides = (
        '            <div class="guide" style="left:24%"></div>\n'
        '            <div class="guide" style="left:70%"></div>\n'
        f'            <span class="guide-lab" style="left:24%">{gb}</span>\n'
        f'            <span class="guide-lab" style="left:70%">{gd}</span>\n'
    )
    good_lanes = _lanes6((14, 20), (58, 24), (14, 20), (58, 24), True, tA, tB, good_guides)
    return f'''  <section class="slide" id="s6">
    <div class="body">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h2 class="title anim d1" style="font-size:42px">{inline(g(d,'titulo'))}</h2>
      <p class="lead anim d2" style="max-width:none; margin-top:18px; font-size:19px">{inline(g(d,'lead'))}</p>

      <div class="anim d3" style="margin-top:24px; display:flex; flex-direction:column; gap:18px; flex:1; justify-content:center">
        <div class="cmp">
          <div class="cmp-head">
            <span class="chip" style="border-color:#f3c2c2;color:var(--bad)">{inline(g(d,'baseline_tag'))}</span>
            <span class="cmp-note">{inline(g(d,'baseline_caption'))}</span>
          </div>
{base_lanes}
        </div>
        <div class="cmp good">
          <div class="cmp-head">
            <span class="chip" style="border-color:#cfcafb;color:var(--brand-deep)"><span class="star" style="width:18px;height:18px;font-size:11px">★</span>&nbsp;{inline(g(d,'proposto_tag'))}</span>
            <span class="cmp-note">{inline(g(d,'proposto_caption'))}</span>
          </div>
{good_lanes}
        </div>
      </div>
    </div>
    {FOOT}
  </section>
'''


def s7(d):
    delays = ["d2", "d3", "d4"]
    rows = ""
    for i, it in enumerate(g(d, "hipoteses", [])[:3]):
        tag, dest, resto, chip, cor = pipe(it, 5)
        rows += f'''        <div class="card anim {delays[i]}" style="padding:22px 28px; display:flex; align-items:center; gap:26px">
          <div style="font-family:var(--font-display);font-weight:800;font-size:34px;color:var(--brand);width:62px;flex:none">{inline(tag)}</div>
          <div style="flex:1"><b style="font-size:19px">{inline(dest)}</b> {inline(resto)}</div>
          <span class="chip" style="flex:none"><span class="dot" style="background:var(--{cor or 'brand'})"></span>&nbsp;{inline(chip)}</span>
        </div>
'''
    return f'''  <section class="slide" id="s7">
    <div class="body">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h2 class="title anim d1" style="font-size:42px">{inline(g(d,'titulo'))}</h2>

      <div style="display:flex; flex-direction:column; gap:16px; margin-top:34px; flex:1; justify-content:center">
{rows}      </div>
      <p class="lead anim d4" style="max-width:none; font-size:18px; margin-bottom:22px">
        {inline(g(d,'fechamento'))}
      </p>
    </div>
    {FOOT}
  </section>
'''


def s8(d):
    syms = [("✓", "ok", "22px"), ("◧", "brand", "20px"), ("♪", "drums", "20px")]
    items = ""
    for i, it in enumerate(g(d, "itens", [])[:3]):
        t, texto = pipe2(it)
        sym, cor, sz = syms[i]
        items += f'''          <div style="display:flex; gap:14px; align-items:flex-start">
            <span style="color:var(--{cor});font-size:{sz};line-height:1">{sym}</span>
            <div><b style="font-size:18px">{inline(t)}</b><br><span style="color:var(--ink-soft);font-size:16px">{inline(texto)}</span></div>
          </div>
'''

    def bars(key, low=False):
        out = ""
        cls = " low" if low else ""
        for it in g(d, key, []):
            lab, val = pipe2(it)
            try:
                w = int(round(float(val) * 100))
            except ValueError:
                w = 0
            out += (f'          <div class="barrow{cls}"><span>{inline(lab)}</span>'
                    f'<div class="track"><i style="width:{w}%"></i></div><b>{inline(val)}</b></div>\n')
        return out

    return f'''  <section class="slide" id="s8">
    <div class="body">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h2 class="title anim d1" style="font-size:42px">{inline(g(d,'titulo'))}</h2>

      <div style="display:flex; gap:30px; margin-top:32px; flex:1">
        <div class="anim d2" style="flex:1.05; display:flex; flex-direction:column; gap:16px">
{items}          <div class="card" style="padding:14px 18px; margin-top:6px; display:flex; align-items:center; gap:12px; background:var(--brand-soft); border-color:#d7d4fb">
            <span class="beat" style="width:30px;height:30px;border-radius:8px;background:var(--brand);color:#fff;display:flex;align-items:center;justify-content:center">▶</span>
            <span style="font-family:var(--font-mono);font-size:13px;color:var(--brand-deep)">{inline(g(d,'callout'))}</span>
          </div>
        </div>

        <div class="card anim d3" style="flex:.95; padding:24px 26px; display:flex; flex-direction:column">
          <div class="microlabel" style="margin-bottom:18px">{inline(g(d,'barras_label'))}</div>
{bars('barras_top')}          <div style="height:1px;background:var(--line);margin:14px 0"></div>
{bars('barras_low', True)}          <p style="font-size:13px;color:var(--ink-faint);margin-top:auto;padding-top:14px">{inline(g(d,'barras_nota'))}</p>
        </div>
      </div>
    </div>
    {FOOT}
  </section>
'''


def s9(d):
    return f'''  <section class="slide" id="s9">
    <div class="body">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h2 class="title anim d1" style="font-size:42px">{inline(g(d,'titulo'))}</h2>

      <div style="display:flex; gap:26px; margin-top:34px; flex:1">
        <div class="card anim d2" style="flex:1; padding:28px 30px; display:flex; flex-direction:column">
          <div class="chip" style="align-self:flex-start; border-color:#cfcafb; color:var(--brand-deep); margin-bottom:18px">{inline(g(d,'card1_tag'))}</div>
          <div style="font-family:var(--font-display);font-weight:700;font-size:23px;line-height:1.2;margin-bottom:14px">{inline(g(d,'card1_titulo'))}</div>
          <p style="font-size:17px;line-height:1.5;color:var(--ink-soft)">
            {inline(g(d,'card1_texto'))}
          </p>
        </div>
        <div class="card anim d3" style="flex:1; padding:28px 30px; display:flex; flex-direction:column">
          <div class="chip" style="align-self:flex-start; border-color:var(--line); color:var(--ink-soft); margin-bottom:18px">{inline(g(d,'card2_tag'))}</div>
          <div style="font-family:var(--font-display);font-weight:700;font-size:23px;line-height:1.2;margin-bottom:14px">{inline(g(d,'card2_titulo'))}</div>
          <p style="font-size:17px;line-height:1.5;color:var(--ink-soft)">
            {inline(g(d,'card2_texto'))}
          </p>
        </div>
      </div>
      <p class="lead anim d4" style="max-width:none; font-size:18px; margin:22px 0 22px">
        {inline(g(d,'fechamento'))}
      </p>
    </div>
    {FOOT}
  </section>
'''


def s10(d):
    cards = ""
    for it in g(d, "cards", []):
        lab, t, sub = pipe3(it)
        cards += f'''        <div class="card anim d3" style="flex:1; padding:22px 24px">
          <div class="microlabel" style="color:var(--brand-deep); margin-bottom:12px">{inline(lab)}</div>
          <div style="font-weight:600; font-size:17px; line-height:1.35">{inline(t)}<br><span style="color:var(--ink-soft);font-weight:400;font-size:15px">{inline(sub)}</span></div>
        </div>
'''
    return f'''  <section class="slide" id="s10">
    <div class="body">
      <div class="kicker anim"><span class="microlabel">{inline(g(d,'kicker'))}</span></div>
      <h2 class="title anim d1">{inline(g(d,'titulo'))}</h2>
      <p class="lead anim d2" style="margin-top:22px; max-width:none">
        {inline(g(d,'lead'))}
      </p>

      <div style="display:flex; gap:18px; margin-top:34px">
{cards}      </div>

      <div class="anim d4" style="margin-top:auto; margin-bottom:24px; display:flex; align-items:baseline; gap:18px">
        <span style="font-family:var(--font-display);font-weight:800;font-size:40px;letter-spacing:-.03em">{inline(g(d,'assinatura'))}</span>
        <span class="microlabel" style="font-size:14px">{inline(g(d,'assinatura_sub'))}</span>
      </div>
    </div>
    <footer class="foot"><span class="wm">Blend<b>AI</b></span><span class="microlabel">PAV · Processamento de Áudio e Voz · UFG</span></footer>
  </section>
'''


RENDER = {f"s{i}": fn for i, fn in enumerate(
    [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10], start=1)}


# ── HEAD (CSS/identidade fiel ao deck) ──────────────────────────────────────
HEAD = '''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blend AI — Apresentação · PAV/UFG</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600;700;800&family=Instrument+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
/* GERADO por scripts/gera_slides.py a partir de docs/apresentacao-conteudo.md.
   Nao edite este arquivo a mao: edite o .md e rode o gerador. */
:root{
  --paper:#fcfcfd; --surface:#f5f6f9; --surface-2:#edeff4; --line:#e4e7ee;
  --ink:#14171f; --ink-soft:#6a7180; --ink-faint:#9aa1ae;
  --brand:#6d5ef6; --brand-deep:#4f46e5; --brand-soft:#eef0fe;
  --vocal:#3b82f6; --drums:#f59e0b; --bass:#ef4444; --other:#10b981;
  --ok:#10b981; --warn:#f59e0b; --bad:#ef4444;
  --font-display:"Unbounded",system-ui,sans-serif;
  --font-sans:"Instrument Sans",system-ui,sans-serif;
  --font-mono:"IBM Plex Mono",ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  background:#0e0f13;
  font-family:var(--font-sans);
  color:var(--ink);
  overflow:hidden;
  -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;
}

/* palco escalado para caber em qualquer tela mantendo 16:9 */
#stage{
  position:absolute; top:50%; left:50%;
  width:1280px; height:720px;
  transform:translate(-50%,-50%);
  transform-origin:center center;
}
.slide{
  position:absolute; inset:0;
  width:1280px; height:720px;
  background:var(--paper);
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.02'/%3E%3C/svg%3E");
  padding:64px 80px 0;
  display:flex; flex-direction:column;
  opacity:0; visibility:hidden;
  transition:opacity .42s cubic-bezier(.2,.7,.2,1);
}
.slide.active{opacity:1; visibility:visible}
.slide.active .anim{animation:fade-up .6s cubic-bezier(.2,.7,.2,1) both}
.slide.active .anim.d1{animation-delay:.06s}
.slide.active .anim.d2{animation-delay:.13s}
.slide.active .anim.d3{animation-delay:.20s}
.slide.active .anim.d4{animation-delay:.27s}
@keyframes fade-up{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}

.body{flex:1; display:flex; flex-direction:column; min-height:0}
.foot{
  height:54px; flex:none;
  display:flex; align-items:center; justify-content:space-between;
  border-top:1px solid var(--line);
  margin-top:auto;
}
.wm{font-family:var(--font-display);font-weight:700;font-size:15px;letter-spacing:-.01em}
.wm b{color:var(--brand);font-weight:800}

/* ── primitivos ─────────────────────────────────────────────────────────── */
.microlabel{
  font-family:var(--font-mono); font-size:11px; font-weight:500;
  letter-spacing:.16em; text-transform:uppercase; color:var(--ink-faint);
}
.kicker{display:inline-flex; align-items:center; gap:11px; margin-bottom:22px}
.kicker::before{content:""; width:26px; height:3px; border-radius:3px; background:var(--brand)}
.kicker .microlabel{color:var(--brand-deep); font-weight:600}

h1.display{
  font-family:var(--font-display); font-weight:800; font-size:118px;
  line-height:.92; letter-spacing:-.04em; color:var(--ink);
}
h1.display b{color:var(--brand)}
h2.title{
  font-family:var(--font-display); font-weight:700; font-size:48px;
  line-height:1.04; letter-spacing:-.025em; color:var(--ink); max-width:21ch;
}
h2.title em{font-style:normal; color:var(--brand)}
.lead{font-size:23px; line-height:1.45; color:var(--ink-soft); max-width:40ch; font-weight:400}
.lead b{color:var(--ink); font-weight:600}

.card{
  background:var(--surface); border:1px solid var(--line); border-radius:16px;
  box-shadow:0 1px 2px rgb(16 24 40/.05), 0 1px 3px rgb(16 24 40/.04);
}
.chip{
  display:inline-flex; align-items:center; gap:7px;
  font-family:var(--font-mono); font-size:12px; font-weight:500;
  padding:5px 11px; border-radius:999px; border:1px solid var(--line);
  background:#fff;
}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}
.stem-vocal{color:var(--vocal)} .bg-vocal{background:var(--vocal)}
.stem-drums{color:var(--drums)} .bg-drums{background:var(--drums)}
.stem-bass{color:var(--bass)}   .bg-bass{background:var(--bass)}
.stem-other{color:var(--other)} .bg-other{background:var(--other)}

.star{
  display:inline-flex; align-items:center; justify-content:center;
  width:24px; height:24px; border-radius:7px; flex:none;
  background:var(--brand); color:#fff; font-size:13px; font-weight:700;
}

/* timeline de estrutura — assinatura visual */
.timeline{display:flex; gap:4px; height:46px}
.seg{
  display:flex; align-items:center; justify-content:center;
  border-radius:8px; background:var(--surface-2);
  font-family:var(--font-mono); font-size:10px; letter-spacing:.04em;
  text-transform:uppercase; color:var(--ink-soft); overflow:hidden; white-space:nowrap;
}
.seg.verso{background:#eef0fe; color:var(--brand-deep)}
.seg.refrao{background:#e6f0ff; color:#1d5fc4}
.seg.drop{background:var(--brand); color:#fff; font-weight:600; box-shadow:0 4px 14px rgb(109 94 246/.35)}
.seg.build{background:repeating-linear-gradient(135deg,#fdecca,#fdecca 4px,#fbe1ad 4px,#fbe1ad 8px); color:#b45309; font-weight:500}

/* ── slide 4 — pipeline ─────────────────────────────────────────────────── */
#s4 .node{flex:1; background:var(--surface); border:1px solid var(--line); border-radius:12px;
  padding:14px 12px 12px; font-size:14px; font-weight:600; line-height:1.25; color:var(--ink);
  display:flex; flex-direction:column; min-height:108px}
#s4 .node span{font-weight:400; color:var(--ink-faint); font-size:12px}
#s4 .node i{font-style:normal; margin-top:auto; padding-top:8px}
#s4 .star-node{background:var(--brand-soft); border-color:#d7d4fb}

/* ── slide 6 — alinhamento das estruturas (break/drop) ──────────────────── */
#s6 .cmp{position:relative; background:var(--surface); border:1px solid var(--line);
  border-radius:14px; padding:14px 26px 26px}
#s6 .cmp.good{background:#fbfbff; border-color:#d7d4fb}
#s6 .cmp-head{display:flex; align-items:center; justify-content:space-between; gap:18px; margin-bottom:12px}
#s6 .cmp-note{font-size:14.5px; line-height:1.35; color:var(--ink-soft); text-align:right; max-width:54ch}
#s6 .lanes{position:relative; margin-left:104px}
#s6 .lane{position:relative; height:30px; margin:8px 0; border-radius:7px;
  background:repeating-linear-gradient(90deg,#e7eaf1,#e7eaf1 2px,transparent 2px,transparent 9px)}
#s6 .cmp.good .lane{background:repeating-linear-gradient(90deg,#e6e3fb,#e6e3fb 2px,transparent 2px,transparent 9px)}
#s6 .trk-lab{position:absolute; right:calc(100% + 14px); top:50%; transform:translateY(-50%);
  white-space:nowrap; font-family:var(--font-mono); font-size:11px; letter-spacing:.04em;
  text-transform:uppercase; color:var(--ink-faint)}
#s6 .blk{position:absolute; top:0; height:30px; border-radius:7px; display:flex; align-items:center;
  justify-content:center; font-family:var(--font-mono); font-size:10px; letter-spacing:.06em;
  text-transform:uppercase}
#s6 .blk.break{background:#e7e4fb; color:var(--brand-deep); box-shadow:inset 0 0 0 1px #d7d4fb}
#s6 .blk.drop{background:var(--brand); color:#fff; font-weight:600; box-shadow:0 4px 14px rgb(109 94 246/.35)}
#s6 .guide{position:absolute; top:-3px; bottom:-3px; width:2px; background:var(--ok); z-index:3; border-radius:2px}
#s6 .guide.miss{background:none; border-left:2px dashed var(--bad); width:0}
#s6 .guide-lab{position:absolute; bottom:-20px; transform:translateX(-50%); white-space:nowrap;
  font-family:var(--font-mono); font-size:10px; letter-spacing:.07em; text-transform:uppercase;
  color:var(--brand-deep)}

/* ── slide 8 — barras de score ──────────────────────────────────────────── */
#s8 .barrow{display:flex; align-items:center; gap:12px; margin-bottom:11px; font-size:13px}
#s8 .barrow span{width:150px; flex:none; color:var(--ink-soft); font-family:var(--font-mono); font-size:11.5px}
#s8 .barrow .track{flex:1; height:13px; background:var(--surface-2); border-radius:7px; overflow:hidden}
#s8 .barrow i{display:block; height:100%; background:var(--brand); border-radius:7px}
#s8 .barrow.low i{background:var(--ink-faint)}
#s8 .barrow b{width:38px; text-align:right; font-family:var(--font-mono); font-size:13px}

/* ── chrome (tela apenas) ───────────────────────────────────────────────── */
#bar{position:fixed; top:0; left:0; height:3px; background:var(--brand); width:10%; z-index:50; transition:width .3s}
#hud{position:fixed; bottom:18px; right:22px; z-index:50; display:flex; align-items:center; gap:14px;
  font-family:var(--font-mono); font-size:12px; color:#8a8f9c}
#hud button{font:inherit; color:#cfd3dc; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14);
  border-radius:8px; padding:5px 10px; cursor:pointer}
#hud button:hover{background:rgba(255,255,255,.14)}
#count{color:#e9ebf0; letter-spacing:.1em}
#hint{position:fixed; bottom:18px; left:50%; transform:translateX(-50%); z-index:50; font-family:var(--font-mono);
  font-size:11px; letter-spacing:.12em; color:#6c7080; text-transform:uppercase; transition:opacity .6s; pointer-events:none}

/* modo limpo: esconde a navegação p/ exportar imagem de cada slide (?clean) */
body.clean #bar, body.clean #hud, body.clean #hint{display:none!important}

/* ── impressão / PDF: cada slide vira uma página ────────────────────────── */
@page{ size:1280px 720px; margin:0 }
@media print{
  body{overflow:visible; background:#fff}
  #stage{position:static; transform:none; width:auto; height:auto}
  .slide{position:relative; inset:auto; opacity:1!important; visibility:visible!important;
    page-break-after:always; transition:none}
  .slide.active .anim, .anim{animation:none!important}
  #bar,#hud,#hint{display:none!important}
}
</style>
</head>
<body>

<div id="bar"></div>
<div id="hud">
  <button data-nonav onclick="prev()">◂</button>
  <span id="count">01 / 10</span>
  <button data-nonav onclick="next()">▸</button>
  <button data-nonav onclick="window.print()" title="Exportar PDF">PDF</button>
</div>
<div id="hint">← → navegar · F tela cheia · P imprimir/pdf</div>

<div id="stage">

'''

# ── TAIL (navegação) ────────────────────────────────────────────────────────
TAIL = '''
</div>

<script>
(function(){
  var STAGE_W=1280, STAGE_H=720;
  var stage=document.getElementById('stage');
  var slides=[].slice.call(document.querySelectorAll('.slide'));
  var bar=document.getElementById('bar'), count=document.getElementById('count'), hint=document.getElementById('hint');
  var idx=0;

  function fit(){
    var s=Math.min(window.innerWidth/STAGE_W, window.innerHeight/STAGE_H);
    stage.style.transform='translate(-50%,-50%) scale('+s+')';
  }
  function show(n){
    idx=Math.max(0, Math.min(slides.length-1, n));
    slides.forEach(function(s,i){ s.classList.toggle('active', i===idx); });
    var t=String(idx+1).padStart(2,'0')+' / '+String(slides.length).padStart(2,'0');
    count.textContent=t;
    bar.style.width=((idx+1)/slides.length*100)+'%';
    if(history.replaceState) history.replaceState(null,'','#'+(idx+1));
  }
  window.next=function(){ show(idx+1); };
  window.prev=function(){ show(idx-1); };

  document.addEventListener('keydown', function(e){
    if(e.key==='ArrowRight'||e.key==='PageDown'||e.key===' '||e.key==='Enter'){ next(); e.preventDefault(); }
    else if(e.key==='ArrowLeft'||e.key==='PageUp'){ prev(); e.preventDefault(); }
    else if(e.key==='Home'){ show(0); }
    else if(e.key==='End'){ show(slides.length-1); }
    else if(e.key==='f'||e.key==='F'){ if(!document.fullscreenElement){document.documentElement.requestFullscreen&&document.documentElement.requestFullscreen();}else{document.exitFullscreen&&document.exitFullscreen();} }
    else if(e.key==='p'||e.key==='P'){ window.print(); }
  });
  document.addEventListener('click', function(e){
    if(e.target.closest('[data-nonav]')) return;
    if(e.clientX < window.innerWidth*0.22) prev(); else next();
  });
  var x0=null;
  document.addEventListener('touchstart', function(e){ x0=e.touches[0].clientX; }, {passive:true});
  document.addEventListener('touchend', function(e){
    if(x0===null) return; var dx=e.changedTouches[0].clientX-x0;
    if(Math.abs(dx)>50){ dx<0?next():prev(); } x0=null;
  });

  window.addEventListener('resize', fit);
  setTimeout(function(){ if(hint) hint.style.opacity='0'; }, 4200);

  if(location.search.indexOf('clean')>=0){ document.body.classList.add('clean'); }
  var start=parseInt((location.hash||'').replace('#',''),10);
  fit(); show(isNaN(start)?0:start-1);
})();
</script>
</body>
</html>
'''


def main():
    if not MD.exists():
        sys.exit(f"conteudo nao encontrado: {MD}")
    data = parse(MD.read_text(encoding="utf-8"))
    body = "".join(RENDER[f"s{i}"](data.get(f"s{i}", {})) for i in range(1, 11))
    OUT.write_text(HEAD + body + TAIL, encoding="utf-8")
    n = len([k for k in data if re.match(r"s\d+$", k)])
    print(f"ok: {n} slides -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
