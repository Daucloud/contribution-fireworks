"""Render a GitHub contribution calendar as a looping fireworks SVG.

Usage: GITHUB_TOKEN=... python3 fireworks.py <user> <outdir> [--palette seasons|gold|rainbow]

Writes fireworks.svg (light) and fireworks-dark.svg into <outdir>.
Standard library only.
"""
import argparse, colorsys, datetime, json, math, os, random, urllib.request

CELL, GAP = 11, 3
STEP = CELL + GAP
PAD_X, GRID_Y, GROUND_Y = 10, 34, 178
CYCLE = 14.0          # seconds per loop
SWEEP = 7.0           # seconds for the whole year to launch
RISE, BURST = 0.045, 0.16   # fractions of CYCLE
PARTICLES = 12
MAX_BURSTS = 60

THEMES = {
    "light": dict(empty="#ebedf0", star=None, light=(0.50, 0.55), spark=0.52),
    "dark": dict(empty="#161b22", star="#c9d1d9", light=(0.60, 0.70), spark=0.65),
}


def graphql(token, query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req))["data"]


def fetch(user, token):
    data = graphql(token, """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
      weeks{contributionDays{contributionCount weekday date}}}}}}""", u=user)
    if not data or not data["user"]:
        raise SystemExit(f"GitHub user {user!r} not found")
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [[(d["weekday"], d["contributionCount"], d["date"]) for d in w["contributionDays"]] for w in weeks]


def hex_color(h, l, s=0.85):
    r, g, b = colorsys.hls_to_rgb(h % 1, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def hue_of(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)[0]


def mix_hue(a, b, f):
    d = (b - a + .5) % 1 - .5
    return a + d * f


# Mid-month anchors: frost, lavender, orchid, sakura, coral, gold,
# sun, amber, tangerine, maple, dusk, ice.
SEASONS = [hue_of(c) for c in ("#7aa2ff", "#9a8cff", "#e48cff", "#ff8fc7", "#ff9f8f", "#ffc46b",
                               "#ffe066", "#ffb347", "#ff8c5a", "#ff6b6b", "#c77dff", "#6fb7ff")]


def palette(name, weeks):
    """Return (wi, date) -> (hue, saturation scale) for the chosen palette."""
    if name == "rainbow":
        return lambda wi, date: (0.92 + wi / len(weeks) * 0.85, 1)
    if name == "gold":
        return lambda wi, date: (0.115, 1)
    if name == "seasons":
        def season(wi, date):
            d = datetime.date.fromisoformat(date)
            pos = (d.month - 1) + (d.day - 15) / 30
            i, f = math.floor(pos) % 12, pos - math.floor(pos)
            return mix_hue(SEASONS[i], SEASONS[(i + 1) % 12], f), 1
        return season
    raise ValueError(f"unknown palette {name!r}")


def pct(x):
    return f"{x * 100:.2f}%"


def render(weeks, theme, color_of):
    t = THEMES[theme]
    rng = random.Random(42)
    width = PAD_X * 2 + len(weeks) * STEP - GAP
    height = GROUND_Y + 8
    peak = max((c for w in weeks for _, c, _ in w), default=1) or 1

    css = [
        f".a{{animation-duration:{CYCLE}s;animation-iteration-count:infinite;"
        "animation-fill-mode:backwards;animation-timing-function:linear}",
        f".rk{{animation-name:rk;animation-timing-function:cubic-bezier(.2,.7,.4,1)}}",
        f"@keyframes rk{{0%{{opacity:0;transform:translateY(var(--d))}}.3%{{opacity:1}}"
        f"{pct(RISE)}{{opacity:1;transform:translateY(0)}}{pct(RISE + .005)},100%{{opacity:0;transform:translateY(0)}}}}",
        f".fl{{animation-name:fl;transform-box:fill-box;transform-origin:center}}",
        f"@keyframes fl{{0%,{pct(RISE)}{{opacity:0;transform:scale(.1)}}{pct(RISE + .005)}{{opacity:.55;transform:scale(.3)}}"
        f"{pct(RISE + .05)}{{opacity:0;transform:scale(1)}}100%{{opacity:0}}}}",
        f".c,.q{{transform-box:fill-box;transform-origin:center}}",
    ]
    # Cells stay lit for most of the loop, so they use absolute keyframes on a
    # shared clock instead of animation-delay; otherwise each cell would fade
    # out on its own schedule and the finished calendar would never be seen whole.
    cell_frames = {}

    def cell_anim(kind, delay):
        start = round((delay / CYCLE + RISE) * 200) / 200
        name = f"{kind}{int(start * 200)}"
        if name not in cell_frames:
            peak_scale = 1.6 if kind == "c" else 1.15
            cell_frames[name] = (
                f"@keyframes {name}{{0%,{pct(start)}{{opacity:0;transform:scale(.2)}}"
                f"{pct(start + .02)}{{opacity:1;transform:scale({peak_scale})}}"
                f"{pct(start + .06)},82%{{opacity:1;transform:scale(1)}}90%,100%{{opacity:0;transform:scale(.6)}}}}")
        return f"animation-name:{name}"
    for i in range(PARTICLES):
        ang = 2 * math.pi * i / PARTICLES
        for ring, (dist, life) in enumerate([(1.0, 1.0), (0.55, 0.8)]):
            a = ang + ring * math.pi / PARTICLES
            dx, dy = math.cos(a) * dist, math.sin(a) * dist
            mid, end = RISE + BURST * life * .55, RISE + BURST * life
            css.append(
                f"@keyframes p{ring}{i}{{0%,{pct(RISE)}{{opacity:0;transform:translate(0,0)}}"
                f"{pct(RISE + .004)}{{opacity:1;transform:translate(0,0)}}"
                f"{pct(mid)}{{opacity:1;transform:translate(calc({dx:.2f}*var(--r)),calc({dy:.2f}*var(--r)))}}"
                f"{pct(end)}{{opacity:0;transform:translate(calc({dx * 1.15:.2f}*var(--r)),calc({dy * 1.15:.2f}*var(--r) + 7px))}}"
                f"100%{{opacity:0}}}}"
                f".p{ring}{i}{{animation-name:p{ring}{i};animation-timing-function:cubic-bezier(.15,.75,.35,1)}}"
            )
    if t["star"]:
        css.append("@keyframes tw{0%,100%{opacity:.15}50%{opacity:.8}}.s{animation:tw 3s ease-in-out infinite}")

    out = []

    if t["star"]:
        for _ in range(40):
            x, y = rng.uniform(0, width), rng.uniform(2, GRID_Y + 7 * STEP)
            out.append(f'<circle class="s" cx="{x:.1f}" cy="{y:.1f}" r="{rng.uniform(.4, .9):.2f}" '
                       f'fill="{t["star"]}" style="animation-delay:-{rng.uniform(0, 3):.2f}s"/>')

    for wi, week in enumerate(weeks):
        for wd, _, _ in week:
            x, y = PAD_X + wi * STEP, GRID_Y + wd * STEP
            out.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{t["empty"]}"/>')

    # Busy calendars would turn into a wall of sparks: past MAX_BURSTS active
    # days, launch only from the brightest ones and never from neighbouring cells.
    days = sorted(((c, wi, wd) for wi, w in enumerate(weeks) for wd, c, _ in w if c), reverse=True)
    if len(days) <= MAX_BURSTS:
        bursts = {(wi, wd) for _, wi, wd in days}
    else:
        bursts = set()
        for _, wi, wd in days:
            if len(bursts) == MAX_BURSTS:
                break
            if all(abs(wi - bw) > 1 or abs(wd - bd) > 1 for bw, bd in bursts):
                bursts.add((wi, wd))

    lmin, lmax = t["light"]
    for wi, week in enumerate(weeks):
        for wd, count, date in week:
            if not count:
                continue
            hue, sat = color_of(wi, date)
            x, y = PAD_X + wi * STEP, GRID_Y + wd * STEP
            cx, cy = x + CELL / 2, y + CELL / 2
            k = math.sqrt(count / peak)
            color = hex_color(hue, lmax - (lmax - lmin) * k, (0.6 + 0.35 * k) * sat)
            spark = hex_color(hue + rng.uniform(-.04, .04), t["spark"], 0.85 * sat)
            delay = wi / len(weeks) * SWEEP + wd * 0.03 + rng.uniform(0, .12)
            st = f'animation-delay:{delay:.2f}s'
            if (wi, wd) not in bursts:
                out.append(f'<rect class="a q" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                           f'fill="{color}" style="{cell_anim("q", delay)}"/>')
                continue
            trail = "".join(f'<circle cx="{cx}" cy="{cy + 2.5 * j}" r="{1.3 - .25 * j:.2f}" fill="{spark}" '
                            f'opacity="{1 - .22 * j:.2f}"/>' for j in range(1, 5))
            out.append(f'<g class="a rk" style="{st};--d:{GROUND_Y - cy:.0f}px">{trail}'
                       f'<circle cx="{cx}" cy="{cy}" r="1.5" fill="{spark}"/></g>')
            out.append(f'<circle class="a fl" cx="{cx}" cy="{cy}" r="{10 + 8 * k:.1f}" fill="{spark}" style="{st}"/>')
            radius = f"--r:{14 + 16 * k:.1f}px"
            for ring in range(2):
                for i in range(PARTICLES):
                    out.append(f'<circle class="a p{ring}{i}" cx="{cx}" cy="{cy}" r="{(1.3 if ring == 0 else 1) + k * .5:.2f}" '
                               f'fill="{spark}" style="{st};{radius}"/>')
            out.append(f'<rect class="a c" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                       f'fill="{color}" style="{cell_anim("c", delay)}"/>')

    css.extend(cell_frames.values())
    head = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            f"<style>{''.join(css)}</style>"]
    return "\n".join(head + out + ["</svg>"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render contribution fireworks SVGs.")
    parser.add_argument("user")
    parser.add_argument("outdir")
    parser.add_argument("--palette", default="seasons", choices=["seasons", "gold", "rainbow"])
    args = parser.parse_args()
    weeks = fetch(args.user, os.environ["GITHUB_TOKEN"])
    color_of = palette(args.palette, weeks)
    os.makedirs(args.outdir, exist_ok=True)
    for theme in THEMES:
        name = "fireworks" + ("" if theme == "light" else "-dark") + ".svg"
        with open(os.path.join(args.outdir, name), "w") as f:
            f.write(render(weeks, theme, color_of))
