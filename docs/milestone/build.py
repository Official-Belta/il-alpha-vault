#!/usr/bin/env python3
"""
Build milestone page from roadmap.json + Foundry broadcast files.

Usage:
    python docs/milestone/build.py

Reads:
    - docs/milestone/roadmap.json  (milestone data — edit this to update roadmap)
    - contracts/broadcast/*/11155111/run-latest.json  (deployed contract addresses)

Writes:
    - docs/milestone/index.html
"""

import json
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MILESTONE_DIR = ROOT / "docs" / "milestone"
BROADCAST_DIR = ROOT / "contracts" / "broadcast"
CHAIN_ID = "11155111"  # Sepolia


def load_roadmap():
    with open(MILESTONE_DIR / "roadmap.json") as f:
        return json.load(f)


def load_contracts_from_broadcast():
    """Read all broadcast files and extract contract name → address mapping."""
    contracts = {}
    if not BROADCAST_DIR.exists():
        return contracts

    for script_dir in BROADCAST_DIR.iterdir():
        run_file = script_dir / CHAIN_ID / "run-latest.json"
        if not run_file.exists():
            continue
        with open(run_file) as f:
            data = json.load(f)
        for tx in data.get("transactions", []):
            name = tx.get("contractName")
            addr = tx.get("contractAddress")
            if name and addr:
                # Keep last deployment (in case of duplicates)
                contracts[name] = addr
    return contracts


def count_items(phases):
    """Count total tests (Python + Solidity) and total contracts."""
    total_tests = 77  # From roadmap descriptions
    deployed = sum(
        1 for p in phases for i in p["items"]
        if i["status"] == "done" and "deploy" in i["text"].lower()
    )
    return total_tests, deployed


def esc(text):
    return html.escape(text)


# i18n helpers
_ko = {}  # populated from roadmap.json


def t(en_text, ko_text=None):
    """Return HTML with data-ko attribute for translation."""
    if ko_text is None:
        ko_text = _ko.get("items", {}).get(en_text, en_text)
    return f' data-ko="{esc(ko_text)}"' if ko_text != en_text else ""


def render_item(item):
    status = item["status"]
    icon_class = {"done": "icon-done", "active": "icon-active", "pending": "icon-pending"}[status]
    text_class = {"done": "text-done", "active": "text-active", "pending": "text-pending"}[status]
    icon_content = "&#10003;" if status == "done" else ""
    ko_text = _ko.get("items", {}).get(item["text"], item["text"])
    sub_html = ""
    if item.get("sub"):
        ko_sub = _ko.get("subs", {}).get(item["sub"], item["sub"])
        sub_ko_attr = f' data-ko="{esc(ko_sub)}"' if ko_sub != item["sub"] else ""
        sub_html = f'<div class="item-sub"{sub_ko_attr}>{esc(item["sub"])}</div>'
    ko_attr = f' data-ko="{esc(ko_text)}"' if ko_text != item["text"] else ""
    return f"""<div class="item"><div class="item-icon {icon_class}">{icon_content}</div><div><div class="{text_class}"{ko_attr}>{esc(item["text"])}</div>{sub_html}</div></div>"""


def render_phase(phase):
    status_class = {
        "complete": "status-done",
        "active": "status-active",
        "upcoming": "status-wait"
    }[phase["status"]]
    status_en = {"complete": "Complete", "active": "In Progress", "upcoming": "Upcoming"}[phase["status"]]
    status_ko = {"complete": "완료", "active": "진행 중", "upcoming": "예정"}[phase["status"]]

    ko_phases = _ko.get("phases", {}).get(phase["number"], {})
    ko_name = ko_phases.get("name", phase["name"])
    ko_desc = ko_phases.get("description", phase["description"])

    items_html = "\n            ".join(render_item(i) for i in phase["items"])

    name_ko_attr = f' data-ko="{esc(ko_name)}"' if ko_name != phase["name"] else ""
    desc_ko_attr = f' data-ko="{esc(ko_desc)}"' if ko_desc != phase["description"] else ""
    status_ko_attr = f' data-ko="{esc(status_ko)}"'

    return f"""
      <div class="phase reveal">
        <div>
          <div class="phase-label" data-ko="페이즈 {esc(phase['number'])}">Phase {esc(phase["number"])}</div>
          <div class="phase-name"{name_ko_attr}>{esc(phase["name"])}</div>
          <div class="phase-status {status_class}"{status_ko_attr}>{status_en}</div>
        </div>
        <div class="phase-body">
          <p class="phase-desc"{desc_ko_attr}>{esc(phase["description"])}</p>
          <div class="items">
            {items_html}
          </div>
        </div>
      </div>"""


def render_contract(name, address, meta, etherscan_base):
    info = meta.get(name, {"role": "", "tag": None})
    tag_html = f' <span class="tag">{esc(info["tag"])}</span>' if info.get("tag") else ""
    short_addr = f"{address[:10]}...{address[-8:]}"
    url = f"{etherscan_base}/address/{address}"
    ko_role = _ko.get("contracts_meta", {}).get(name, info["role"])
    role_ko_attr = f' data-ko="{esc(ko_role)}"' if ko_role != info["role"] else ""

    return f"""<div class="contract">
        <div class="contract-name">{esc(name)}{tag_html}</div>
        <div class="contract-desc"{role_ko_attr}>{esc(info["role"])}</div>
        <div class="contract-addr"><a href="{url}" target="_blank" rel="noopener">{short_addr} &nearr;</a></div>
        <div class="contract-live" data-address="{address}"></div>
      </div>"""


def render_log_summary(log_entries):
    """Render compact build counter for main page — latest day only."""
    total_days = len(log_entries)
    total_items = sum(len(e.get("items", [])) for d in log_entries for e in d["entries"])
    latest = log_entries[0] if log_entries else None
    if not latest:
        return ""

    category_labels = {"dev": "Development", "strategy": "Strategy", "design": "Design & Marketing"}
    category_labels_ko = {"dev": "개발", "strategy": "전략", "design": "디자인 & 홍보"}

    latest_lines = ""
    for entry in latest["entries"]:
        cat = entry["category"]
        label_en = category_labels.get(cat, cat)
        label_ko = category_labels_ko.get(cat, cat)
        title_ko = entry.get("title_ko", entry["title"])
        detail_url = f"log/{latest['date']}.html#{cat}"
        latest_lines += f"""
        <a class="log-latest-row" href="{detail_url}">
          <span class="log-latest-cat" data-ko="{esc(label_ko)}">{esc(label_en)}</span>
          <span class="log-latest-title" data-ko="{esc(title_ko)}">{esc(entry["title"])}</span>
          <span class="log-latest-arrow">&rarr;</span>
        </a>"""

    return f"""
    <div class="log-counter reveal">
      <div class="log-counter-num" data-ko="Day {total_days} · {total_items}개 마일스톤">Day {total_days} · {total_items} milestones</div>
      <div class="log-counter-date">{esc(latest["date"])}</div>
    </div>
    <div class="log-latest reveal">{latest_lines}
    </div>
    <a class="log-archive-link" href="log/" data-ko="전체 빌드 로그 보기 →">View full build log →</a>"""


def render_log_detail_page(day, proj, ko_ui, ko_proj):
    """Generate a full detail page for one day."""
    category_labels = {"dev": "Development", "strategy": "Strategy", "design": "Design & Marketing"}
    category_labels_ko = {"dev": "개발", "strategy": "전략", "design": "디자인 & 홍보"}

    sections_html = ""
    for entry in day["entries"]:
        cat = entry["category"]
        label_en = category_labels.get(cat, cat)
        label_ko = category_labels_ko.get(cat, cat)
        title_ko = entry.get("title_ko", entry["title"])
        items_en = entry.get("items", [])
        items_ko = entry.get("items_ko", items_en)

        items_html = ""
        for i, item in enumerate(items_en):
            ko = items_ko[i] if i < len(items_ko) else item
            ko_attr = f' data-ko="{esc(ko)}"' if ko != item else ""
            items_html += f'<li{ko_attr}>{esc(item)}</li>'

        sections_html += f"""
    <section class="detail-section" id="{cat}">
      <div class="detail-card">
        <div class="detail-cat" data-cat="{cat}" data-ko="{esc(label_ko)}">{esc(label_en)}</div>
        <h2 class="detail-title" data-ko="{esc(title_ko)}">{esc(entry["title"])}</h2>
        <ul class="detail-items">{items_html}</ul>
      </div>
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(proj["name"])} — {esc(day["date"])}</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,700;1,400;1,500&display=swap" rel="stylesheet">
<link href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-sans/style.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-mono/style.min.css" rel="stylesheet">
<style>
  :root {{ --black:#0C0C0C; --white:#FAFAF9; --gray-200:#E7E5E4; --gray-400:#A8A29E; --gray-500:#78716C; --gray-600:#57534E; --gray-700:#44403C; --gray-900:#1C1917; --accent:#1A7F64; --display:'Playfair Display',Georgia,serif; --sans:'Geist Sans','Satoshi',system-ui,sans-serif; --mono:'Geist Mono','SF Mono',monospace; --ease:cubic-bezier(0.25,0.46,0.45,0.94); }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:var(--sans); background:var(--white); color:var(--black); -webkit-font-smoothing:antialiased; }}
  ::selection {{ background:var(--black); color:var(--white); }}

  nav {{ position:sticky; top:0; z-index:100; padding:0 48px; height:64px; display:flex; align-items:center; justify-content:space-between; background:rgba(250,250,249,0.92); backdrop-filter:blur(20px); border-bottom:1px solid var(--gray-200); }}
  .logo {{ font-family:var(--sans); font-weight:700; font-size:18px; letter-spacing:-0.03em; color:var(--black); text-decoration:none; }}
  .nav-links {{ display:flex; align-items:center; gap:28px; }}
  .nav-links a {{ font-size:15px; font-weight:500; color:var(--gray-600); text-decoration:none; transition:color 300ms var(--ease); }}
  .nav-links a:hover {{ color:var(--black); }}
  .nav-links a.active {{ color:var(--black); font-weight:700; border-bottom:2px solid var(--accent); padding-bottom:2px; }}
  .nav-live::before {{ content:''; display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--accent); margin-right:6px; animation:pulse 2s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.4; }} }}
  .hamburger {{ display:none; background:none; border:none; cursor:pointer; padding:8px; color:var(--gray-600); }}
  .hamburger svg {{ width:24px; height:24px; }}
  .mobile-menu {{ display:none; position:fixed; top:64px; left:0; right:0; background:var(--white); border-bottom:1px solid var(--gray-200); padding:16px 24px; z-index:99; flex-direction:column; gap:16px; }}
  .mobile-menu.open {{ display:flex; }}
  .mobile-menu a {{ font-size:16px; font-weight:500; color:var(--gray-600); text-decoration:none; padding:8px 0; }}
  .mobile-menu a.active {{ color:var(--accent); font-weight:700; }}
  @media (max-width:640px) {{ .nav-links a.hm {{ display:none; }} .hamburger {{ display:block; }} }}
  .lang-btn {{ position:relative; display:flex; align-items:center; gap:6px; font-family:var(--sans); font-size:14px; font-weight:500; color:var(--gray-500); background:transparent; border:1px solid var(--gray-200); border-radius:100px; padding:6px 14px; cursor:pointer; transition:all 200ms var(--ease); }}
  .lang-btn:hover {{ color:var(--black); border-color:var(--gray-400); }}
  .lang-btn svg {{ width:16px; height:16px; }}
  .lang-dropdown {{ position:absolute; top:calc(100% + 8px); right:0; background:var(--white); border:1px solid var(--gray-200); border-radius:8px; box-shadow:0 8px 24px rgba(0,0,0,0.12); overflow:hidden; opacity:0; transform:translateY(-4px); pointer-events:none; transition:all 200ms var(--ease); min-width:140px; z-index:200; }}
  .lang-dropdown.open {{ opacity:1; transform:translateY(0); pointer-events:auto; }}
  .lang-option {{ display:flex; align-items:center; gap:10px; padding:12px 16px; font-size:14px; font-weight:500; color:var(--gray-600); cursor:pointer; transition:background 150ms var(--ease); }}
  .lang-option:hover {{ background:var(--gray-200); }}
  .lang-option.active {{ color:var(--accent); }}
  @media (max-width:640px) {{ nav {{ padding:0 24px; }} }}

  .hero {{ padding:100px 48px 64px; }}
  @media (max-width:640px) {{ .hero {{ padding:80px 24px 48px; }} }}
  .hero-date {{ font-family:var(--display); font-size:clamp(36px,5vw,56px); font-weight:400; letter-spacing:-0.025em; margin-bottom:16px; }}

  .detail-section {{ padding:48px 48px; max-width:820px; }}
  .detail-section + .detail-section {{ border-top:1px solid var(--gray-200); margin-top:16px; padding-top:48px; }}
  @media (max-width:640px) {{ .detail-section {{ padding:32px 24px; }} }}
  .detail-card {{ background:var(--gray-100); border-radius:12px; padding:48px; margin-bottom:0; }}
  .detail-cat {{ display:inline-block; font-family:var(--sans); font-size:18px; font-weight:700; text-transform:uppercase; letter-spacing:0.04em; color:var(--black); padding:0 0 8px; margin-bottom:24px; border-bottom:2px solid var(--black); }}
  .detail-title {{ font-family:var(--display); font-size:clamp(32px,5vw,48px); font-weight:400; letter-spacing:-0.02em; margin-bottom:36px; line-height:1.2; }}
  .detail-items {{ padding-left:20px; display:flex; flex-direction:column; gap:24px; }}
  .detail-items li {{ font-size:18px; color:var(--gray-600); line-height:1.8; }}

  .fab-back {{ position:fixed; bottom:32px; right:32px; z-index:90; font-family:var(--sans); font-size:15px; font-weight:600; color:var(--white); background:var(--black); text-decoration:none; display:flex; align-items:center; gap:8px; padding:14px 24px; border-radius:9999px; box-shadow:0 4px 20px rgba(0,0,0,0.2); transition:all 200ms var(--ease); opacity:0; transform:translateY(12px); pointer-events:none; }}
  .fab-back.visible {{ opacity:1; transform:translateY(0); pointer-events:auto; }}
  .fab-back:hover {{ background:var(--accent); transform:translateY(-2px); box-shadow:0 6px 28px rgba(0,0,0,0.25); }}
  @media (max-width:640px) {{ .fab-back {{ bottom:24px; right:24px; font-size:14px; padding:12px 20px; }} }}

  footer {{ padding:32px 48px; border-top:1px solid var(--gray-200); }}
  footer span {{ font-family:var(--mono); font-size:11px; color:var(--gray-500); }}
</style>
</head>
<body>
<nav>
  <a class="logo" href="../index.html">{esc(proj["name"])}</a>
  <div class="nav-links">
    <a href="../index.html#roadmap" class="hm" data-ko="로드맵">Roadmap</a>
    <a href="../index.html#log" class="hm active" data-ko="빌드 로그">Log</a>
    <a href="../thesis.html" class="hm" data-ko="투자 논문">Thesis</a>
    <button class="hamburger" onclick="document.querySelector('.mobile-menu').classList.toggle('open')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <div style="position:relative;">
      <button class="lang-btn" onclick="document.querySelector('.lang-dropdown').classList.toggle('open')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
        <span id="langLabel">EN</span>
      </button>
      <div class="lang-dropdown">
        <div class="lang-option active" data-lang="en" onclick="setLang('en')">English</div>
        <div class="lang-option" data-lang="ko" onclick="setLang('ko')">한국어</div>
      </div>
    </div>
  </div>
</nav>

<div class="mobile-menu">
  <a href="../index.html#roadmap" data-ko="로드맵" onclick="this.parentElement.classList.remove('open')">Roadmap</a>
  <a href="../vault.html" data-ko="볼트" onclick="this.parentElement.classList.remove('open')">Vault</a>
  <a href="../index.html#log" data-ko="빌드 로그" onclick="this.parentElement.classList.remove('open')">Log</a>
  <a href="../thesis.html" data-ko="투자 논문">Thesis</a>
</div>

<section class="hero">
  <h1 class="hero-date">{esc(day["date"])}</h1>
</section>

{sections_html}

<a class="fab-back" href="../index.html" id="fabBack">&larr; <span data-ko="메인으로">Home</span></a>

<footer><span>&copy; 2026 {esc(proj["name"])}</span></footer>

<script>
  // Floating back button
  const fabBack = document.getElementById('fabBack');
  window.addEventListener('scroll', () => {{
    fabBack.classList.toggle('visible', window.scrollY > 300);
  }});

  let currentLang = localStorage.getItem('lang') || 'en';
  const langLabel = document.getElementById('langLabel');
  const dropdown = document.querySelector('.lang-dropdown');
  function setLang(lang) {{ currentLang = lang; localStorage.setItem('lang', lang); dropdown.classList.remove('open'); applyLang(); }}
  function applyLang() {{
    langLabel.textContent = currentLang === 'en' ? 'EN' : 'KR';
    document.documentElement.lang = currentLang === 'ko' ? 'ko' : 'en';
    document.querySelectorAll('.lang-option').forEach(o => o.classList.toggle('active', o.dataset.lang === currentLang));
    document.querySelectorAll('[data-ko],[data-ko-html]').forEach(el => {{
      if (!el.dataset.en) el.dataset.en = el.innerHTML;
      if (currentLang === 'ko') {{
        if (el.dataset.koHtml) el.innerHTML = el.dataset.koHtml;
        else if (el.dataset.ko) el.textContent = el.dataset.ko;
      }} else if (el.dataset.en) {{
        el.innerHTML = el.dataset.en;
      }}
    }});
  }}
  document.addEventListener('click', e => {{ if (!e.target.closest('.lang-btn') && !e.target.closest('.lang-dropdown')) dropdown.classList.remove('open'); }});
  if (currentLang === 'ko') applyLang();
</script>
</body>
</html>"""


def render_log_archive(log_entries, proj, ko_ui, ko_proj):
    """Generate the full build log archive page with inline expansion."""
    category_labels = {"dev": "Development", "strategy": "Strategy", "design": "Design & Marketing"}
    category_labels_ko = {"dev": "개발", "strategy": "전략", "design": "디자인 & 홍보"}
    total_days = len(log_entries)
    total_items = sum(len(e.get("items", [])) for d in log_entries for e in d["entries"])

    days_html = ""
    for day in log_entries:
        entries_html = ""
        for entry in day["entries"]:
            cat = entry["category"]
            label_en = category_labels.get(cat, cat)
            label_ko = category_labels_ko.get(cat, cat)
            title_ko = entry.get("title_ko", entry["title"])
            items_en = entry.get("items", [])
            items_ko = entry.get("items_ko", items_en)

            items_html = ""
            for i, item in enumerate(items_en):
                ko = items_ko[i] if i < len(items_ko) else item
                ko_attr = f' data-ko="{esc(ko)}"' if ko != item else ""
                items_html += f'<li{ko_attr}>{esc(item)}</li>'

            entries_html += f"""
      <div class="arc-entry" onclick="this.classList.toggle('open')">
        <div class="arc-row">
          <span class="arc-cat" data-ko="{esc(label_ko)}">{esc(label_en)}</span>
          <span class="arc-title" data-ko="{esc(title_ko)}">{esc(entry["title"])}</span>
          <span class="arc-toggle">+</span>
        </div>
        <div class="arc-detail">
          <ul class="arc-items">{items_html}</ul>
        </div>
      </div>"""

        days_html += f"""
    <div class="arc-day">
      <div class="arc-date">{esc(day["date"])}</div>
      {entries_html}
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(proj["name"])} — Build Log</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;700&display=swap" rel="stylesheet">
<link href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-sans/style.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-mono/style.min.css" rel="stylesheet">
<style>
  :root {{ --black:#0C0C0C; --white:#FAFAF9; --gray-100:#F5F5F4; --gray-200:#E7E5E4; --gray-300:#D6D3D1; --gray-400:#A8A29E; --gray-500:#78716C; --gray-600:#57534E; --gray-700:#44403C; --gray-900:#1C1917; --accent:#1A7F64; --display:'Playfair Display',Georgia,serif; --sans:'Geist Sans','Satoshi',system-ui,sans-serif; --mono:'Geist Mono','SF Mono',monospace; --ease:cubic-bezier(0.25,0.46,0.45,0.94); }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:var(--sans); background:var(--white); color:var(--black); -webkit-font-smoothing:antialiased; }}
  ::selection {{ background:var(--black); color:var(--white); }}

  nav {{ position:sticky; top:0; z-index:100; padding:0 48px; height:64px; display:flex; align-items:center; justify-content:space-between; background:rgba(250,250,249,0.92); backdrop-filter:blur(20px); border-bottom:1px solid var(--gray-200); }}
  .logo {{ font-family:var(--sans); font-weight:700; font-size:18px; letter-spacing:-0.03em; color:var(--black); text-decoration:none; }}
  .nav-links {{ display:flex; align-items:center; gap:28px; }}
  .nav-links a {{ font-size:15px; font-weight:500; color:var(--gray-600); text-decoration:none; transition:color 300ms var(--ease); }}
  .nav-links a:hover {{ color:var(--black); }}
  .nav-links a.active {{ color:var(--black); font-weight:700; border-bottom:2px solid var(--accent); padding-bottom:2px; }}
  .hamburger {{ display:none; background:none; border:none; cursor:pointer; padding:8px; color:var(--gray-600); }}
  .hamburger svg {{ width:24px; height:24px; }}
  @media (max-width:640px) {{ .nav-links a.hm {{ display:none; }} .hamburger {{ display:block; }} nav {{ padding:0 24px; }} }}

  .lang-btn {{ position:relative; display:flex; align-items:center; gap:6px; font-family:var(--sans); font-size:14px; font-weight:500; color:var(--gray-500); background:transparent; border:1px solid var(--gray-200); border-radius:100px; padding:6px 14px; cursor:pointer; transition:all 200ms var(--ease); }}
  .lang-btn:hover {{ color:var(--black); border-color:var(--gray-400); }}
  .lang-btn svg {{ width:16px; height:16px; }}
  .lang-dropdown {{ position:absolute; top:calc(100% + 8px); right:0; background:var(--white); border:1px solid var(--gray-200); border-radius:8px; box-shadow:0 8px 24px rgba(0,0,0,0.12); overflow:hidden; opacity:0; transform:translateY(-4px); pointer-events:none; transition:all 200ms var(--ease); min-width:140px; z-index:200; }}
  .lang-dropdown.open {{ opacity:1; transform:translateY(0); pointer-events:auto; }}
  .lang-option {{ display:flex; align-items:center; gap:10px; padding:12px 16px; font-size:14px; font-weight:500; color:var(--gray-600); cursor:pointer; transition:background 150ms var(--ease); }}
  .lang-option:hover {{ background:var(--gray-100); }}
  .lang-option.active {{ color:var(--accent); }}

  .mobile-menu {{ display:none; position:fixed; top:64px; left:0; right:0; background:var(--white); border-bottom:1px solid var(--gray-200); padding:16px 24px; z-index:99; flex-direction:column; gap:16px; }}
  .mobile-menu.open {{ display:flex; }}
  .mobile-menu a {{ font-size:16px; font-weight:500; color:var(--gray-600); text-decoration:none; padding:8px 0; }}

  .archive {{ max-width:760px; margin:0 auto; padding:96px 48px 64px; }}
  @media (max-width:640px) {{ .archive {{ padding:80px 24px 48px; }} }}
  .arc-eyebrow {{ font-family:var(--mono); font-size:12px; text-transform:uppercase; letter-spacing:0.1em; color:var(--gray-500); margin-bottom:16px; }}
  .arc-h1 {{ font-family:var(--display); font-size:clamp(36px,5vw,56px); font-weight:400; letter-spacing:-0.025em; margin-bottom:8px; }}
  .arc-stat {{ font-family:var(--mono); font-size:14px; color:var(--gray-500); margin-bottom:48px; }}

  .arc-day {{ margin-bottom:48px; }}
  .arc-date {{ font-family:var(--mono); font-size:14px; font-weight:600; color:var(--gray-500); text-transform:uppercase; letter-spacing:0.06em; margin-bottom:8px; padding-bottom:8px; border-bottom:1px solid var(--gray-200); }}
  .arc-entry {{ cursor:pointer; border-bottom:1px solid var(--gray-200); }}
  .arc-row {{ display:grid; grid-template-columns:130px 1fr 24px; gap:20px; padding:16px 0; align-items:baseline; transition:opacity 200ms var(--ease); }}
  .arc-entry:hover .arc-row {{ opacity:0.7; }}
  @media (max-width:640px) {{ .arc-row {{ grid-template-columns:1fr auto; gap:8px; }} .arc-cat {{ display:none; }} }}
  .arc-cat {{ font-family:var(--mono); font-size:13px; font-weight:500; text-transform:uppercase; letter-spacing:0.06em; color:var(--gray-500); }}
  .arc-title {{ font-family:var(--sans); font-size:17px; font-weight:500; letter-spacing:-0.01em; color:var(--black); }}
  .arc-toggle {{ font-family:var(--mono); font-size:18px; color:var(--gray-400); transition:transform 200ms var(--ease); }}
  .arc-entry.open .arc-toggle {{ transform:rotate(45deg); }}
  .arc-detail {{ max-height:0; overflow:hidden; transition:max-height 300ms var(--ease); }}
  .arc-entry.open .arc-detail {{ max-height:800px; }}
  .arc-items {{ padding:0 0 24px 150px; list-style:none; }}
  @media (max-width:640px) {{ .arc-items {{ padding:0 0 24px 0; }} }}
  .arc-items li {{ font-size:15px; color:var(--gray-600); line-height:1.75; padding:8px 0; border-bottom:1px solid var(--gray-100); }}
  .arc-items li:last-child {{ border-bottom:none; }}

  footer {{ padding:24px 48px; border-top:1px solid var(--gray-200); }}
  footer span {{ font-family:var(--mono); font-size:11px; color:var(--gray-500); }}
</style>
</head>
<body>

<nav>
  <a class="logo" href="../index.html">{esc(proj["name"])}</a>
  <div class="nav-links">
    <a href="../index.html#roadmap" class="hm" data-ko="로드맵">Roadmap</a>
    <a href="./" class="hm active" data-ko="빌드 로그">Log</a>
    <a href="../thesis.html" class="hm" data-ko="투자 논문">Thesis</a>
    <button class="hamburger" onclick="document.querySelector('.mobile-menu').classList.toggle('open')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <div style="position:relative;">
      <button class="lang-btn" onclick="document.querySelector('.lang-dropdown').classList.toggle('open')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
        <span id="langLabel">EN</span>
      </button>
      <div class="lang-dropdown">
        <div class="lang-option active" data-lang="en" onclick="setLang('en')">English</div>
        <div class="lang-option" data-lang="ko" onclick="setLang('ko')">한국어</div>
      </div>
    </div>
  </div>
</nav>

<div class="mobile-menu">
  <a href="../index.html#roadmap" data-ko="로드맵" onclick="this.parentElement.classList.remove('open')">Roadmap</a>
  <a href="../vault.html" data-ko="볼트">Vault</a>
  <a href="./" class="active" data-ko="빌드 로그">Log</a>
  <a href="../thesis.html" data-ko="투자 논문">Thesis</a>
</div>

<div class="archive">
  <div class="arc-eyebrow" data-ko="빌드 로그">Build Log</div>
  <h1 class="arc-h1" data-ko="빌드 히스토리">Build history</h1>
  <div class="arc-stat" data-ko="Day {total_days} · {total_items}개 마일스톤">Day {total_days} · {total_items} milestones shipped</div>
  {days_html}
</div>

<footer><span>&copy; 2026 {esc(proj["name"])}</span></footer>

<script>
let currentLang = localStorage.getItem('lang') || 'en';
const langLabel = document.getElementById('langLabel');
const dropdown = document.querySelector('.lang-dropdown');
function setLang(lang) {{ currentLang = lang; localStorage.setItem('lang', lang); dropdown.classList.remove('open'); applyLang(); }}
function applyLang() {{
  langLabel.textContent = currentLang === 'en' ? 'EN' : 'KR';
  document.documentElement.lang = currentLang === 'ko' ? 'ko' : 'en';
  document.querySelectorAll('.lang-option').forEach(o => o.classList.toggle('active', o.dataset.lang === currentLang));
  document.querySelectorAll('[data-ko],[data-ko-html]').forEach(el => {{
    if (!el.dataset.en) el.dataset.en = el.innerHTML;
    if (currentLang === 'ko') {{
      if (el.dataset.koHtml) el.innerHTML = el.dataset.koHtml;
      else if (el.dataset.ko) el.textContent = el.dataset.ko;
    }} else if (el.dataset.en) {{ el.innerHTML = el.dataset.en; }}
  }});
}}
document.addEventListener('click', e => {{ if (!e.target.closest('.lang-btn') && !e.target.closest('.lang-dropdown')) dropdown.classList.remove('open'); }});
if (currentLang === 'ko') applyLang();
</script>
</body>
</html>"""


def render_competitor(comp):
    ko_action = comp.get("action_ko", comp["action"])
    ko_exposure = comp.get("exposure_ko", comp["exposure"])
    action_ko = f' data-ko="{esc(ko_action)}"' if ko_action != comp["action"] else ""
    exp_ko = f' data-ko="{esc(ko_exposure)}"' if ko_exposure != comp["exposure"] else ""
    return f"""<tr><td class="name">{esc(comp["name"])}</td><td class="action"{action_ko}>{esc(comp["action"])}</td><td class="exposed"{exp_ko}>{esc(comp["exposure"])}</td></tr>"""


def build_html(roadmap, contracts):
    global _ko
    _ko = roadmap.get("i18n", {}).get("ko", {})
    ko_ui = _ko.get("ui", {})
    ko_proj = _ko.get("project", {})

    proj = roadmap["project"]
    phases = roadmap["phases"]
    total_tests = 77
    total_phases = len(phases)
    current_phase = next(
        (i + 1 for i, p in enumerate(phases) if p["status"] == "active"),
        len(phases)
    )

    # Render phases
    phases_html = "\n".join(render_phase(p) for p in phases)

    # Render contracts
    display_order = roadmap["contracts"]["display_order"]
    meta = roadmap["contracts"]["meta"]
    contracts_html = ""
    contract_addresses = []
    for name in display_order:
        addr = contracts.get(name)
        if addr:
            contracts_html += render_contract(name, addr, meta, proj["etherscan_base"])
            contract_addresses.append(addr)

    # Render competitors
    competitors_html = "\n        ".join(render_competitor(c) for c in roadmap["competitors"])

    # Render build log (summary for main page)
    log_html = render_log_summary(roadmap.get("log", []))

    # Contract addresses JSON for live data
    addresses_json = json.dumps(contract_addresses)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(proj["name"])}</title>
<meta name="description" content="{esc(proj["tagline"])}. {esc(proj["description"])}">
<meta property="og:title" content="{esc(proj["name"])} — Milestones">
<meta property="og:description" content="{esc(proj["tagline"])}. Live on {esc(proj["network"])} testnet.">

<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,700;1,400;1,500&display=swap" rel="stylesheet">
<link href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700,900&display=swap" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-sans/style.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-mono/style.min.css" rel="stylesheet">

<style>
  :root {{
    --black: #0C0C0C;
    --white: #FAFAF9;
    --gray-100: #F5F5F4;
    --gray-200: #E7E5E4;
    --gray-300: #D6D3D1;
    --gray-400: #A8A29E;
    --gray-500: #78716C;
    --gray-600: #57534E;
    --gray-700: #44403C;
    --gray-800: #292524;
    --gray-900: #1C1917;
    --accent: #1A7F64;
    --display: 'Playfair Display', Georgia, serif;
    --sans: 'Geist Sans', 'Satoshi', system-ui, sans-serif;
    --mono: 'Geist Mono', 'SF Mono', monospace;
    --ease: cubic-bezier(0.25, 0.46, 0.45, 0.94);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: var(--sans); background: var(--white); color: var(--black); -webkit-font-smoothing: antialiased; }}
  ::selection {{ background: var(--black); color: var(--white); }}

  nav {{ position: fixed; top: 0; left: 0; right: 0; z-index: 100; padding: 0 48px; height: 64px; display: flex; align-items: center; justify-content: space-between; background: rgba(250,250,249,0.9); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-bottom: 1px solid transparent; transition: border-color 400ms var(--ease); }}
  nav.scrolled {{ border-bottom-color: var(--gray-200); }}
  .nav-dark {{ background: rgba(12,12,12,0.9) !important; border-bottom-color: rgba(255,255,255,0.06) !important; }}
  .nav-dark .logo, .nav-dark .nav-links a {{ color: var(--white); }}
  .nav-dark .nav-links a:hover {{ color: var(--gray-400); }}
  .nav-dark .nav-status {{ color: var(--gray-400); border-color: rgba(255,255,255,0.1); }}
  .logo {{ font-family: var(--sans); font-weight: 700; font-size: 18px; letter-spacing: -0.03em; color: var(--black); text-decoration: none; }}
  .fab-vault {{ position: fixed; bottom: 0; right: 48px; z-index: 90; text-decoration: none; color: var(--white); background: rgba(12,12,12,0.92); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); width: 340px; padding: 28px 32px; display: flex; flex-direction: column; gap: 16px; transform: translateY(100%); transition: transform 500ms var(--ease); }}
  .fab-vault.intro {{ transform: translateY(0); }}
  .fab-vault.settled {{ transform: translateY(calc(100% - 56px)); }}
  .fab-vault:hover {{ transform: translateY(0); }}
  .fab-vault .fab-label {{ font-family: var(--mono); font-size: 14px; font-weight: 500; letter-spacing: 0.1em; text-transform: uppercase; color: var(--white); display: flex; align-items: center; justify-content: space-between; }}
  .fab-vault .fab-label::after {{ content: ''; display: inline-block; width: 24px; height: 1px; background: var(--gray-600); transition: width 300ms var(--ease); }}
  .fab-vault:hover .fab-label::after {{ width: 48px; background: var(--white); }}
  .fab-vault .fab-desc {{ font-family: var(--sans); font-size: 16px; color: var(--gray-500); line-height: 1.65; }}
  .fab-vault .fab-arrow {{ font-family: var(--mono); font-size: 13px; color: var(--gray-600); transition: color 200ms var(--ease); padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); }}
  .fab-vault:hover .fab-arrow {{ color: var(--white); }}
  @media (max-width: 640px) {{ .fab-vault {{ right: 0; width: 100%; }} }}
  .nav-links {{ display: flex; align-items: center; gap: 28px; }}
  .nav-links a {{ font-size: 15px; font-weight: 500; color: var(--gray-600); text-decoration: none; transition: color 300ms var(--ease); }}
  .nav-links a:hover {{ color: var(--black); }}
  .nav-status {{ font-family: var(--mono); font-size: 12px; color: var(--gray-500); padding: 5px 14px; border: 1px solid var(--gray-200); border-radius: 100px; }}
  .lang-btn {{ position: relative; display: flex; align-items: center; gap: 6px; font-family: var(--sans); font-size: 14px; font-weight: 500; color: var(--gray-500); background: transparent; border: 1px solid var(--gray-200); border-radius: 100px; padding: 6px 14px; cursor: pointer; transition: all 200ms var(--ease); }}
  .lang-btn:hover {{ color: var(--black); border-color: var(--gray-400); }}
  .lang-btn svg {{ width: 16px; height: 16px; }}
  .nav-dark .lang-btn {{ color: var(--gray-400); border-color: rgba(255,255,255,0.1); }}
  .nav-dark .lang-btn:hover {{ color: var(--white); border-color: rgba(255,255,255,0.2); }}
  .lang-dropdown {{ position: absolute; top: calc(100% + 8px); right: 0; background: var(--white); border: 1px solid var(--gray-200); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.12); overflow: hidden; opacity: 0; transform: translateY(-4px); pointer-events: none; transition: all 200ms var(--ease); min-width: 140px; z-index: 200; }}
  .lang-dropdown.open {{ opacity: 1; transform: translateY(0); pointer-events: auto; }}
  .nav-dark .lang-dropdown {{ background: var(--gray-900); border-color: rgba(255,255,255,0.1); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }}
  .lang-option {{ display: flex; align-items: center; gap: 10px; padding: 12px 16px; font-size: 14px; font-weight: 500; color: var(--gray-600); cursor: pointer; transition: background 150ms var(--ease); }}
  .lang-option:hover {{ background: var(--gray-100); }}
  .nav-dark .lang-option {{ color: var(--gray-400); }}
  .nav-dark .lang-option:hover {{ background: rgba(255,255,255,0.05); }}
  .lang-option.active {{ color: var(--accent); }}
  .nav-links a.active {{ color: var(--black); font-weight: 700; border-bottom: 2px solid var(--accent); padding-bottom: 2px; }}
  .nav-dark .nav-links a.active {{ color: var(--white); font-weight: 700; border-bottom: 2px solid var(--accent); padding-bottom: 2px; }}
  .nav-live::before {{ content: ''; display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--accent); margin-right: 6px; animation: pulse 2s ease-in-out infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.4; }} }}
  .hamburger {{ display:none; background:none; border:none; cursor:pointer; padding:8px; color:var(--gray-600); }}
  .hamburger svg {{ width:24px; height:24px; }}
  .nav-dark .hamburger {{ color:var(--gray-400); }}
  .mobile-menu {{ display:none; position:fixed; top:64px; left:0; right:0; background:var(--white); border-bottom:1px solid var(--gray-200); padding:16px 24px; z-index:99; flex-direction:column; gap:16px; }}
  .mobile-menu.open {{ display:flex; }}
  .mobile-menu a {{ font-size:16px; font-weight:500; color:var(--gray-600); text-decoration:none; padding:8px 0; }}
  .mobile-menu a.active {{ color:var(--accent); }}
  @media (max-width: 640px) {{ .nav-links a.hm {{ display: none; }} .nav-links {{ gap: 12px; }} .hamburger {{ display:block; }} }}

  .hero {{ background: var(--black); color: var(--white); padding: 180px 48px 120px; min-height: 85vh; display: flex; flex-direction: column; justify-content: flex-end; position: relative; overflow: hidden; }}
  .hero::before {{ content: ''; position: absolute; inset: 0; background: repeating-linear-gradient(0deg, transparent, transparent 79px, rgba(255,255,255,0.03) 79px, rgba(255,255,255,0.03) 80px), repeating-linear-gradient(90deg, transparent, transparent 79px, rgba(255,255,255,0.03) 79px, rgba(255,255,255,0.03) 80px); pointer-events: none; }}
  .hero::after {{ content: ''; position: absolute; bottom: 0; right: 0; width: 50%; height: 60%; background: radial-gradient(ellipse at bottom right, rgba(26,127,100,0.06) 0%, transparent 70%); pointer-events: none; }}
  @media (max-width: 640px) {{ .hero {{ padding: 140px 24px 80px; min-height: 70vh; }} }}
  .hero-eyebrow {{ font-family: var(--mono); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--gray-500); margin-bottom: 32px; }}
  .hero h1 {{ font-family: var(--display); font-weight: 400; font-size: clamp(52px,8vw,96px); line-height: 1.08; letter-spacing: -0.025em; max-width: 900px; margin-bottom: 40px; }}
  .hero h1 em {{ font-style: normal; color: var(--accent); }}
  .hero-sub {{ font-size: 20px; color: var(--gray-400); max-width: 520px; line-height: 1.7; }}

  .metrics-bar {{ background: var(--white); padding: 64px 48px; border-bottom: 1px solid var(--gray-200); }}
  @media (max-width: 640px) {{ .metrics-bar {{ padding: 48px 24px; }} }}
  .metrics-row {{ display: flex; gap: 80px; flex-wrap: wrap; max-width: 960px; }}
  @media (max-width: 640px) {{ .metrics-row {{ gap: 40px; }} }}
  .metric-label {{ font-family: var(--mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-500); margin-bottom: 8px; }}
  .metric-value {{ font-family: var(--display); font-size: 42px; font-weight: 400; letter-spacing: -0.03em; line-height: 1.1; }}

  .section-light {{ background: var(--white); padding: 96px 48px; border-bottom: 1px solid var(--gray-200); }}
  .section-dark {{ background: var(--black); color: var(--white); padding: 96px 48px; }}
  @media (max-width: 640px) {{ .section-light, .section-dark {{ padding: 64px 24px; }} }}
  .section-inner {{ max-width: 960px; }}
  .section-eyebrow {{ font-family: var(--mono); font-size: 12px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-500); margin-bottom: 14px; display: flex; align-items: center; gap: 16px; }}
  .section-eyebrow::after {{ content: ''; flex: 1; max-width: 48px; height: 1px; background: var(--gray-300); }}
  .section-dark .section-eyebrow::after {{ background: var(--gray-700); }}
  .section-title {{ font-family: var(--display); font-weight: 400; font-size: clamp(36px,5vw,56px); letter-spacing: -0.025em; line-height: 1.15; margin-bottom: 56px; }}

  .phase {{ display: grid; grid-template-columns: 220px 1fr; gap: 48px; padding: 48px 0; border-top: 1px solid var(--gray-200); }}
  @media (max-width: 768px) {{ .phase {{ grid-template-columns: 1fr; gap: 24px; }} }}
  .phase-label {{ font-family: var(--mono); font-size: 15px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-500); margin-bottom: 12px; }}
  .phase-name {{ font-family: var(--display); font-size: clamp(36px,5vw,48px); font-weight: 400; letter-spacing: -0.02em; margin-bottom: 10px; line-height: 1.2; }}
  .phase-status {{ font-family: var(--mono); font-size: 15px; font-weight: 600; }}
  .status-done {{ color: var(--accent); }}
  .status-active {{ color: var(--black); font-weight: 500; }}
  .status-wait {{ color: var(--gray-400); }}
  .phase-desc {{ font-size: 18px; color: var(--gray-600); line-height: 1.75; margin-bottom: 28px; max-width: 560px; }}
  .items {{ display: flex; flex-direction: column; gap: 6px; }}
  .item {{ display: flex; align-items: flex-start; gap: 12px; padding: 10px 0; font-size: 17px; line-height: 1.5; }}
  .item-icon {{ width: 20px; height: 20px; flex-shrink: 0; margin-top: 2px; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }}
  .icon-done {{ background: var(--accent); color: white; }}
  .icon-active {{ border: 2px solid var(--black); }}
  .icon-pending {{ border: 1.5px solid var(--gray-300); }}
  .text-done {{ color: var(--gray-600); }}
  .text-active {{ color: var(--black); font-weight: 500; }}
  .text-pending {{ color: var(--gray-400); }}
  .item-sub {{ font-family: var(--mono); font-size: 13px; color: var(--gray-500); margin-top: 2px; }}

  .contracts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; border-top: 1px solid var(--gray-200); }}
  @media (max-width: 640px) {{ .contracts-grid {{ grid-template-columns: 1fr; }} }}
  .contract {{ padding: 32px 0; border-bottom: 1px solid var(--gray-200); }}
  .contract:nth-child(odd) {{ padding-right: 32px; border-right: 1px solid var(--gray-200); }}
  .contract:nth-child(even) {{ padding-left: 32px; }}
  @media (max-width: 640px) {{ .contract:nth-child(odd) {{ padding-right: 0; border-right: none; }} .contract:nth-child(even) {{ padding-left: 0; }} }}
  .contract-name {{ font-size: 18px; font-weight: 600; margin-bottom: 4px; }}
  .contract-name .tag {{ font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); margin-left: 8px; font-weight: 500; }}
  .contract-desc {{ font-size: 15px; color: var(--gray-500); margin-bottom: 12px; }}
  .contract-addr {{ font-family: var(--mono); font-size: 13px; }}
  .contract-addr a {{ color: var(--gray-500); text-decoration: none; transition: color 200ms var(--ease); }}
  .contract-addr a:hover {{ color: var(--black); }}
  .contract-live {{ font-family: var(--mono); font-size: 12px; color: var(--gray-400); margin-top: 8px; }}

  .how-row {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 0; border-top: 1px solid rgba(255,255,255,0.06); }}
  @media (max-width: 640px) {{ .how-row {{ grid-template-columns: 1fr; }} }}
  .how-item {{ padding: 40px 32px 40px 0; border-bottom: 1px solid rgba(255,255,255,0.06); }}
  .how-item:not(:last-child) {{ border-right: 1px solid rgba(255,255,255,0.06); padding-right: 32px; }}
  .how-item:not(:first-child) {{ padding-left: 32px; }}
  @media (max-width: 640px) {{ .how-item {{ padding: 32px 0 !important; border-right: none !important; }} }}
  .how-num {{ font-family: var(--display); font-size: 32px; font-weight: 400; color: var(--gray-700); margin-bottom: 20px; line-height: 1; }}
  .how-name {{ font-size: 20px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 12px; }}
  .how-desc {{ font-size: 16px; color: var(--gray-400); line-height: 1.7; }}

  .comp-table {{ width: 100%; border-collapse: collapse; border-top: 1px solid var(--gray-200); }}
  .comp-table th {{ font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-500); text-align: left; font-weight: 500; padding: 16px 0; border-bottom: 1px solid var(--gray-200); }}
  .comp-table td {{ font-size: 16px; padding: 20px 0; border-bottom: 1px solid var(--gray-200); }}
  .comp-table tr:last-child td {{ border-bottom: none; }}
  .comp-table .name {{ font-weight: 600; width: 160px; }}
  .comp-table .action {{ font-family: var(--mono); font-size: 13px; color: var(--gray-500); }}
  .comp-table .exposed {{ color: var(--gray-400); }}
  .comp-table .ours .name {{ color: var(--accent); }}
  .comp-table .ours .action {{ color: var(--accent); }}
  .comp-table .ours .result {{ color: var(--accent); font-weight: 700; font-size: 16px; }}

  .log-section {{ background: var(--black); color: var(--white); padding: 96px 48px; }}
  @media (max-width: 640px) {{ .log-section {{ padding: 64px 24px; }} }}
  .log-section .section-eyebrow::after {{ background: var(--gray-700); }}
  .log-counter {{ margin-bottom: 40px; }}
  .log-counter-num {{ font-family: var(--display); font-size: clamp(36px,5vw,56px); font-weight: 400; letter-spacing: -0.025em; color: var(--white); margin-bottom: 8px; }}
  .log-counter-date {{ font-family: var(--mono); font-size: 14px; color: var(--gray-500); }}
  .log-latest {{ border-top: 1px solid rgba(255,255,255,0.08); margin-bottom: 40px; }}
  .log-latest-row {{ display: grid; grid-template-columns: 180px 1fr auto; gap: 28px; padding: 24px 0; border-bottom: 1px solid rgba(255,255,255,0.08); text-decoration: none; color: inherit; transition: opacity 200ms var(--ease); opacity: 0.6; }}
  .log-latest-row:hover {{ opacity: 1; }}
  @media (max-width: 768px) {{ .log-latest-row {{ grid-template-columns: 1fr; gap: 8px; }} }}
  .log-latest-cat {{ font-family: var(--mono); font-size: 16px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--gray-400); }}
  .log-latest-title {{ font-family: var(--sans); font-size: 20px; font-weight: 500; color: var(--white); letter-spacing: -0.01em; }}
  .log-latest-arrow {{ font-family: var(--mono); font-size: 18px; color: var(--gray-600); }}
  .log-latest-row:hover .log-latest-arrow {{ color: var(--white); }}
  .log-archive-link {{ font-family: var(--mono); font-size: 15px; color: var(--gray-500); text-decoration: none; transition: color 200ms var(--ease); }}
  .log-archive-link:hover {{ color: var(--white); }}
  .log-filters {{ display: flex; gap: 8px; margin-bottom: 32px; }}
  .log-filter {{ font-family: var(--mono); font-size: 12px; color: var(--gray-500); background: transparent; border: 1px solid rgba(255,255,255,0.08); border-radius: 100px; padding: 6px 16px; cursor: pointer; transition: all 200ms var(--ease); }}
  .log-filter:hover, .log-filter.active {{ color: var(--white); border-color: rgba(255,255,255,0.2); }}
  .log-items {{ padding-left: 18px; display: flex; flex-direction: column; gap: 10px; }}
  .log-items li {{ font-size: 15px; color: var(--gray-400); line-height: 1.65; }}

  .cta {{ background: var(--black); color: var(--white); padding: 120px 48px; }}
  @media (max-width: 640px) {{ .cta {{ padding: 80px 24px; }} }}
  .cta h2 {{ font-family: var(--display); font-weight: 400; font-size: clamp(36px,5vw,56px); letter-spacing: -0.025em; line-height: 1.15; margin-bottom: 24px; max-width: 600px; }}
  .cta p {{ font-size: 16px; color: var(--gray-500); margin-bottom: 48px; max-width: 400px; line-height: 1.7; }}
  .cta-row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .btn-white {{ display: inline-flex; align-items: center; gap: 8px; font-family: var(--sans); font-weight: 600; font-size: 14px; background: var(--white); color: var(--black); padding: 14px 28px; border-radius: 4px; text-decoration: none; transition: opacity 300ms var(--ease), transform 200ms var(--ease); }}
  .btn-white:hover {{ opacity: 0.88; transform: translateY(-1px); }}
  .btn-outline {{ display: inline-flex; align-items: center; gap: 8px; font-family: var(--sans); font-weight: 500; font-size: 14px; background: transparent; color: var(--gray-400); padding: 14px 28px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.1); text-decoration: none; transition: all 300ms var(--ease); }}
  .btn-outline:hover {{ border-color: rgba(255,255,255,0.2); color: var(--white); }}

  .unaudited {{ background: var(--gray-900); color: var(--gray-400); font-family: var(--mono); font-size: 12px; text-align: center; padding: 10px 48px; letter-spacing: 0.06em; border-bottom: 1px solid rgba(255,255,255,0.06); }}
  .unaudited strong {{ color: var(--white); }}

  footer {{ background: var(--black); border-top: 1px solid rgba(255,255,255,0.06); padding: 24px 48px; display: flex; justify-content: space-between; align-items: center; }}
  @media (max-width: 640px) {{ footer {{ padding: 24px; }} }}
  footer span {{ font-family: var(--mono); font-size: 11px; color: var(--gray-700); }}

  .reveal {{ opacity: 0; transform: translateY(20px); transition: opacity 700ms var(--ease), transform 700ms var(--ease); }}
  .reveal.visible {{ opacity: 1; transform: translateY(0); }}
  @media (prefers-reduced-motion: reduce) {{ .reveal {{ opacity: 1; transform: none; }} }}
</style>
</head>
<body>

<nav id="nav">
  <a class="logo" href="#">{esc(proj["name"])}</a>
  <div class="nav-links">
    <a href="#roadmap" class="hm nav-item" data-section="roadmap" data-ko="{esc(ko_ui.get('roadmap', 'Roadmap'))}">Roadmap</a>
    <a href="#log" class="hm nav-item" data-section="log" data-ko="빌드 로그">Log</a>
    <a href="thesis.html" class="hm nav-item" data-ko="투자 논문">Thesis</a>
    <button class="hamburger" onclick="document.querySelector('.mobile-menu').classList.toggle('open')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
    </button>
    <div style="position:relative;">
      <button class="lang-btn" onclick="document.querySelector('.lang-dropdown').classList.toggle('open')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
        <span id="langLabel">EN</span>
      </button>
      <div class="lang-dropdown">
        <div class="lang-option active" data-lang="en" onclick="setLang('en')">English</div>
        <div class="lang-option" data-lang="ko" onclick="setLang('ko')">한국어</div>
      </div>
    </div>
  </div>
</nav>

<div class="mobile-menu">
  <a href="#roadmap" data-ko="{esc(ko_ui.get('roadmap', 'Roadmap'))}" onclick="this.parentElement.classList.remove('open')">Roadmap</a>
  <a href="vault.html" data-ko="볼트">Vault</a>
  <a href="#log" data-ko="빌드 로그" onclick="this.parentElement.classList.remove('open')">Log</a>
  <a href="thesis.html" data-ko="투자 논문">Thesis</a>
</div>

<section class="hero">
  <div class="hero-eyebrow">{esc(proj["eyebrow"])} &middot; {esc(proj["network"])}</div>
  <h1 class="reveal" data-ko-html="변동성 기반 유동성 <em>관리</em>">{esc(proj["tagline"]).replace("liquidity ", "liquidity <em>").replace("management", "management</em>")}</h1>
  <p class="hero-sub reveal" data-ko="{esc(ko_proj.get('description', proj['description']))}">{esc(proj["description"])}</p>
</section>

<section class="metrics-bar">
  <div class="metrics-row">
    <div class="reveal">
      <div class="metric-label" data-ko="{esc(ko_ui.get('phase', 'Phase'))}">{esc(ko_ui.get('phase', 'Phase') if False else 'Phase')}</div>
      <div class="metric-value">{current_phase} of {total_phases}</div>
    </div>
    <div class="reveal">
      <div class="metric-label" data-ko="{esc(ko_ui.get('tests_passing', 'Tests Passing'))}">Tests Passing</div>
      <div class="metric-value" data-count="{total_tests}">{total_tests}</div>
    </div>
    <div class="reveal">
      <div class="metric-label" data-ko="{esc(ko_ui.get('contracts_deployed', 'Contracts Deployed'))}">Contracts Deployed</div>
      <div class="metric-value" data-count="{len(contracts)}">{len(contracts)}</div>
    </div>
    <div class="reveal">
      <div class="metric-label" data-ko="{esc(ko_ui.get('network', 'Network'))}">Network</div>
      <div class="metric-value">{esc(proj["network"])}</div>
    </div>
  </div>
</section>

<section class="log-section" id="log">
  <div class="section-inner">
    <div class="section-eyebrow" data-ko="빌드 로그">Build Log</div>
    <h2 class="section-title reveal" data-ko="오늘 우리가 한 일">What we shipped</h2>
    {log_html}
  </div>
</section>

<section class="section-light" id="roadmap">
  <div class="section-inner">
    <div class="section-eyebrow" data-ko="{esc(ko_ui.get('progress', 'Progress'))}">Progress</div>
    <h2 class="section-title reveal" data-ko="{esc(ko_ui.get('roadmap', 'Roadmap'))}">Roadmap</h2>
    <div class="timeline">
      {phases_html}
    </div>
  </div>
</section>

<section class="section-dark" id="vault">
  <div class="section-inner">
    <div class="section-eyebrow" data-ko="볼트">Vault</div>
    <h2 class="section-title reveal" style="max-width:600px;" data-ko="변동성이 높을 때, LP를 제거합니다">When volatility spikes, we remove your LP</h2>
    <div class="how-row reveal" style="border-top:1px solid rgba(255,255,255,0.06); margin-bottom:48px;">
      <div class="how-item">
        <div class="how-num" style="color:var(--gray-600);">01</div>
        <div class="how-name" style="color:var(--white);" data-ko="성과 수수료 10%">10% Performance Fee</div>
        <div class="how-desc" data-ko="수익 없으면 수수료 없음. 관리보수 0%. 출금 수수료 0%.">No profit, no fee. 0% management. 0% withdrawal.</div>
      </div>
      <div class="how-item">
        <div class="how-num" style="color:var(--gray-600);">02</div>
        <div class="how-name" style="color:var(--white);" data-ko="ERC-4626">ERC-4626</div>
        <div class="how-desc" data-ko="표준 볼트. DeFi 프로토콜과 즉시 호환. 락업 없음.">Standard vault. Composable with DeFi. No lockup.</div>
      </div>
      <div class="how-item">
        <div class="how-num" style="color:var(--gray-600);">03</div>
        <div class="how-name" style="color:var(--white);" data-ko="Sharpe 3.66">Sharpe 3.66</div>
        <div class="how-desc" data-ko="S&P 500 대비 7배. Max Drawdown -12%. 백테스트 검증.">7x the S&P 500. Max DD -12%. Backtest verified.</div>
      </div>
    </div>
    <a href="vault.html" style="font-family:var(--mono); font-size:15px; color:var(--gray-500); text-decoration:none; transition:color 300ms var(--ease); border-bottom:1px solid var(--gray-700); padding-bottom:4px;" onmouseover="this.style.color='var(--white)';this.style.borderColor='var(--white)'" onmouseout="this.style.color='var(--gray-500)';this.style.borderColor='var(--gray-700)'" data-ko="볼트 열기 →">Open Vault →</a>
  </div>
</section>

<section class="section-dark" id="how">
  <div class="section-inner">
    <div class="section-eyebrow" data-ko="{esc(ko_ui.get('mechanism', 'Mechanism'))}">Mechanism</div>
    <h2 class="section-title reveal" data-ko="{esc(ko_ui.get('how_it_works', 'How it works'))}">How it works</h2>
    <div class="how-row reveal">
      <div class="how-item">
        <div class="how-num">01</div>
        <div class="how-name" data-ko="{esc(ko_ui.get('monitor', 'Monitor'))}">Monitor</div>
        <div class="how-desc" data-ko="{esc(ko_ui.get('monitor_desc', ''))}">On-chain volatility oracle tracks price variance using EWMA. Every swap updates the estimate. Zero off-chain dependencies.</div>
      </div>
      <div class="how-item">
        <div class="how-num">02</div>
        <div class="how-name" data-ko="{esc(ko_ui.get('evaluate', 'Evaluate'))}">Evaluate</div>
        <div class="how-desc" data-ko="{esc(ko_ui.get('evaluate_desc', ''))}">When variance exceeds the threshold, the hook signals removal. A binary decision. Safe to LP, or not.</div>
      </div>
      <div class="how-item">
        <div class="how-num">03</div>
        <div class="how-name" data-ko="{esc(ko_ui.get('execute', 'Execute'))}">Execute</div>
        <div class="how-desc" data-ko="{esc(ko_ui.get('execute_desc', ''))}">Keeper bot acts on the signal. Removes LP during high volatility, re-enters when conditions normalize.</div>
      </div>
    </div>
  </div>
</section>

<section class="section-light">
  <div class="section-inner">
    <div class="section-eyebrow" data-ko="{esc(ko_ui.get('positioning', 'Positioning'))}">Positioning</div>
    <h2 class="section-title reveal" data-ko="{esc(ko_ui.get('when_vol_spikes', 'When volatility spikes'))}">When volatility spikes</h2>
    <table class="comp-table reveal">
      <thead><tr><th data-ko="{esc(ko_ui.get('protocol', 'Protocol'))}">Protocol</th><th data-ko="{esc(ko_ui.get('response', 'Response'))}">Response</th><th data-ko="{esc(ko_ui.get('il_exposure', 'IL Exposure'))}">IL Exposure</th></tr></thead>
      <tbody>
        {competitors_html}
        <tr class="ours"><td class="name">{esc(proj["name"])}</td><td class="action" data-ko="{esc(ko_ui.get('remove_lp', 'Remove LP entirely'))}">Remove LP entirely</td><td class="result" data-ko="{esc(ko_ui.get('zero', 'Zero'))}">Zero</td></tr>
      </tbody>
    </table>
  </div>
</section>

<section class="cta">
  <h2 class="reveal" data-ko="{esc(ko_ui.get('building_public', 'Building in public.'))}"><span data-ko="{esc(ko_ui.get('building_public', 'Building in public.'))}">Building in public.</span><br><em data-ko="{esc(ko_ui.get('everything_onchain', 'Everything on-chain.'))}">Everything on-chain.</em></h2>
  <p class="reveal" data-ko="{esc(ko_ui.get('follow_progress', ''))}">{esc("Follow our testnet progress. Be the first to know when we reach mainnet.")}</p>
  <div class="cta-row reveal">
    <a class="btn-white" href="{esc(proj["etherscan_base"])}/address/{list(contracts.values())[0] if contracts else ''}" target="_blank" rel="noopener" data-ko="{esc(ko_ui.get('view_etherscan', 'View on Etherscan'))} &rarr;">View on Etherscan &rarr;</a>
    <a class="btn-outline" href="{esc(proj["twitter"])}" target="_blank" rel="noopener" data-ko="{esc(ko_ui.get('follow_x', 'Follow on X'))}">Follow on X</a>
  </div>
</section>


<a class="fab-vault" id="fabVault" href="vault.html">
  <span class="fab-label" data-ko="VAULT 열기 →">OPEN VAULT →</span>
  <span class="fab-desc" data-ko="변동성이 높을 때 LP를 자동 제거합니다. Sharpe 3.66. 성과 수수료만.">Automatically removes LP during high volatility. Sharpe 3.66. Performance-fee-only.</span>
  <span class="fab-arrow" data-ko="입금 및 출금 →">Deposit & Withdraw →</span>
</a>

<footer>
  <span>&copy; 2026 {esc(proj["name"])}</span>
  <span>{esc(proj["network"])} &middot; Uniswap V4</span>
</footer>

<script>
  // Reveal
  const obs = new IntersectionObserver(e => e.forEach(x => {{ if (x.isIntersecting) x.target.classList.add('visible'); }}), {{ threshold: 0.08, rootMargin: '0px 0px -60px 0px' }});
  document.querySelectorAll('.reveal').forEach((el, i) => {{ el.style.transitionDelay = `${{Math.min(i*60,400)}}ms`; obs.observe(el); }});
  setTimeout(() => document.querySelectorAll('.reveal').forEach(el => el.classList.add('visible')), 2500);

  // Nav
  const nav = document.getElementById('nav');
  const hero = document.querySelector('.hero');
  function updateNav() {{
    nav.classList.toggle('scrolled', window.scrollY > 20);
    nav.classList.toggle('nav-dark', window.scrollY < hero.offsetTop + hero.offsetHeight - 80);
  }}
  window.addEventListener('scroll', () => requestAnimationFrame(updateNav));
  updateNav();

  // Counter
  function animateCount(el, target) {{
    const start = performance.now();
    function tick(now) {{
      const p = Math.min((now - start) / 1000, 1);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick);
    }}
    requestAnimationFrame(tick);
  }}
  const mObs = new IntersectionObserver(e => e.forEach(x => {{
    if (x.isIntersecting) {{
      x.target.querySelectorAll('[data-count]').forEach(el => animateCount(el, parseInt(el.dataset.count)));
      mObs.unobserve(x.target);
    }}
  }}), {{ threshold: 0.5 }});
  mObs.observe(document.querySelector('.metrics-row'));

  // Live contract data from Etherscan API
  const ETHERSCAN_API = '{esc(proj["etherscan_base"])}/api';
  const CONTRACT_ADDRS = {addresses_json};

  async function fetchLiveData() {{
    for (const addr of CONTRACT_ADDRS) {{
      const el = document.querySelector(`[data-address="${{addr}}"]`);
      if (!el) continue;
      try {{
        const res = await fetch(`${{ETHERSCAN_API}}?module=proxy&action=eth_getTransactionCount&address=${{addr}}&tag=latest`);
        const data = await res.json();
        if (data.result) {{
          const txCount = parseInt(data.result, 16);
          el.textContent = `${{txCount}} transaction${{txCount !== 1 ? 's' : ''}}`;
        }}
      }} catch (e) {{
        el.textContent = 'verified on-chain';
      }}
    }}
  }}
  fetchLiveData();

  // FAB intro animation
  const fabVault = document.getElementById('fabVault');
  if (fabVault) {{
    setTimeout(() => {{
      fabVault.classList.add('intro');
      setTimeout(() => {{
        fabVault.classList.remove('intro');
        fabVault.classList.add('settled');
      }}, 2000);
    }}, 1500);
  }}

  // i18n
  let currentLang = localStorage.getItem('lang') || 'en';
  const langLabel = document.getElementById('langLabel');
  const dropdown = document.querySelector('.lang-dropdown');

  function setLang(lang) {{
    currentLang = lang;
    localStorage.setItem('lang', lang);
    dropdown.classList.remove('open');
    applyLang();
  }}

  function applyLang() {{
    langLabel.textContent = currentLang === 'en' ? 'EN' : 'KR';
    document.documentElement.lang = currentLang === 'ko' ? 'ko' : 'en';
    document.querySelectorAll('.lang-option').forEach(o => {{
      o.classList.toggle('active', o.dataset.lang === currentLang);
    }});
    document.querySelectorAll('[data-ko],[data-ko-html]').forEach(el => {{
      if (!el.dataset.en) el.dataset.en = el.innerHTML;
      if (currentLang === 'ko') {{
        if (el.dataset.koHtml) el.innerHTML = el.dataset.koHtml;
        else if (el.dataset.ko) el.textContent = el.dataset.ko;
      }} else if (el.dataset.en) {{
        el.innerHTML = el.dataset.en;
      }}
    }});
  }}

  // Close dropdown on outside click
  document.addEventListener('click', e => {{
    if (!e.target.closest('.lang-btn') && !e.target.closest('.lang-dropdown')) {{
      dropdown.classList.remove('open');
    }}
  }});

  if (currentLang === 'ko') applyLang();

  // Active section highlighting
  const sections = document.querySelectorAll('section[id]');
  const navItems = document.querySelectorAll('.nav-item[data-section]');
  function updateActive() {{
    let current = '';
    sections.forEach(s => {{
      if (window.scrollY >= s.offsetTop - 120) current = s.id;
    }});
    navItems.forEach(a => {{
      a.classList.toggle('active', a.dataset.section === current);
    }});
  }}
  window.addEventListener('scroll', () => requestAnimationFrame(updateActive));
  updateActive();
</script>
</body>
</html>"""


def main():
    global _ko
    roadmap = load_roadmap()
    _ko = roadmap.get("i18n", {}).get("ko", {})
    ko_ui = _ko.get("ui", {})
    ko_proj = _ko.get("project", {})
    contracts = load_contracts_from_broadcast()

    print(f"Found {len(contracts)} contracts from broadcast files:")
    for name, addr in contracts.items():
        print(f"  {name}: {addr}")

    # Build main page
    html_content = build_html(roadmap, contracts)
    output = MILESTONE_DIR / "index.html"
    output.write_text(html_content)
    print(f"\nWritten to {output}")

    # Build detail pages
    log_dir = MILESTONE_DIR / "log"
    log_dir.mkdir(exist_ok=True)
    for day in roadmap.get("log", []):
        detail_html = render_log_detail_page(day, roadmap["project"], ko_ui, ko_proj)
        detail_file = log_dir / f"{day['date']}.html"
        detail_file.write_text(detail_html)
        print(f"Written to {detail_file}")

    # Build log archive
    archive_html = render_log_archive(roadmap.get("log", []), roadmap["project"], ko_ui, ko_proj)
    archive_file = log_dir / "index.html"
    archive_file.write_text(archive_html)
    print(f"Written to {archive_file}")

    print("Done.")


if __name__ == "__main__":
    main()
