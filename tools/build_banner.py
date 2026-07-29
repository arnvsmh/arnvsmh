#!/usr/bin/env python3
"""
build_banner.py — generates the animated telemetry banner for the arnvsmh
GitHub profile README.

Design brief: Mercedes-AMG F1 pit-wall telemetry. Carbon black, Petronas
teal, brushed silver. The signature element is a real lap trace (speed +
throttle channels) plotted under the wordmark, with a scanning readout
cursor — the same picture an engineer stares at on a Saturday.

Hard constraints (these are what make it actually work on GitHub):
  * No <script>, no <foreignObject>, no external URLs. GitHub serves
    README images through the camo proxy inside an <img> tag, which is a
    sandboxed, non-scripting context. Anything fetched at render time
    silently fails.
  * No webfonts for the same reason — the type personality has to come
    from system stacks + tracking + weight contrast.
  * Animation is CSS-only (not SMIL) so that
    @media (prefers-reduced-motion: reduce) can switch it off. Every
    animated element's *base* style is its final resting state, so the
    reduced-motion render is the finished frame, not a blank one.

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
DISCIPLINES = "MACHINE LEARNING  ·  COMPUTATIONAL PHYSICS  ·  MOLECULAR INTELLIGENCE  ·  CFD"
TAGLINE = "research \u2192 simulation \u2192 discovery"
HANDLE = "@arnvsmh"
STATUS = "TELEMETRY \u00b7 LIVE"

W, H = 1200, 340

# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Theme:
    key: str
    bg_top: str
    bg_bottom: str
    ink: str          # wordmark
    ink_soft: str     # subtitle
    ink_faint: str    # hairlines, grid
    accent: str       # petronas teal
    accent_hi: str    # brighter teal for the highlight pass
    shine: str        # sweep highlight over the wordmark
    trace_2: str      # secondary channel (throttle)


DARK = Theme(
    key="dark",
    bg_top="#0A0E10",
    bg_bottom="#05080A",
    ink="#E9EDEE",
    ink_soft="#9AA4A8",
    ink_faint="#20282B",
    accent="#00D2BE",
    accent_hi="#5CF5E2",
    shine="#FFFFFF",
    trace_2="#828C90",
)

LIGHT = Theme(
    key="light",
    bg_top="#F7F8F8",
    bg_bottom="#EDEFEF",
    ink="#0B0F10",
    ink_soft="#4E585C",
    ink_faint="#CFD5D6",
    accent="#009D8C",
    accent_hi="#00C6B1",
    shine="#00D2BE",
    trace_2="#8C9599",
)

# ---------------------------------------------------------------------------
# Telemetry channel synthesis
# ---------------------------------------------------------------------------

# A lap, described as segments: (length_units, kind).
#   'straight'  full throttle, speed climbs toward v_max
#   'brake'     speed collapses
#   'corner'    speed held low, partial throttle
#   'exit'      speed climbs off the apex
LAP = [
    (7, "straight"), (2, "brake"), (3, "corner"), (4, "exit"),
    (5, "straight"), (2, "brake"), (2, "corner"), (3, "exit"),
    (9, "straight"), (3, "brake"), (4, "corner"), (5, "exit"),
    (4, "straight"), (2, "brake"), (3, "corner"), (6, "exit"),
    (8, "straight"), (2, "brake"), (2, "corner"), (4, "exit"),
]

SAMPLES = 320


def lap_channels(n: int = SAMPLES) -> tuple[list[float], list[float]]:
    """Return (speed, throttle) each normalised 0..1, sampled n times."""
    total = sum(seg for seg, _ in LAP)
    speed: list[float] = []
    throttle: list[float] = []

    v = 0.55
    for i in range(n):
        # locate the segment this sample falls in
        pos = (i / n) * total
        acc = 0.0
        kind = "straight"
        local = 0.0
        seg_len = 1.0
        for seg, k in LAP:
            if pos < acc + seg:
                kind, local, seg_len = k, pos - acc, float(seg)
                break
            acc += seg
        t = local / seg_len

        if kind == "straight":
            target, thr = 0.93 + 0.05 * math.sin(t * math.pi), 1.0
            v += (target - v) * 0.22
        elif kind == "brake":
            target, thr = 0.20, 0.0
            v += (target - v) * 0.45
        elif kind == "corner":
            target = 0.24 + 0.06 * math.sin(t * math.pi)
            thr = 0.18 + 0.25 * t
            v += (target - v) * 0.30
        else:  # exit
            target, thr = 0.55 + 0.42 * t, min(1.0, 0.45 + 1.2 * t)
            v += (target - v) * 0.26

        # engine/sensor jitter — deterministic, no RNG dependency
        v_j = v + 0.008 * math.sin(i * 1.9) + 0.005 * math.sin(i * 0.43)
        speed.append(max(0.0, min(1.0, v_j)))
        throttle.append(max(0.0, min(1.0, thr)))

    return speed, throttle


def to_path(values: list[float], x0: float, x1: float, y0: float, y1: float,
            step: bool = False) -> str:
    """Map a normalised channel onto a plot box and return SVG path data."""
    n = len(values)
    pts = []
    for i, val in enumerate(values):
        x = x0 + (x1 - x0) * (i / (n - 1))
        y = y1 - (y1 - y0) * val
        pts.append((x, y))

    d = [f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"]
    if step:
        prev_y = pts[0][1]
        for x, y in pts[1:]:
            if abs(y - prev_y) > 0.01:
                d.append(f"L {x:.2f} {prev_y:.2f}")
            d.append(f"L {x:.2f} {y:.2f}")
            prev_y = y
    else:
        for x, y in pts[1:]:
            d.append(f"L {x:.2f} {y:.2f}")
    return " ".join(d)


def path_length(d: str) -> float:
    """Rough polyline length — enough to seed stroke-dasharray."""
    nums = d.replace("M", " ").replace("L", " ").split()
    coords = [(float(nums[i]), float(nums[i + 1])) for i in range(0, len(nums) - 1, 2)]
    return sum(
        math.dist(coords[i], coords[i + 1]) for i in range(len(coords) - 1)
    )


# ---------------------------------------------------------------------------
# SVG assembly
# ---------------------------------------------------------------------------

# Two stacked panels, the way a real telemetry overlay is stacked:
# speed on top with room to breathe, throttle as a thin binary band below.
PLOT = dict(x0=152.0, x1=W - 152.0, y0=254.0, y1=300.0)
THROTTLE_BAND = dict(y0=308.0, y1=320.0)
LABEL_X = 140.0


def build(theme: Theme) -> str:
    t = theme
    speed, throttle = lap_channels()

    d_speed = to_path(speed, PLOT["x0"], PLOT["x1"], PLOT["y0"], PLOT["y1"])
    d_throttle = to_path(throttle, PLOT["x0"], PLOT["x1"],
                         THROTTLE_BAND["y0"], THROTTLE_BAND["y1"], step=True)
    len_speed = path_length(d_speed)
    len_throttle = path_length(d_throttle)

    # plot grid: vertical hairlines every 8 samples' worth of width
    grid = []
    cols = 24
    for i in range(cols + 1):
        x = PLOT["x0"] + (PLOT["x1"] - PLOT["x0"]) * i / cols
        grid.append(
            f'<line x1="{x:.1f}" y1="{PLOT["y0"] - 10:.0f}" '
            f'x2="{x:.1f}" y2="{THROTTLE_BAND["y1"] + 8:.0f}" '
            f'stroke="{t.ink_faint}" stroke-width="1" opacity="{0.9 if i % 6 == 0 else 0.45}"/>'
        )
    grid_svg = "\n      ".join(grid)

    # ambient flow lines behind the wordmark
    flow = []
    for i, (y, dash, dur, op) in enumerate([
        (62, "160 900", "17s", 0.55),
        (80, "90 520", "23s", 0.30),
        (98, "240 760", "19s", 0.42),
    ]):
        flow.append(
            f'<line class="flow f{i}" x1="0" y1="{y}" x2="{W}" y2="{y}" '
            f'stroke="{t.accent}" stroke-width="1" stroke-dasharray="{dash}" '
            f'opacity="{op}" style="animation-duration:{dur}"/>'
        )
    flow_svg = "\n      ".join(flow)

    css = f"""
    .flow {{ animation: flow linear infinite; }}
    @keyframes flow {{ from {{ stroke-dashoffset: 1100; }} to {{ stroke-dashoffset: 0; }} }}

    .trace-speed {{
      stroke-dasharray: {len_speed:.0f};
      stroke-dashoffset: 0;
      animation: draw 2.6s cubic-bezier(.22,.61,.36,1) .35s backwards;
    }}
    .trace-throttle {{
      stroke-dasharray: {len_throttle:.0f};
      stroke-dashoffset: 0;
      animation: draw 2.6s cubic-bezier(.22,.61,.36,1) .5s backwards;
    }}
    @keyframes draw {{ from {{ stroke-dashoffset: {max(len_speed, len_throttle):.0f}; }} }}

    .scan {{ animation: scan 7s cubic-bezier(.45,0,.55,1) 2.4s infinite; }}
    @keyframes scan {{
      0%   {{ transform: translateX(0);   opacity: 0; }}
      6%   {{ opacity: 1; }}
      92%  {{ opacity: 1; }}
      100% {{ transform: translateX({PLOT['x1'] - PLOT['x0']:.0f}px); opacity: 0; }}
    }}

    .pulse {{ animation: pulse 2.4s ease-in-out infinite; transform-origin: center; }}
    @keyframes pulse {{
      0%, 100% {{ opacity: .25; }}
      50%      {{ opacity: 1; }}
    }}

    .rule {{ transform-origin: {W/2}px 0; animation: rule 1.4s cubic-bezier(.16,1,.3,1) .25s backwards; }}
    @keyframes rule {{ from {{ transform: scaleX(0); }} }}

    .rise {{ animation: rise .9s cubic-bezier(.16,1,.3,1) backwards; }}
    .d1 {{ animation-delay: .05s; }}
    .d2 {{ animation-delay: .18s; }}
    .d3 {{ animation-delay: .30s; }}
    .d4 {{ animation-delay: .42s; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} }}

    .sweep {{ animation: sweep 9s ease-in-out 1.6s infinite; }}
    @keyframes sweep {{
      0%, 62%  {{ transform: translateX(-{W}px); }}
      100%     {{ transform: translateX({W}px); }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      .flow, .trace-speed, .trace-throttle, .scan,
      .pulse, .rule, .rise, .sweep {{ animation: none; }}
      .scan {{ opacity: 0; }}
      .sweep {{ opacity: 0; }}
    }}
    """

    # A trailing letter-space is appended after the final glyph, which drags
    # a centred string right by half a step. Pull it back.
    name_size, name_track = 68, 18
    name_dx = -name_track / 2

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"
     width="{W}" height="{H}" role="img"
     aria-label="{NAME} — machine learning, computational physics, molecular intelligence, CFD">
  <title>{NAME} · {TAGLINE}</title>

  <defs>
    <linearGradient id="bg-{t.key}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{t.bg_top}"/>
      <stop offset="1" stop-color="{t.bg_bottom}"/>
    </linearGradient>

    <radialGradient id="glow-{t.key}" cx="0.5" cy="0.42" r="0.62">
      <stop offset="0" stop-color="{t.accent}" stop-opacity="0.12"/>
      <stop offset="1" stop-color="{t.accent}" stop-opacity="0"/>
    </radialGradient>

    <linearGradient id="fade-{t.key}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0.00" stop-color="#000"/>
      <stop offset="0.14" stop-color="#fff"/>
      <stop offset="0.86" stop-color="#fff"/>
      <stop offset="1.00" stop-color="#000"/>
    </linearGradient>
    <mask id="edge-{t.key}">
      <rect width="{W}" height="{H}" fill="url(#fade-{t.key})"/>
    </mask>

    <linearGradient id="shine-{t.key}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0.35" stop-color="{t.shine}" stop-opacity="0"/>
      <stop offset="0.50" stop-color="{t.shine}" stop-opacity="0.85"/>
      <stop offset="0.65" stop-color="{t.shine}" stop-opacity="0"/>
    </linearGradient>

    <linearGradient id="trace-{t.key}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{t.accent}"/>
      <stop offset="0.55" stop-color="{t.accent_hi}"/>
      <stop offset="1" stop-color="{t.accent}"/>
    </linearGradient>

    <linearGradient id="bar-{t.key}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{t.accent}" stop-opacity="0"/>
      <stop offset="0.5" stop-color="{t.accent}"/>
      <stop offset="1" stop-color="{t.accent}" stop-opacity="0"/>
    </linearGradient>

    <clipPath id="name-clip-{t.key}">
      <text x="{W/2 + name_dx}" y="152" text-anchor="middle"
            font-family="'Helvetica Neue', Helvetica, Arial, sans-serif"
            font-size="{name_size}" font-weight="700"
            letter-spacing="{name_track}">{NAME}</text>
    </clipPath>

    <style>{css}</style>
  </defs>

  <rect width="{W}" height="{H}" fill="url(#bg-{t.key})"/>
  <rect width="{W}" height="{H}" fill="url(#glow-{t.key})"/>

  <!-- ambient data flow -->
  <g mask="url(#edge-{t.key})" opacity="0.5">
      {flow_svg}
  </g>

  <!-- top hairline + HUD -->
  <rect x="0" y="0" width="{W}" height="2" fill="{t.accent}" opacity="0.9"/>
  <g class="rise d1" font-family="ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
     font-size="11" letter-spacing="2.4">
    <circle class="pulse" cx="96" cy="44" r="3.5" fill="{t.accent}"/>
    <text x="110" y="48" fill="{t.ink_soft}">{STATUS}</text>
    <text x="{W - 96}" y="48" fill="{t.ink_soft}" text-anchor="end">{HANDLE}</text>
  </g>

  <!-- wordmark -->
  <g class="rise d2">
    <text x="{W/2 + name_dx}" y="152" text-anchor="middle" fill="{t.ink}"
          font-family="'Helvetica Neue', Helvetica, Arial, sans-serif"
          font-size="{name_size}" font-weight="700"
          letter-spacing="{name_track}">{NAME}</text>
  </g>
  <g clip-path="url(#name-clip-{t.key})">
    <rect class="sweep" x="-{W}" y="90" width="{W}" height="80" fill="url(#shine-{t.key})"/>
  </g>

  <!-- rule -->
  <rect class="rule" x="{W/2 - 210}" y="177" width="420" height="1" fill="{t.ink_faint}"/>
  <rect class="rule" x="{W/2 - 30}" y="176.5" width="60" height="2" fill="{t.accent}"/>

  <!-- disciplines -->
  <text class="rise d3" x="{W/2}" y="206" text-anchor="middle" fill="{t.ink_soft}"
        font-family="'Helvetica Neue', Helvetica, Arial, sans-serif"
        font-size="13" font-weight="500" letter-spacing="4.2">{DISCIPLINES}</text>

  <text class="rise d3" x="{W/2}" y="234" text-anchor="middle" fill="{t.accent}"
        font-family="ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
        font-size="12.5" letter-spacing="2">{TAGLINE}</text>

  <!-- telemetry plot -->
  <g class="rise d4">
    <g mask="url(#edge-{t.key})" opacity="0.85">
      {grid_svg}
    </g>

    <g font-family="ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, monospace"
       font-size="9.5" letter-spacing="1.6" fill="{t.ink_soft}" text-anchor="end">
      <text x="{LABEL_X}" y="{(PLOT['y0'] + PLOT['y1']) / 2 + 3.5:.0f}" opacity="0.8">SPD</text>
      <text x="{LABEL_X}" y="{(THROTTLE_BAND['y0'] + THROTTLE_BAND['y1']) / 2 + 3.5:.0f}"
            opacity="0.5">THR</text>
    </g>

    <path class="trace-throttle" d="{d_throttle}" fill="none" stroke="{t.trace_2}"
          stroke-width="1.2" stroke-opacity="0.6" stroke-linejoin="miter"/>
    <path class="trace-speed" d="{d_speed}" fill="none" stroke="url(#trace-{t.key})"
          stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>

    <g class="scan" transform="translate(0,0)">
      <line x1="{PLOT['x0']}" y1="{PLOT['y0'] - 10:.0f}"
            x2="{PLOT['x0']}" y2="{THROTTLE_BAND['y1'] + 8:.0f}"
            stroke="{t.accent_hi}" stroke-width="1" opacity="0.55"/>
      <circle cx="{PLOT['x0']}" cy="{PLOT['y0'] - 14:.0f}" r="2.5" fill="{t.accent_hi}"/>
    </g>
  </g>

  <!-- bottom accent -->
  <rect x="0" y="{H - 2}" width="{W}" height="2" fill="url(#bar-{t.key})" opacity="0.8"/>
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
