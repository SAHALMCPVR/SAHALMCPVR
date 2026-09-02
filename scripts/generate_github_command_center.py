import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timezone

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("GITHUB_USERNAME", "SAHALMCPVR")

QUERY = """
query($login:String!) {
  user(login:$login) {
    login
    createdAt
    repositories(
      first:100
      ownerAffiliations:[OWNER]
      privacy:PUBLIC
      isFork:false
    ) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first:20, orderBy:{field:SIZE, direction:DESC}) {
          edges {
            size
            node { name color }
          }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
    }
  }
}
"""

def graphql():
    payload = json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "github-command-center",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        result = json.load(r)
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    return result["data"]["user"]

def esc(s):
    return (str(s).replace("&","&amp;").replace("<","&lt;")
            .replace(">","&gt;").replace('"',"&quot;"))

def svg_text(x, y, text, size=16, fill="#E6EDF3", weight="400", anchor="start"):
    return f'<text x="{x}" y="{y}" font-family="Inter,Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{esc(text)}</text>'

def rounded_card(x, y, w, h):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#0D1117" stroke="#1F6FEB" stroke-opacity=".35"/>'

def main():
    user = graphql()
    repos = user["repositories"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    total = cal["totalContributions"]

    lang_bytes = Counter()
    lang_colors = {}
    for repo in repos["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_bytes[name] += edge["size"]
            lang_colors[name] = edge["node"].get("color") or "#58A6FF"

    top = lang_bytes.most_common(6)
    total_bytes = sum(lang_bytes.values()) or 1

    days = []
    for week in cal["weeks"]:
        days.extend(week["contributionDays"])
    days = days[-371:]

    W, H = 1000, 610
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<defs>',
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#020617"/><stop offset="1" stop-color="#0B1F2A"/></linearGradient>',
        '<filter id="glow"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        '</defs>',
        '<rect width="1000" height="610" rx="24" fill="url(#bg)"/>',
        '<rect x="1" y="1" width="998" height="608" rx="24" fill="none" stroke="#00F7FF" stroke-opacity=".25"/>',
        svg_text(38, 48, "📊  GITHUB COMMAND CENTER", 24, "#00F7FF", "700"),
        svg_text(38, 76, USERNAME, 18, "#FFFFFF", "700"),
        svg_text(962, 48, "LIVE • GitHub GraphQL", 12, "#8B949E", "600", "end"),
        rounded_card(30, 100, 940, 245),
        svg_text(55, 135, f"{total:,} Contributions in the last year", 20, "#FFFFFF", "700"),
        svg_text(55, 162, "Contribution activity", 12, "#8B949E"),
    ]

    # Contribution heatmap
    start_x, start_y = 55, 185
    cell, gap = 11, 3
    max_count = max([d["contributionCount"] for d in days] or [1])
    # 53 columns x 7 rows, chronological
    for i, d in enumerate(days):
        col = i // 7
        row = i % 7
        if col > 76:
            break
        count = d["contributionCount"]
        if count == 0:
            fill = "#161B22"
        else:
            level = min(4, max(1, int((count / max_count) * 4)))
            fill = ["#0E4429","#006D32","#26A641","#39D353"][level-1]
        x = start_x + col*(cell+gap)
        y = start_y + row*(cell+gap)
        out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{fill}"/>')

    commits = user["contributionsCollection"]["totalCommitContributions"]
    issues = user["contributionsCollection"]["totalIssueContributions"]
    prs = user["contributionsCollection"]["totalPullRequestContributions"]
    reviews = user["contributionsCollection"]["totalPullRequestReviewContributions"]

    stats = [
        ("REPOSITORIES", repos["totalCount"]),
        ("COMMITS", commits),
        ("PULL REQUESTS", prs),
        ("ISSUES", issues),
    ]
    sx = 55
    for label, value in stats:
        out.append(svg_text(sx, 306, f"{value:,}", 22, "#00F7FF", "700"))
        out.append(svg_text(sx, 327, label, 10, "#8B949E", "600"))
        sx += 205

    # Lower cards
    out += [
        rounded_card(30, 365, 455, 215),
        rounded_card(515, 365, 455, 215),
        svg_text(55, 402, "TOP LANGUAGES BY REPOSITORY", 14, "#00F7FF", "700"),
        svg_text(540, 402, "CONTRIBUTION BREAKDOWN", 14, "#00F7FF", "700"),
    ]

    # Donut
    cx, cy, r = 150, 475, 70
    circumference = 2 * 3.1415926535 * r
    offset = 0
    for name, b in top:
        pct = b / total_bytes
        dash = pct * circumference
        color = lang_colors.get(name, "#58A6FF")
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="24" stroke-dasharray="{dash} {circumference-dash}" stroke-dashoffset="{-offset}" transform="rotate(-90 {cx} {cy})"/>')
        offset += dash
    out.append(svg_text(cx, cy-2, f"{len(top)}", 24, "#FFFFFF", "700", "middle"))
    out.append(svg_text(cx, cy+18, "languages", 10, "#8B949E", "400", "middle"))

    ly = 435
    for name, b in top:
        pct = b / total_bytes * 100
        out.append(f'<circle cx="255" cy="{ly-5}" r="5" fill="{lang_colors.get(name,"#58A6FF")}"/>')
        out.append(svg_text(270, ly, name, 13, "#E6EDF3", "600"))
        out.append(svg_text(455, ly, f"{pct:.1f}%", 12, "#8B949E", "400", "end"))
        ly += 24

    breakdown = [
        ("Commits", commits),
        ("Pull requests", prs),
        ("Issues", issues),
        ("Reviews", reviews),
    ]
    by = 440
    for label, value in breakdown:
        out.append(svg_text(540, by, label, 14, "#E6EDF3", "600"))
        out.append(svg_text(920, by, f"{value:,}", 14, "#00F7FF", "700", "end"))
        out.append(f'<rect x="540" y="{by+9}" width="380" height="5" rx="3" fill="#161B22"/>')
        ratio = min(1, value / max(1, total))
        out.append(f'<rect x="540" y="{by+9}" width="{380*ratio:.1f}" height="5" rx="3" fill="#00F7FF"/>')
        by += 31

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out.append(svg_text(38, 600, f"Updated automatically • {generated}", 10, "#6E7681"))
    out.append("</svg>")

    os.makedirs("assets", exist_ok=True)
    with open("assets/github-command-center.svg", "w", encoding="utf-8") as f:
        f.write("\n".join(out))

if __name__ == "__main__":
    main()
