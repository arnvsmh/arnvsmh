#!/usr/bin/env python3
"""
build_banner.py — generates the banner for the arnvsmh GitHub profile.

Design brief: the banner is a quiver plot of a two-dimensional turbulent
velocity field — the same kind of figure that comes out of the LIFT-550
work — with streamlines integrated through it and a hairline panel floating
over the top. The field is the subject, computed rather than drawn.

The field is a superposition of Lamb-Oseen vortices on a shear profile.
Segment angle is the local velocity direction; segment length and tone track
local speed. Streamlines are RK2 integrations through the same field, so the
arrows and the lines can't disagree with each other.

Hard constraints (these are what make it work on GitHub):
  * No <script>, no <foreignObject>, no external URLs. GitHub serves README
    images through the camo proxy inside a sandboxed <img>. Anything fetched
    at render time silently fails — including webfonts, which is why the type
    is a system mono stack carrying its personality through tracking alone.
  * Animation is CSS, not SMIL, so @media (prefers-reduced-motion: reduce)
    can switch it off. Every animated element's base style is its finished
    state, so the reduced-motion render is the completed frame.

Usage:
    python3 tools/build_banner.py            # writes assets/*.svg
    python3 tools/build_banner.py --out DIR
"""

from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

NAME = "ARNAV SIMHA"
DISCIPLINES = "MACHINE LEARNING / COMPUTATIONAL PHYSICS / MOLECULAR INTELLIGENCE"
TAGLINE = "research -> simulation -> discovery"
EYEBROW = "// FLOW RECONSTRUCTED"
STAMP = "RE_TAU 550 / DNS"

W, H = 1200, 420

# Panel geometry — the inset the type sits inside.
PX0, PY0, PX1, PY1 = 180.0, 112.0, 1020.0, 308.0

# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Theme:
    key: str
    bg: str
    field: tuple[str, str, str, str]  # slowest -> fastest
    accent: str                       # streamlines
    panel: str
    panel_edge: str
    ink: str
    ink_soft: str
    ink_faint: str


DARK = Theme(
    key="dark",
    bg="#080B0C",
    field=("#2A3436", "#3B4749", "#51605F", "#11897E"),
    accent="#00D2BE",
    panel="#070A0B",
    panel_edge="#1E2729",
    ink="#E7EBEC",
    ink_soft="#8C979B",
    ink_faint="#5C6669",
)

LIGHT = Theme(
    key="light",
    bg="#FAFBFB",
    field=("#D3D9DA", "#B4BEC0", "#93A0A2", "#4FAFA5"),
    accent="#00998A",
    panel="#FFFFFF",
    panel_edge="#DCE2E3",
    ink="#0A0E0F",
    ink_soft="#4B5457",
    ink_faint="#7C8588",
)

# ---------------------------------------------------------------------------
# Velocity field
# ---------------------------------------------------------------------------

# (x, y, circulation, core radius). Alternating signs on a blue-noise
# placement, some seeded off-canvas so the structure runs past the edges
# rather than stopping at them. Chosen by searching layouts for two
# properties: an isotropic angle distribution (no direction dominates, so
# the field never reads as scan lines) and even speed coverage top to
# bottom (no dead band at the walls).
VORTICES = [
    (1231.0, 222.8, -6812.7, 78.7),
    (344.3, 91.2, 5214.1, 74.9),
    (354.5, 298.0, -6003.5, 90.6),
    (789.1, -14.7, 5806.7, 71.2),
    (1125.5, 53.6, -8015.0, 90.8),
    (78.3, 459.5, 5786.8, 87.8),
    (181.7, 334.1, -5563.6, 65.0),
    (550.4, 209.0, 8302.8, 58.1),
    (3.8, 321.0, -8710.4, 99.4),
    (991.0, 443.0, 7814.1, 71.9),
    (166.4, 89.0, -7909.4, 90.7),
    (1003.5, 157.7, 7901.9, 68.9),
    (-6.4, 140.1, -5370.2, 101.1),
    (713.8, 348.2, 8800.3, 96.1),
]

SHEAR = 6.0  # gentle mean advection; the vortices carry the structure


def velocity(x: float, y: float) -> tuple[float, float]:
    """Lamb-Oseen vortices superposed on a shear profile."""
    u = SHEAR
    v = 0.0

    for vx, vy, gamma, core in VORTICES:
        dx, dy = x - vx, y - vy
        r2 = dx * dx + dy * dy + 1e-6
        decay = 1.0 - math.exp(-r2 / (core * core))
        f = gamma * decay / (2.0 * math.pi * r2)
        u += -f * dy
        v += f * dx

    return u, v


def speed_range(step: int) -> tuple[float, float]:
    """Sample the field so tone buckets key to the real distribution."""
    speeds = []
    y = step / 2
    while y < H:
        x = step / 2
        while x < W:
            u, v = velocity(x, y)
            speeds.append(math.hypot(u, v))
            x += step
        y += step
    speeds.sort()
    return speeds[len(speeds) // 20], speeds[len(speeds) * 19 // 20]


def streamline(x: float, y: float, steps: int, h: float) -> list[tuple[float, float]]:
    """RK2 integration through the same field the quiver plot draws."""
    pts = [(x, y)]
    for _ in range(steps):
        u1, v1 = velocity(x, y)
        s1 = math.hypot(u1, v1) + 1e-9
        mx, my = x + h * u1 / s1 * 0.5, y + h * v1 / s1 * 0.5
        u2, v2 = velocity(mx, my)
        s2 = math.hypot(u2, v2) + 1e-9
        x, y = x + h * u2 / s2, y + h * v2 / s2
        if not (-40 < x < W + 40 and -40 < y < H + 40):
            break
        pts.append((x, y))
    return pts


def polyline(pts: list[tuple[float, float]]) -> str:
    head = f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    return head + "".join(f" L {x:.1f} {y:.1f}" for x, y in pts[1:])


def path_length(pts: list[tuple[float, float]]) -> float:
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


# ---------------------------------------------------------------------------
# SVG assembly
# ---------------------------------------------------------------------------

STEP = 24          # quiver grid spacing
PANEL_PAD = 16.0   # segments this close to the panel are dropped

STREAM_SEEDS = [
    (-20.0, 132.0), (-20.0, 264.0), (-20.0, 344.0),
    (240.0, 18.0), (620.0, 404.0), (900.0, 22.0),
]


def quiver(theme: Theme) -> tuple[str, int]:
    lo, hi = speed_range(STEP * 2)
    span = max(hi - lo, 1e-6)
    segments: list[str] = []

    y = STEP / 2
    while y < H:
        x = STEP / 2
        while x < W:
            # drop anything the panel would cover — saves a third of the file
            if not (PX0 - PANEL_PAD < x < PX1 + PANEL_PAD
                    and PY0 - PANEL_PAD < y < PY1 + PANEL_PAD):
                u, v = velocity(x, y)
                s = math.hypot(u, v)
                frac = min(1.0, max(0.0, (s - lo) / span))
                bucket = min(3, int(frac * 4))
                length = 8.0 + 8.0 * frac
                ux, uy = u / (s + 1e-9), v / (s + 1e-9)
                hx, hy = ux * length / 2, uy * length / 2
                segments.append(
                    f'<path class="q{bucket}" d="M{x - hx:.1f} {y - hy:.1f}'
                    f'l{2 * hx:.1f} {2 * hy:.1f}"/>'
                )
            x += STEP
        y += STEP

    return "".join(segments), len(segments)


def build(theme: Theme) -> str:
    t = theme
    field_svg, _ = quiver(t)

    streams = []
    for i, (sx, sy) in enumerate(STREAM_SEEDS):
        pts = streamline(sx, sy, 260, 6.0)
        if len(pts) < 12:
            continue
        length = path_length(pts)
        streams.append(
            f'<path class="sl" d="{polyline(pts)}" '
            f'style="stroke-dasharray:{length * 0.16:.0f} {length * 0.84:.0f};'
            f'animation-duration:{15 + i * 4}s;animation-delay:-{i * 3}s"/>'
        )
    streams_svg = "".join(streams)

    panel_w, panel_h = PX1 - PX0, PY1 - PY0
    panel_perim = 2 * (panel_w + panel_h)

    css = f"""
    .q0{{stroke:{t.field[0]}}}.q1{{stroke:{t.field[1]}}}
    .q2{{stroke:{t.field[2]}}}.q3{{stroke:{t.field[3]}}}
    .sl{{fill:none;stroke:{t.accent};stroke-width:1.2;stroke-opacity:.5;
      stroke-linecap:round;stroke-dashoffset:0;
      animation-name:drift;animation-timing-function:linear;
      animation-iteration-count:infinite}}
    @keyframes drift{{from{{stroke-dashoffset:0}}to{{stroke-dashoffset:-2400}}}}
    .edge{{stroke-dasharray:{panel_perim:.0f};stroke-dashoffset:0;
      animation:edge 1.8s cubic-bezier(.16,1,.3,1) .1s backwards}}
    @keyframes edge{{from{{stroke-dashoffset:{panel_perim:.0f}}}}}
    .up{{animation:up .8s cubic-bezier(.16,1,.3,1) backwards}}
    .u1{{animation-delay:.30s}}.u2{{animation-delay:.42s}}
    .u3{{animation-delay:.54s}}.u4{{animation-delay:.66s}}
    @keyframes up{{from{{opacity:0;transform:translateY(7px)}}}}
    @media (prefers-reduced-motion:reduce){{
      .sl,.edge,.up{{animation:none}}
    }}
    """.strip()

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"
     width="{W}" height="{H}" role="img"
     aria-label="{NAME} — machine learning, computational physics, molecular intelligence">
  <title>{NAME} / {TAGLINE}</title>
  <desc>A quiver plot of a turbulent velocity field with streamlines traced through it.</desc>
  <defs><style>{css}</style></defs>

  <rect width="{W}" height="{H}" fill="{t.bg}"/>

  <g stroke-width="1.1" stroke-linecap="round" fill="none">{field_svg}</g>
  <g>{streams_svg}</g>

  <rect x="{PX0}" y="{PY0}" width="{panel_w}" height="{panel_h}"
        fill="{t.panel}" fill-opacity="0.93"/>
  <rect class="edge" x="{PX0}" y="{PY0}" width="{panel_w}" height="{panel_h}"
        fill="none" stroke="{t.panel_edge}" stroke-width="1"/>

  <g font-family="ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace">
    <g class="up u1" font-size="11" letter-spacing="1.6" fill="{t.ink_faint}">
      <text x="{PX0 + 24}" y="{PY0 + 30}">{EYEBROW}</text>
      <text x="{PX1 - 24}" y="{PY0 + 30}" text-anchor="end">{STAMP}</text>
    </g>

    <text class="up u2" x="{(PX0 + PX1) / 2 + 5.5}" y="{PY0 + 104}" text-anchor="middle"
          fill="{t.ink}" font-size="46" font-weight="500"
          letter-spacing="11">{NAME}</text>

    <text class="up u3" x="{(PX0 + PX1) / 2 + 1.7}" y="{PY0 + 140}" text-anchor="middle"
          fill="{t.ink_soft}" font-size="12.5" letter-spacing="3.4">{DISCIPLINES}</text>

    <text class="up u4" x="{(PX0 + PX1) / 2 + 0.8}" y="{PY0 + 170}" text-anchor="middle"
          fill="{t.ink_faint}" font-size="11.5" letter-spacing="1.6">{TAGLINE}</text>
  </g>
</svg>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="assets", help="output directory")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    for theme in (DARK, LIGHT):
        path = os.path.join(args.out, f"banner-{theme.key}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(build(theme))
        print(f"wrote {path}  ({os.path.getsize(path) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
