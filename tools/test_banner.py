#!/usr/bin/env python3
"""
test_banner.py — guards the properties that make the banner actually work
once GitHub proxies it through camo and drops it into an <img> tag.

Run:  python3 tools/test_banner.py         (from the repo root)
      python3 -m unittest discover tools   (equivalent)

No third-party dependencies. Standard library only, so CI is instant.
"""

from __future__ import annotations

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

# Rough per-character advance as a fraction of font-size. Deliberately
# generous — the point is to catch text that would overflow the viewBox on
# a wide-metric fallback font, not to typeset precisely.
ADVANCE_SANS_BOLD = 0.76
ADVANCE_SANS = 0.60
ADVANCE_MONO = 0.62


def read(variant: str) -> str:
    with open(os.path.join(ASSETS, f"banner-{variant}.svg"), encoding="utf-8") as fh:
        return fh.read()


class TestChannels(unittest.TestCase):
    """The synthesised lap data itself."""

    def test_channels_are_normalised(self):
        speed, throttle = bb.lap_channels()
        for name, chan in (("speed", speed), ("throttle", throttle)):
            with self.subTest(channel=name):
                self.assertEqual(len(chan), bb.SAMPLES)
                self.assertTrue(all(0.0 <= v <= 1.0 for v in chan))
                self.assertGreater(max(chan) - min(chan), 0.5,
                                   "channel is too flat to read as telemetry")

    def test_channels_are_deterministic(self):
        self.assertEqual(bb.lap_channels(), bb.lap_channels())

    def test_speed_looks_like_a_lap(self):
        """Braking zones must actually appear — otherwise it's just noise."""
        speed, _ = bb.lap_channels()
        drops = sum(
            1 for i in range(1, len(speed))
            if speed[i - 1] - speed[i] > 0.05
        )
        self.assertGreaterEqual(drops, 5, "expected several braking events")

    def test_path_data_is_finite(self):
        speed, _ = bb.lap_channels()
        d = bb.to_path(speed, 0, 100, 0, 50)
        self.assertNotIn("nan", d.lower())
        self.assertNotIn("inf", d.lower())
        self.assertTrue(d.startswith("M "))

    def test_step_path_is_orthogonal(self):
        """A step trace must move in axis-aligned segments only."""
        d = bb.to_path([0.0, 1.0, 0.0, 1.0], 0, 30, 0, 10, step=True)
        nums = [float(n) for n in d.replace("M", " ").replace("L", " ").split()]
        pts = list(zip(nums[0::2], nums[1::2]))
        for a, b in zip(pts, pts[1:]):
            moved_x = abs(a[0] - b[0]) > 1e-6
            moved_y = abs(a[1] - b[1]) > 1e-6
            self.assertFalse(moved_x and moved_y,
                             f"diagonal segment {a} -> {b} in a step path")


class TestGeneratedSVGs(unittest.TestCase):
    """Every property below is a thing that has broken someone's README."""

    def test_files_exist(self):
        for v in VARIANTS:
            self.assertTrue(os.path.isfile(os.path.join(ASSETS, f"banner-{v}.svg")),
                            f"assets/banner-{v}.svg missing — run tools/build_banner.py")

    def test_is_wellformed_xml(self):
        for v in VARIANTS:
            with self.subTest(variant=v):
                root = ET.fromstring(read(v))
                self.assertEqual(root.tag, f"{{{SVG_NS}}}svg")

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
        url_pattern = re.compile(r"https?://[^\"'\s)]+")
        allowed = {SVG_NS, "http://www.w3.org/1999/xlink"}
        for v in VARIANTS:
            with self.subTest(variant=v):
                found = set(url_pattern.findall(read(v))) - allowed
                self.assertEqual(found, set(), f"external references: {found}")
                self.assertNotIn("@import", read(v))

    def test_all_references_resolve(self):
        """Every url(#x) and clip-path/mask points at an id defined in the file."""
        for v in VARIANTS:
            svg = read(v)
            ids = set(re.findall(r'\sid="([^"]+)"', svg))
            refs = set(re.findall(r"url\(#([^)]+)\)", svg))
            with self.subTest(variant=v):
                self.assertTrue(refs, "expected gradient/mask references")
                self.assertEqual(refs - ids, set(),
                                 f"dangling references: {refs - ids}")

    def test_variant_ids_are_namespaced(self):
        """Both files can coexist in one document without id collisions."""
        dark_ids = set(re.findall(r'\sid="([^"]+)"', read("dark")))
        light_ids = set(re.findall(r'\sid="([^"]+)"', read("light")))
        self.assertEqual(dark_ids & light_ids, set(),
                         "dark and light share ids; one would shadow the other")

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
                for needle in (bb.NAME, bb.TAGLINE, bb.HANDLE, bb.STATUS):
                    self.assertIn(needle, svg)

    def test_is_accessible(self):
        for v in VARIANTS:
            root = ET.fromstring(read(v))
            with self.subTest(variant=v):
                self.assertEqual(root.get("role"), "img")
                self.assertTrue(root.get("aria-label"))
                self.assertIsNotNone(root.find(f"{{{SVG_NS}}}title"))

    def test_respects_reduced_motion(self):
        for v in VARIANTS:
            with self.subTest(variant=v):
                self.assertIn("prefers-reduced-motion", read(v))

    def test_animation_base_state_is_the_finished_frame(self):
        """
        With animations disabled the traces must still be fully drawn, so the
        base rule needs stroke-dashoffset:0 and the keyframe supplies the
        offset — not the other way round.
        """
        for v in VARIANTS:
            svg = read(v)
            with self.subTest(variant=v):
                self.assertRegex(svg, r"\.trace-speed\s*\{[^}]*stroke-dashoffset:\s*0")
                self.assertRegex(svg, r"\.trace-throttle\s*\{[^}]*stroke-dashoffset:\s*0")

    def test_themes_actually_differ(self):
        self.assertNotEqual(read("dark"), read("light"))
        self.assertIn(bb.DARK.bg_top, read("dark"))
        self.assertIn(bb.LIGHT.bg_top, read("light"))
        self.assertNotIn(bb.DARK.bg_top, read("light"))

    def test_text_fits_inside_the_viewbox(self):
        """Guards against a fallback font pushing the wordmark off the edge."""
        checks = [
            (bb.NAME, 68, 18, ADVANCE_SANS_BOLD),
            (bb.DISCIPLINES, 13, 4.2, ADVANCE_SANS),
            (bb.TAGLINE, 12.5, 2.0, ADVANCE_MONO),
        ]
        for text, size, track, advance in checks:
            width = len(text) * (size * advance + track)
            with self.subTest(text=text[:24]):
                self.assertLess(width, bb.W - 64,
                                f"{text[:24]!r} is ~{width:.0f}px wide; "
                                f"it would crowd the {bb.W}px frame")

    def test_plot_stays_inside_the_frame(self):
        self.assertGreater(bb.PLOT["x0"], 0)
        self.assertLess(bb.PLOT["x1"], bb.W)
        self.assertLess(bb.THROTTLE_BAND["y1"], bb.H)
        self.assertGreater(bb.PLOT["y0"], 0)
        self.assertLess(bb.PLOT["y1"], bb.THROTTLE_BAND["y0"],
                        "speed panel overlaps the throttle band")

    def test_plot_is_horizontally_centred(self):
        left = bb.PLOT["x0"]
        right = bb.W - bb.PLOT["x1"]
        self.assertAlmostEqual(left, right, delta=1.0)

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
    """The README has to reference the assets the builder actually emits."""

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

    def test_no_placeholder_links(self):
        bad = re.findall(r'href="(https://x\.com/?|https://www\.linkedin\.com/?)"',
                         self.readme)
        self.assertEqual(bad, [], f"placeholder links left in README: {bad}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
