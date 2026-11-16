#!/usr/bin/env python3
"""Gera assets/kp.svg (índice Kp da NOAA) e assets/stats.svg (stats do GitHub).

Roda pelo GitHub Actions (.github/workflows/update.yml). Só usa a biblioteca padrão.
"""
import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from html import escape

USER = os.environ.get("GH_USER", "mraiahh")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")

BG = "#0d1117"
BORDER = "#2d2a55"
TITLE = "#a78bfa"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def fetch(url, headers=None, body=None):
    req = urllib.request.Request(url, headers=headers or {}, data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------- Kp (NOAA)
def load_kp():
    data = fetch("https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json")
    rows = []
    for item in data:
        if isinstance(item, dict):  # formato novo: lista de objetos
            t, k = item.get("time_tag"), item.get("Kp", item.get("kp_index"))
        else:  # formato antigo: lista de listas, primeira linha é cabeçalho
            if item and item[0] == "time_tag":
                continue
            t, k = item[0], item[1]
        try:
            rows.append((str(t), float(k)))
        except (TypeError, ValueError):
            continue
    return rows[-16:]


def kp_style(kp):
    if kp < 4:
        return "#5eead4", "Calmo"
    if kp < 5:
        return "#fde68a", "Ativo"
    if kp < 6:
        return "#fdba74", "Tempestade G1"
    if kp < 7:
        return "#fb923c", "Tempestade G2"
    if kp < 8:
        return "#f87171", "Tempestade G3"
    if kp < 9:
        return "#ef4444", "Tempestade G4"
    return "#dc2626", "Tempestade G5"


def kp_svg(rows):
    last_t, last_k = rows[-1]
    color, status = kp_style(last_k)
    bars = []
    x0, bw, gap, base, hmax = 190, 11, 3, 160, 100
    for i, (_, k) in enumerate(rows):
        h = max(2, k / 9 * hmax)
        c, _ = kp_style(k)
        bars.append(
            f'<rect x="{x0 + i * (bw + gap)}" y="{base - h:.1f}" width="{bw}" '
            f'height="{h:.1f}" rx="2" fill="{c}" fill-opacity="0.85"/>'
        )
    stamp = last_t[:16].replace("T", " ")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 200" width="440" height="200" role="img" aria-label="Índice Kp atual: {last_k:.2f} ({escape(status)})">
  <rect x="0.5" y="0.5" width="439" height="199" rx="12" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="34" font-family="{FONT}" font-size="14" font-weight="600" fill="{TITLE}">Índice Kp · agora</text>
  <text x="24" y="100" font-family="{FONT}" font-size="52" font-weight="700" fill="{color}">{last_k:.1f}</text>
  <text x="24" y="126" font-family="{FONT}" font-size="14" fill="{TEXT}">{escape(status)}</text>
  <text x="24" y="150" font-family="{FONT}" font-size="11" fill="{MUTED}">campo geomagnético</text>
  <line x1="190" y1="{base + 0.5}" x2="414" y2="{base + 0.5}" stroke="{BORDER}"/>
  {''.join(bars)}
  <text x="190" y="180" font-family="{FONT}" font-size="10" fill="{MUTED}">~48 h atrás</text>
  <text x="414" y="180" text-anchor="end" font-family="{FONT}" font-size="10" fill="{MUTED}">agora</text>
  <text x="24" y="186" font-family="{FONT}" font-size="10" fill="{MUTED}">{stamp} UTC · NOAA SWPC</text>
</svg>
"""


# ------------------------------------------------------------ Stats (GitHub)
QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      totalIssueContributions
    }
    repositories(first:100, ownerAffiliations:OWNER, isFork:false){
      totalCount
      nodes{ stargazerCount primaryLanguage{ name color } }
    }
  }
}
"""


def load_stats():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    res = fetch(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
        body=body,
    )
    u = res["data"]["user"]
    cc = u["contributionsCollection"]
    repos = u["repositories"]["nodes"]
    langs = Counter()
    colors = {}
    for r in repos:
        pl = r.get("primaryLanguage")
        if pl:
            langs[pl["name"]] += 1
            colors[pl["name"]] = pl["color"] or "#a78bfa"
    return {
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": u["repositories"]["totalCount"],
        "langs": langs.most_common(5),
        "colors": colors,
    }


def stats_svg(s):
    items = [
        ("Commits (último ano)", s["commits"]),
        ("Pull requests", s["prs"]),
        ("Issues", s["issues"]),
        ("Estrelas", s["stars"]),
    ]
    cells = []
    for i, (label, value) in enumerate(items):
        x = 24 + (i % 2) * 200
        y = 62 + (i // 2) * 40
        cells.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="22" font-weight="700" fill="#5eead4">{value}</text>'
            f'<text x="{x}" y="{y + 15}" font-family="{FONT}" font-size="11" fill="{MUTED}">{escape(label)}</text>'
        )
    total = sum(n for _, n in s["langs"]) or 1
    bar, legend, x = [], [], 24
    for i, (name, n) in enumerate(s["langs"]):
        w = 392 * n / total
        c = s["colors"].get(name, "#a78bfa")
        bar.append(f'<rect x="{x:.1f}" y="152" width="{max(w - 2, 2):.1f}" height="8" rx="4" fill="{c}"/>')
        lx = 24 + (i % 3) * 135
        ly = 180 + (i // 3) * 14
        legend.append(
            f'<circle cx="{lx + 4}" cy="{ly - 3}" r="4" fill="{c}"/>'
            f'<text x="{lx + 14}" y="{ly}" font-family="{FONT}" font-size="11" fill="{TEXT}">{escape(name)} {100 * n / total:.0f}%</text>'
        )
        x += w
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 210" width="440" height="210" role="img" aria-label="Estatísticas do GitHub de {escape(USER)}">
  <rect x="0.5" y="0.5" width="439" height="209" rx="12" fill="{BG}" stroke="{BORDER}"/>
  <text x="24" y="34" font-family="{FONT}" font-size="14" font-weight="600" fill="{TITLE}">GitHub · {escape(USER)}</text>
  {''.join(cells)}
  {''.join(bar)}
  {''.join(legend)}
</svg>
"""


def write(name, content):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(content)
    print("ok:", name)


if __name__ == "__main__":
    failed = False
    try:
        write("kp.svg", kp_svg(load_kp()))
    except Exception as e:  # noqa: BLE001
        failed = True
        print("kp falhou:", e)
    try:
        write("stats.svg", stats_svg(load_stats()))
    except Exception as e:  # noqa: BLE001
        failed = True
        print("stats falhou:", e)
    if failed:
        raise SystemExit(1)
    print("gerado em", datetime.now(timezone.utc).isoformat(timespec="minutes"))
