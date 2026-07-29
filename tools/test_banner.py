#!/usr/bin/env python3
"""
test_banner.py — guards two things.

First, the properties that make the SVG work once GitHub proxies it through
camo into a sandboxed <img>: no external fetches, no scripting, resolvable
references, reduced-motion support.

Second, the properties that make the field look computed rather than drawn:
angle isotropy (no direction dominates, so it never reads as scan lines),
even coverage across the canvas, and streamlines that actually follow the
velocity field the quiver plot is showing.

And a third, smaller thing: the README stays free of the four generic
profile tells — shields badges, stats cards, a contribution snake, and
placeholder links.

Run:  python3 tools/test_banner.py
"""

from __future__ import annotations

import collections
import math
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_banner as bb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
VARIANTS = ("dark", "light")
SVG_NS = "http://www.w3.org/2000/svg"

# Mono advance is ~0.60em across every stack in the font list.
ADVANCE_MONO = 0.60


def read(variant: str) -> str:
    with open(os.path.join(ASSETS, f"banner-{variant}.svg"), encoding="utf-8") as fh:
        return fh.read()


def sample_field(step: int = 24):
    """Yield (x, y, u, v) over the same lattice the quiver plot uses."""
    y = step / 2
    while y < bb.H:
        x = step / 2
        while x < bb.W:
            u, v = bb.velocity(x, y)
            yield x, y, u, v
            x += step
        y += step


class TestField(unittest.TestCase):
    """The velocity field itself, before any of it becomes SVG."""

    def test_angles_are_isotropic(self):
        """
        If one direction dominates, the quiver plot reads as scan lines
        instead of a flow field. Six 30-degree buckets, none starved.
        """
        hist = collections.Counter(
            int(math.degrees(math.atan2(v, u)) % 180 // 30)
            for _, _, u, v in sample_field()
        )
        self.assertEqual(len(hist), 6, "some orientations are entirely absent")
        ratio = min(hist.values()) / max(hist.values())
        self.assertGreater(ratio, 0.40,
                           f"angle distribution is lopsided (ratio {ratio:.2f})")

    def test_coverage_is_even_top_to_bottom(self):
        """No dead band — every row has to carry visible speed."""
        rows = collections.defaultdict(list)
        for _, y, u, v in sample_field():
            rows[round(y)].append(math.hypot(u, v))
        means = {k: sum(s) / len(s) for k, s in rows.items()}
        ratio = min(means.values()) / max(means.values())
        self.assertGreater(ratio, 0.55,
                           f"row {min(means, key=means.get)} is nearly empty "
                           f"(ratio {ratio:.2f})")

    def test_field_is_finite_everywhere(self):
        """Vortex cores are the obvious place for a divide-by-zero."""
        for vx, vy, _, _ in bb.VORTICES:
            u, v = bb.velocity(vx, vy)
            self.assertTrue(math.isfinite(u) and math.isfinite(v),
                            f"non-finite velocity at vortex core ({vx}, {vy})")
        for x, y, u, v in sample_field(60):
            self.assertTrue(math.isfinite(u) and math.isfinite(v))
            self.assertLess(math.hypot(u, v), 1e4, f"runaway speed at ({x}, {y})")

    def test_field_is_deterministic(self):
        self.assertEqual(bb.velocity(371.0, 208.0), bb.velocity(371.0, 208.0))

    def test_streamlines_follow_the_field(self):
        """
        The arrows and the lines have to agree. Each streamline step should
        point along the local velocity — check the angle between them.
        """
        pts = bb.streamline(-20.0, 264.0, 60, 6.0)
        self.assertGreater(len(pts), 30, "streamline died immediately")
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            u, v = bb.velocity((x0 + x1) / 2, (y0 + y1) / 2)
            step_ang = math.atan2(y1 - y0, x1 - x0)
            flow_ang = math.atan2(v, u)
            delta = abs((step_ang - flow_ang + math.pi) % (2 * math.pi) - math.pi)
            self.assertLess(delta, 0.35,
                            f"streamline diverges from the field at ({x0:.0f}, {y0:.0f})")

    def test_streamlines_stay_near_the_canvas(self):
        for sx, sy in bb.STREAM_SEEDS:
            for x, y in bb.streamline(sx, sy, 260, 6.0):
                self.assertTrue(-60 < x < bb.W + 60 and -60 < y < bb.H + 60)

    def test_quiver_skips_the_panel(self):
        """Segments under the panel are invisible weight in the file."""
        body, count = bb.quiver(bb.DARK)
        self.assertGreater(count, 300, "field is too sparse to read")
        self.assertLess(count, 1200, "field is heavier than it needs to be")
        for mx, my in re.findall(r'd="M(-?[\d.]+) (-?[\d.]+)', body):
            x, y = float(mx), float(my)
            inside = (bb.PX0 < x < bb.PX1) and (bb.PY0 < y < bb.PY1)
            self.assertFalse(inside, f"segment at ({x}, {y}) is hidden by the panel")


class TestSway(unittest.TestCase):
    """
    The field sways. With no scripting available, that means bucketing every
    segment into an amplitude class and a phase class — so the buckets have
    to be populated sensibly or the motion reads as jitter.
    """

    def setUp(self):
        self.body, _ = bb.quiver(bb.DARK)
        self.classes = re.findall(r'class="q(\d) w a(\d) p(\d+)"', self.body)
        self.assertTrue(self.classes, "no segments carry sway classes")

    def test_every_segment_sways(self):
        n_paths = self.body.count("<path")
        self.assertEqual(len(self.classes), n_paths,
                         "some segments are missing amplitude or phase classes")

    def test_phase_buckets_are_evenly_filled(self):
        """
        A traveling wave only reads as one motion if every phase of it is
        represented. A starved bucket shows up as a gap in the crest.
        """
        hist = collections.Counter(int(p) for _, _, p in self.classes)
        self.assertEqual(len(hist), bb.PHASE_BUCKETS, "a phase bucket is empty")
        ratio = min(hist.values()) / max(hist.values())
        self.assertGreater(ratio, 0.5, f"phase distribution is lumpy ({ratio:.2f})")

    def test_every_amplitude_bucket_is_used(self):
        hist = collections.Counter(int(a) for _, a, _ in self.classes)
        self.assertEqual(len(hist), bb.AMP_BUCKETS)
        self.assertGreater(min(hist.values()), 20,
                           "an amplitude bucket is nearly unused")

    def test_amplitude_tracks_vorticity(self):
        """
        Segments sitting in a vortex should sway harder than free-stream
        segments. Compare mean curl in the top bucket against the bottom.
        """
        by_bucket = collections.defaultdict(list)
        coords = re.findall(
            r'class="q\d w a(\d) p\d+" d="M(-?[\d.]+) (-?[\d.]+)l(-?[\d.]+) (-?[\d.]+)',
            self.body)
        for amp, mx, my, dx, dy in coords:
            cx = float(mx) + float(dx) / 2
            cy = float(my) + float(dy) / 2
            by_bucket[int(amp)].append(abs(bb.vorticity(cx, cy)))
        lowest = sum(by_bucket[0]) / len(by_bucket[0])
        highest = sum(by_bucket[bb.AMP_BUCKETS - 1]) / len(by_bucket[bb.AMP_BUCKETS - 1])
        self.assertGreater(highest, lowest * 2,
                           "amplitude isn't tracking local vorticity")

    def test_rotation_pivots_on_the_segment(self):
        """
        Without transform-box:fill-box the rotation origin falls back to the
        viewBox origin and the segments fly across the canvas instead of
        pivoting in place. This is the one CSS feature the sway depends on.
        """
        for v in VARIANTS:
            svg = read(v)
            with self.subTest(variant=v):
                self.assertIn("transform-box:fill-box", svg)
                self.assertIn("transform-origin:center", svg)

    def test_sway_rests_at_the_true_field_angle(self):
        """
        Keyframes run from -A to +A, so the midpoint — the resting state with
        animation disabled — is the actual velocity direction.
        """
        for i, deg in enumerate(bb.AMP_DEGREES):
            svg = read("dark")
            self.assertIn(f"@keyframes k{i}{{from{{transform:rotate({-deg}deg)}}"
                          f"to{{transform:rotate({deg}deg)}}}}", svg)

    def test_sway_amplitudes_stay_subtle(self):
        """Past ~20 degrees it stops reading as flow and starts reading as wind."""
        self.assertEqual(len(bb.AMP_DEGREES), bb.AMP_BUCKETS)
        self.assertLess(max(bb.AMP_DEGREES), 20.0)
        self.assertEqual(list(bb.AMP_DEGREES), sorted(bb.AMP_DEGREES))


class TestGeneratedSVGs(unittest.TestCase):
    """Every property below is a thing that has broken someone's README."""

    def test_files_exist(self):
        for v in VARIANTS:
            self.assertTrue(os.path.isfile(os.path.join(ASSETS, f"banner-{v}.svg")),
                            f"assets/banner-{v}.svg missing — run tools/build_banner.py")

    def test_is_wellformed_xml(self):
        for v in VARIANTS:
            with self.subTest(variant=v):
                self.assertEqual(ET.fromstring(read(v)).tag, f"{{{SVG_NS}}}svg")

    def test_no_scripting_or_foreign_content(self):
        """camo serves the file into a sandboxed <img>: neither ever runs."""
        for v in VARIANTS:
            svg = read(v).lower()
            with self.subTest(variant=v):
                self.assertNotIn("<script", svg)
                self.assertNotIn("<foreignobject", svg)
                self.assertNotIn("onload", svg)
                self.assertNotIn("javascript:", svg)

    def test_no_external_resources(self):
        """No webfont, no remote image — nothing is fetched at render time."""
        allowed = {SVG_NS, "http://www.w3.org/1999/xlink"}
        for v in VARIANTS:
            svg = read(v)
            with self.subTest(variant=v):
                found = set(re.findall(r"https?://[^\"'\s)]+", svg)) - allowed
                self.assertEqual(found, set(), f"external references: {found}")
                self.assertNotIn("@import", svg)

    def test_all_references_resolve(self):
        for v in VARIANTS:
            svg = read(v)
            ids = set(re.findall(r'\sid="([^"]+)"', svg))
            refs = set(re.findall(r"url\(#([^)]+)\)", svg))
            with self.subTest(variant=v):
                self.assertEqual(refs - ids, set(),
                                 f"dangling references: {refs - ids}")

    def test_viewbox_and_intrinsic_size_agree(self):
        for v in VARIANTS:
            root = ET.fromstring(read(v))
            with self.subTest(variant=v):
                self.assertEqual(root.get("viewBox"), f"0 0 {bb.W} {bb.H}")
                self.assertEqual(root.get("width"), str(bb.W))
                self.assertEqual(root.get("height"), str(bb.H))

    def test_content_is_present(self):
        for v in VARIANTS:
            svg = read(v)
            with self.subTest(variant=v):
                for needle in (bb.NAME, bb.TAGLINE, bb.EYEBROW, bb.STAMP):
                    self.assertIn(needle, svg)

    def test_uses_ascii_arrows(self):
        """A Unicode arrow in a mono setting breaks the monospace rhythm."""
        self.assertNotIn("\u2192", bb.TAGLINE)
        self.assertIn("->", bb.TAGLINE)

    def test_is_accessible(self):
        for v in VARIANTS:
            root = ET.fromstring(read(v))
            with self.subTest(variant=v):
                self.assertEqual(root.get("role"), "img")
                self.assertTrue(root.get("aria-label"))
                self.assertIsNotNone(root.find(f"{{{SVG_NS}}}title"))
                self.assertIsNotNone(root.find(f"{{{SVG_NS}}}desc"))

    def test_respects_reduced_motion(self):
        for v in VARIANTS:
            with self.subTest(variant=v):
                self.assertIn("prefers-reduced-motion", read(v))

    def test_animation_base_state_is_the_finished_frame(self):
        """
        With animation disabled the panel edge and streamlines must still be
        drawn — the base rule carries dashoffset 0 and the keyframe supplies
        the starting offset, not the other way round.
        """
        for v in VARIANTS:
            svg = read(v)
            with self.subTest(variant=v):
                self.assertRegex(svg, r"\.sl\{[^}]*stroke-dashoffset:0")
                self.assertIn(".w,.sl,.edge,.up{animation:none}", svg.replace("\n","").replace("      ",""))
                self.assertRegex(svg, r"\.edge\{[^}]*stroke-dashoffset:0")

    def test_themes_actually_differ(self):
        self.assertNotEqual(read("dark"), read("light"))
        self.assertIn(bb.DARK.bg, read("dark"))
        self.assertNotIn(bb.DARK.bg, read("light"))

    def test_field_tones_are_distinguishable_from_background(self):
        """The slowest bucket still has to be visible against the canvas."""
        for theme in (bb.DARK, bb.LIGHT):
            with self.subTest(variant=theme.key):
                bg = int(theme.bg[1:], 16)
                slow = int(theme.field[0][1:], 16)
                delta = sum(
                    abs(((bg >> s) & 255) - ((slow >> s) & 255))
                    for s in (16, 8, 0)
                )
                self.assertGreater(delta, 45,
                                   "slowest field segments vanish into the background")

    def test_text_fits_inside_the_panel(self):
        panel_w = bb.PX1 - bb.PX0
        checks = [
            (bb.NAME, 46, 11),
            (bb.DISCIPLINES, 12.5, 3.4),
            (bb.TAGLINE, 11.5, 1.6),
            (bb.EYEBROW + bb.STAMP, 11, 1.6),
        ]
        for text, size, track in checks:
            width = len(text) * (size * ADVANCE_MONO + track)
            with self.subTest(text=text[:24]):
                self.assertLess(width, panel_w - 48,
                                f"{text[:24]!r} is ~{width:.0f}px wide inside a "
                                f"{panel_w:.0f}px panel")

    def test_panel_sits_inside_the_frame(self):
        self.assertGreater(bb.PX0, 0)
        self.assertLess(bb.PX1, bb.W)
        self.assertGreater(bb.PY0, 0)
        self.assertLess(bb.PY1, bb.H)

    def test_stays_small_enough_to_inline(self):
        for v in VARIANTS:
            size = os.path.getsize(os.path.join(ASSETS, f"banner-{v}.svg"))
            with self.subTest(variant=v):
                self.assertLess(size, 60_000, "banner is getting heavy for a README")

    def test_output_is_reproducible(self):
        """Rebuilding must not churn the file — keeps diffs meaningful."""
        for theme in (bb.DARK, bb.LIGHT):
            with self.subTest(variant=theme.key):
                self.assertEqual(bb.build(theme), read(theme.key),
                                 "assets are stale — re-run tools/build_banner.py")


class TestReadme(unittest.TestCase):
    """The README has to stay free of the generic-profile tells."""

    def setUp(self):
        path = os.path.join(ROOT, "README.md")
        if not os.path.isfile(path):
            self.skipTest("README.md not present")
        with open(path, encoding="utf-8") as fh:
            self.readme = fh.read()

    def test_references_both_banner_variants(self):
        for v in VARIANTS:
            self.assertIn(f"assets/banner-{v}.svg", self.readme)

    def test_uses_picture_for_theme_switching(self):
        self.assertIn("prefers-color-scheme: dark", self.readme)
        self.assertIn("<picture>", self.readme)

    def test_img_has_alt_text(self):
        for tag in re.findall(r"<img[^>]*>", self.readme):
            self.assertIn("alt=", tag, f"missing alt text: {tag[:70]}")

    def test_no_generic_profile_widgets(self):
        """
        Badges, stats cards and the contribution snake are the four things
        that make a profile read as generated regardless of what surrounds
        them. Keeping them out is a design decision, so it gets a test.
        """
        banned = {
            "shields.io": "badge service",
            "github-readme-stats": "stats cards",
            "streak-stats": "streak cards",
            "snake.svg": "contribution snake",
            "capsule-render": "header generator",
            "readme-typing-svg": "typing animation",
        }
        for needle, label in banned.items():
            with self.subTest(widget=label):
                self.assertNotIn(needle, self.readme, f"{label} is back in the README")

    def test_no_emoji_headers(self):
        for line in self.readme.splitlines():
            if line.startswith("#"):
                self.assertTrue(all(ord(c) < 0x2100 for c in line),
                                f"emoji or symbol in heading: {line}")

    def test_no_placeholder_links(self):
        bad = re.findall(
            r'href="(https://x\.com/?|https://www\.linkedin\.com/?|'
            r'https://github\.com/?|mailto:you@)"',
            self.readme)
        self.assertEqual(bad, [], f"placeholder links left in README: {bad}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
