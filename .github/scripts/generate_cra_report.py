#!/usr/bin/env python3
"""
CRA Security Evidence Report Generator
.github/scripts/generate_cra_report.py

Reads JSON exports from the report/ directory and writes a self-contained
HTML evidence report to report/cra-evidence-report.html.

CRA reference: Regulation (EU) 2024/2847, Annex I Part II §2(3)
"Apply effective and regular security tests and reviews during development"
"""

import json
import html as html_lib
import datetime
import os
import sys


# ── Data loading ───────────────────────────────────────────────────────────────

def load(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else []


sbom     = load('report/sbom.spdx.json', {})
cs_open  = load('report/code-scanning-open.json')
cs_dis   = load('report/code-scanning-dismissed.json')
dep_open = load('report/dependabot-open.json')
dep_dis  = load('report/dependabot-dismissed.json')

packages  = sbom.get('packages', [])
pkg_count = len(packages)


# ── GitHub context ─────────────────────────────────────────────────────────────

repo    = os.environ.get('GH_REPO', 'unknown/repo')
ref     = os.environ.get('GH_REF', 'unknown')
sha     = os.environ.get('GH_SHA', '')[:8]
run_id  = os.environ.get('GH_RUN_ID', '')
run_url = f'https://github.com/{repo}/actions/runs/{run_id}'
date    = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


# ── Severity helpers ───────────────────────────────────────────────────────────

SEV_ORDER = ['critical', 'error', 'high', 'warning', 'medium', 'low', 'note', 'unknown']
SEV_FG    = {
    'critical': '#cf222e', 'error':   '#cf222e',
    'high':     '#bc4c00', 'warning': '#9a6700',
    'medium':   '#9a6700', 'low':     '#0969da',
    'note':     '#57606a', 'unknown': '#57606a',
}
SEV_BG = {
    'critical': '#ffeef0', 'error':   '#ffeef0',
    'high':     '#fff3cd', 'warning': '#fff3cd',
    'medium':   '#fff8c5', 'low':     '#ddf4ff',
    'note':     '#f6f8fa', 'unknown': '#f6f8fa',
}


def e(s):
    """HTML-escape a value."""
    return html_lib.escape(str(s or ''))


def sev_rank(s):
    return SEV_ORDER.index(s) if s in SEV_ORDER else 99


def badge(sev):
    sev = (sev or 'unknown').lower()
    col = SEV_FG.get(sev, '#57606a')
    return (f'<span style="background:{col};color:#fff;padding:2px 8px;border-radius:3px;'
            f'font-size:11px;font-weight:600;white-space:nowrap;">{e(sev.upper())}</span>')


def cs_sev(a):
    return (a.get('rule', {}).get('security_severity_level') or
            a.get('rule', {}).get('severity') or 'unknown').lower()


def dep_sev(a):
    return (a.get('security_advisory', {}).get('severity') or 'unknown').lower()


def count_by_sev(alerts, sev_fn):
    counts = {}
    for a in alerts:
        s = sev_fn(a)
        counts[s] = counts.get(s, 0) + 1
    return counts


cs_counts  = count_by_sev(cs_open,  cs_sev)
dep_counts = count_by_sev(dep_open, dep_sev)

total_crit = (cs_counts.get('critical', 0) + cs_counts.get('error', 0)
              + dep_counts.get('critical', 0))
total_high = cs_counts.get('high', 0) + dep_counts.get('high', 0)

status  = 'PASS' if (total_crit + total_high) == 0 else 'REVIEW REQUIRED'
st_col  = '#1a7f37' if status == 'PASS' else '#cf222e'
st_bg   = '#dafbe1' if status == 'PASS' else '#fff0f0'
st_icon = '✅' if status == 'PASS' else '⚠️'


# ── HTML building blocks ───────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 14px; line-height: 1.5; background: #f6f8fa; color: #24292f;
}
.wrap { max-width: 980px; margin: 0 auto; padding: 24px 32px; }
.card { background: #fff; border: 1px solid #d0d7de; border-radius: 6px;
        margin-bottom: 20px; overflow: hidden; }
.card-head { background: #f6f8fa; border-bottom: 1px solid #d0d7de; padding: 10px 16px;
             font-weight: 600; font-size: 14px; display: flex;
             justify-content: space-between; align-items: center; }
.card-body { padding: 16px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.meta-box { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px;
            padding: 10px 14px; }
.meta-label { font-size: 10px; color: #57606a; text-transform: uppercase; letter-spacing: .5px; }
.meta-value { font-size: 13px; font-weight: 600; font-family: ui-monospace, monospace;
              margin-top: 3px; word-break: break-all; }
.count-box { text-align: center; border-radius: 6px; padding: 12px 6px; }
.count-num { font-size: 28px; font-weight: 700; }
.count-lbl { font-size: 10px; text-transform: uppercase; letter-spacing: .5px; margin-top: 2px; }
.sev-label { font-size: 11px; font-weight: 600; color: #57606a; text-transform: uppercase;
             letter-spacing: .5px; margin-bottom: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #f6f8fa; text-align: left; padding: 8px 12px; font-size: 11px;
     font-weight: 600; color: #57606a; text-transform: uppercase; letter-spacing: .3px;
     border-bottom: 1px solid #d0d7de; }
td { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #f6f8fa; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
@media print {
  body { background: #fff; }
  .card { break-inside: avoid; }
  .no-print { display: none; }
}
"""


def card(title, body, count=None, padding=True):
    count_badge = ''
    if count is not None:
        count_badge = (f'<span style="background:#eaf5ff;color:#0969da;font-size:11px;'
                       f'font-weight:600;padding:2px 10px;border-radius:10px;">{count}</span>')
    body_style = 'padding:0' if not padding else ''
    return (f'<div class="card">'
            f'<div class="card-head"><span>{title}</span>{count_badge}</div>'
            f'<div class="card-body" style="{body_style}">{body}</div>'
            f'</div>')


def count_grid(counts, groups):
    """groups: list of (label, [sev_keys]) tuples"""
    boxes = ''
    for label, sevs in groups:
        n   = sum(counts.get(s, 0) for s in sevs)
        fg  = SEV_FG.get(sevs[0], '#57606a')
        bg  = SEV_BG.get(sevs[0], '#f6f8fa')
        boxes += (f'<div class="count-box" style="background:{bg};">'
                  f'<div class="count-num" style="color:{fg};">{n}</div>'
                  f'<div class="count-lbl" style="color:{fg};">{label}</div>'
                  f'</div>')
    return f'<div class="grid-4">{boxes}</div>'


def empty_row(cols, msg='No alerts'):
    return (f'<tr><td colspan="{cols}" style="text-align:center;color:#57606a;'
            f'padding:20px;">{msg}</td></tr>')


# ── Table renderers ────────────────────────────────────────────────────────────

def cs_table(alerts):
    if not alerts:
        return (f'<table><tbody>{empty_row(5)}</tbody></table>')
    rows = ''
    for a in sorted(alerts, key=lambda x: sev_rank(cs_sev(x))):
        num   = a.get('number', '')
        rule  = a.get('rule', {})
        sev   = cs_sev(a)
        desc  = e((rule.get('description') or rule.get('id', ''))[:100])
        loc   = a.get('most_recent_instance', {}).get('location', {})
        path  = e(loc.get('path', ''))
        line  = loc.get('start_line', '')
        url   = e(a.get('html_url', '#'))
        tool  = e(a.get('tool', {}).get('name', 'CodeQL'))
        loc_s = f'{path}:{line}' if path and line else path or '—'
        rows += (f'<tr>'
                 f'<td><a href="{url}">#{num}</a></td>'
                 f'<td>{badge(sev)}</td>'
                 f'<td>{desc}</td>'
                 f'<td style="font-size:11px;color:#57606a;">{loc_s}</td>'
                 f'<td style="font-size:11px;color:#57606a;">{tool}</td>'
                 f'</tr>')
    return (f'<table>'
            f'<thead><tr><th>#</th><th>Severity</th><th>Description</th>'
            f'<th>Location</th><th>Tool</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


def dep_table(alerts):
    if not alerts:
        return f'<table><tbody>{empty_row(5)}</tbody></table>'
    rows = ''
    for a in sorted(alerts, key=lambda x: sev_rank(dep_sev(x))):
        num   = a.get('number', '')
        pkg   = a.get('dependency', {}).get('package', {})
        name  = e(pkg.get('name', ''))
        eco   = e(pkg.get('ecosystem', ''))
        adv   = a.get('security_advisory', {})
        sev   = dep_sev(a)
        cve   = e(adv.get('cve_id') or adv.get('ghsa_id', ''))
        summ  = e((adv.get('summary', ''))[:90])
        url   = e(a.get('html_url', '#'))
        vuln  = a.get('security_vulnerability', {})
        fix   = e((vuln.get('first_patched_version') or {}).get('identifier', '—'))
        rows += (f'<tr>'
                 f'<td><a href="{url}">#{num}</a></td>'
                 f'<td>{badge(sev)}<br>'
                 f'<span style="font-size:10px;color:#57606a;">{cve}</span></td>'
                 f'<td style="font-size:12px;"><strong>{name}</strong><br>'
                 f'<span style="color:#57606a;font-size:11px;">{eco}</span></td>'
                 f'<td style="font-size:12px;">{summ}</td>'
                 f'<td style="font-size:11px;">{fix}</td>'
                 f'</tr>')
    return (f'<table>'
            f'<thead><tr><th>#</th><th>Severity / CVE</th><th>Package</th>'
            f'<th>Summary</th><th>Fix Version</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


def sbom_table(pkgs):
    if not pkgs:
        return f'<table><tbody>{empty_row(3, "No packages in SBOM")}</tbody></table>'
    rows = ''
    for p in pkgs[:100]:
        name = e(p.get('name', ''))
        ver  = e(p.get('versionInfo', '—'))
        lic  = e(p.get('licenseConcluded') or p.get('licenseDeclared', ''))
        rows += (f'<tr>'
                 f'<td style="font-size:12px;">{name}</td>'
                 f'<td style="font-size:12px;color:#57606a;">{ver}</td>'
                 f'<td style="font-size:12px;color:#57606a;">{lic}</td>'
                 f'</tr>')
    if len(pkgs) > 100:
        rows += (f'<tr><td colspan="3" style="text-align:center;color:#57606a;'
                 f'font-size:12px;padding:8px;">… and {len(pkgs)-100} more — '
                 f'see sbom.spdx.json</td></tr>')
    return (f'<table>'
            f'<thead><tr><th>Package</th><th>Version</th><th>License</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


# ── Page sections ──────────────────────────────────────────────────────────────

meta_items = [
    ('Repository',    f'<a href="https://github.com/{e(repo)}">{e(repo)}</a>'),
    ('Ref / Tag',     e(ref)),
    ('Commit SHA',    e(sha)),
    ('Scan Date',     e(date)),
    ('Actions Run',   f'<a href="{e(run_url)}">{e(run_id)}</a>'),
    ('SBOM Packages', str(pkg_count)),
]
meta_html = ''.join(
    f'<div class="meta-box">'
    f'<div class="meta-label">{k}</div>'
    f'<div class="meta-value">{v}</div>'
    f'</div>'
    for k, v in meta_items
)

controls = [
    'Dependency Graph (SBOM)',
    'Dependabot Alerts (SCA)',
    'CodeQL SAST',
    'Copilot Autofix',
    'Secret Scanning',
    'Push Protection',
]
controls_html = ''.join(
    f'<div style="display:flex;align-items:center;gap:8px;font-size:13px;">'
    f'<span style="color:#1a7f37;font-size:15px;">✓</span>{e(c)}</div>'
    for c in controls
)

cs_summary = (
    f'<div style="margin-bottom:16px;">'
    f'<div class="sev-label">Code Scanning (SAST — CodeQL) · {len(cs_open)} open alerts</div>'
    + count_grid(cs_counts, [
        ('Critical', ['critical', 'error']),
        ('High',     ['high']),
        ('Medium',   ['medium', 'warning']),
        ('Low / Note', ['low', 'note']),
    ]) +
    f'</div>'
    f'<div>'
    f'<div class="sev-label">Dependency Vulnerabilities (SCA — Dependabot) · {len(dep_open)} open alerts</div>'
    + count_grid(dep_counts, [
        ('Critical', ['critical']),
        ('High',     ['high']),
        ('Medium',   ['medium']),
        ('Low',      ['low']),
    ]) +
    f'</div>'
)

status_msg = ('No critical or high severity open alerts detected.'
              if status == 'PASS'
              else f'{total_crit} critical · {total_high} high severity alerts require remediation.')


# ── Assemble final HTML ────────────────────────────────────────────────────────

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>CRA Evidence — {e(repo)} {e(ref)}</title>
  <style>{CSS}</style>
</head>
<body>

<div style="background:#0d1117;color:#e6edf3;padding:18px 32px;">
  <div style="font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">
    EU Cyber Resilience Act · Regulation (EU) 2024/2847 · Annex I Part II §2(3)
  </div>
  <h1 style="font-size:20px;font-weight:700;margin-bottom:4px;">Security Evidence Report</h1>
  <div style="font-size:13px;color:#8b949e;">{e(repo)} · {e(ref)} · {e(sha)} · {e(date)}</div>
</div>

<div class="wrap">

  <!-- Status banner -->
  <div style="background:{st_bg};border:1.5px solid {st_col};border-radius:6px;
              padding:12px 18px;margin-bottom:20px;display:flex;align-items:center;gap:12px;">
    <span style="font-size:20px;">{st_icon}</span>
    <div>
      <strong style="color:{st_col};font-size:15px;">{status}</strong>
      <div style="font-size:13px;color:#57606a;margin-top:1px;">{e(status_msg)}</div>
    </div>
  </div>

  {card('Report Metadata', f'<div class="grid-3">{meta_html}</div>')}

  {card('Security Controls Active',
        f'<div class="grid-3">{controls_html}</div>'
        f'<div style="margin-top:10px;font-size:11px;color:#57606a;">'
        f'Verify this list matches your actual enabled features under Settings → Code security.'
        f'</div>')}

  {card('Alert Summary', cs_summary)}

  {card('Code Scanning — Open &nbsp;<span style="font-size:12px;font-weight:400;color:#57606a;">CRA §2(3) SAST Evidence</span>',
        cs_table(cs_open), count=len(cs_open), padding=False)}

  {card('Code Scanning — Dismissed &nbsp;<span style="font-size:12px;font-weight:400;color:#57606a;">Audit Trail</span>',
        cs_table(cs_dis), count=len(cs_dis), padding=False)}

  {card('Dependabot — Open &nbsp;<span style="font-size:12px;font-weight:400;color:#57606a;">CRA §2(3) SCA Evidence</span>',
        dep_table(dep_open), count=len(dep_open), padding=False)}

  {card('Dependabot — Dismissed &nbsp;<span style="font-size:12px;font-weight:400;color:#57606a;">Audit Trail</span>',
        dep_table(dep_dis), count=len(dep_dis), padding=False)}

  {card(f'SBOM — Software Bill of Materials &nbsp;<span style="font-size:12px;font-weight:400;color:#57606a;">CRA Annex I Part II §1</span>',
        sbom_table(packages), count=f'{pkg_count} packages', padding=False)}

  <!-- Footer -->
  <div style="font-size:11px;color:#57606a;padding-top:16px;border-top:1px solid #d0d7de;">
    <strong>CRA Compliance Note:</strong> This report provides evidence for EU Cyber Resilience Act
    (Regulation EU 2024/2847) Annex I Part II §2(3) — <em>"Apply effective and regular security
    tests and reviews during development."</em>
    Full obligations apply from <strong>11 December 2027</strong>.
    Article 14 reporting obligations from <strong>11 September 2026</strong>.
    Retain in product technical file alongside the SBOM (sbom.spdx.json).
    This report does not constitute legal advice.<br><br>
    <strong>Evidence chain:</strong> Dependency Graph (SBOM) · CodeQL SAST · Dependabot SCA ·
    <a href="{e(run_url)}">Actions run {e(run_id)}</a> ·
    Generated {e(date)} · Commit {e(sha)} · Ref {e(ref)}
  </div>

</div>
</body>
</html>"""

out_path = 'report/cra-evidence-report.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(page)

print(f'✓  Report  → {out_path}  ({len(page):,} bytes)')
print(f'   Status:     {status}')
print(f'   SBOM:       {pkg_count} packages')
print(f'   CodeQL:     {len(cs_open)} open  /  {len(cs_dis)} dismissed')
print(f'   Dependabot: {len(dep_open)} open  /  {len(dep_dis)} dismissed')

if status != 'PASS':
    sys.exit(1)   # fail the workflow step if critical/high alerts are open
