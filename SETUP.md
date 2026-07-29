# Setup

```
README.md                      the profile
assets/banner-dark.svg         generated — do not hand-edit
assets/banner-light.svg        generated — do not hand-edit
tools/build_banner.py          the generator (edit this instead)
tools/test_banner.py           30 tests, stdlib only
tools/preview.html             open in a browser to check both variants
.github/workflows/banner.yml   rebuilds + tests on push
```

## Applying this over what you already pushed

From your `~/arnvsmh` clone, after copying this tree in:

```bash
cd ~/arnvsmh
git rm -q .github/workflows/snake.yml
python3 tools/build_banner.py
python3 tools/test_banner.py
git add -A
git commit -m "redesign: velocity field banner, work cards, drop generic widgets"
git push origin main
```

The `output` branch the snake created is now orphaned. Delete it:

```bash
git push origin --delete output
```

Nothing else changes — the repo is already public and Actions already has
write permission.

## Fix the three links

`README.md` uses `x.com/arnvsmh`, `linkedin.com/in/arnvsmh`, and
`arnav@ryniant.com`. Correct any that are wrong. `test_no_placeholder_links`
catches bare stubs but can't know your real handles.

---

# What changed, and why

Four things make a profile read as generated no matter how good the rest is:
shields.io badges, github-readme-stats cards, the contribution snake, and a
bulleted "focus" list. All four are gone, and `test_no_generic_profile_widgets`
fails the build if any of them come back.

What replaced them: work cards that carry a specific claim each — the result,
the venue, the mechanism — rather than a category label. A card that says what
a system does and what it found is the thing a badge row can't fake.

# How the banner works

`tools/build_banner.py` computes a two-dimensional velocity field — fourteen
Lamb-Oseen vortices superposed on a gentle mean flow — and draws it as a
quiver plot. Segment angle is the local velocity direction; segment length and
tone track local speed. The teal streamlines are RK2 integrations through that
same field, so the arrows and the lines can't disagree with each other; a test
checks each streamline step against the local velocity and fails above 0.35
radians of divergence.

The vortex layout wasn't placed by eye. It came out of a search over candidate
layouts scored on two properties, both of which are now tests:

- **Angle isotropy.** If one direction dominates, a quiver plot stops reading
  as a flow field and starts reading as scan lines. Six 30° buckets, none
  allowed to starve below 40% of the fullest.
- **Even coverage.** No row of the canvas may average below 55% of the
  fastest row, or you get a dead band where the field fades out.

Three constraints drove the technical decisions:

**No external resources.** GitHub serves README images through its camo proxy
into a sandboxed `<img>`. Nothing fetched at render time will load — no
webfonts. So the type is a system mono stack, and its personality comes from
tracking and scale rather than a typeface choice. That's also why the centred
strings are nudged a few pixels left: a trailing letter-space is appended after
the final glyph, dragging a centred string right by half a step.

**No scripts.** Same sandbox. Every animation is CSS keyframes.

**Reduced motion has to work.** Because the animation is CSS rather than SMIL,
`@media (prefers-reduced-motion: reduce)` can switch it off. Each animated
element's *base* style is its finished state, with the keyframe supplying the
starting offset — so with motion disabled you get the completed frame, not a
blank one.

## Editing it

Content is at the top of `build_banner.py`:

```python
NAME        = "ARNAV SIMHA"
DISCIPLINES = "MACHINE LEARNING / COMPUTATIONAL PHYSICS / MOLECULAR INTELLIGENCE"
TAGLINE     = "research -> simulation -> discovery"
EYEBROW     = "// FLOW RECONSTRUCTED"
STAMP       = "RE_TAU 550 / DNS"
```

Colour is in the two `Theme` blocks. `field` is a four-stop ramp from slowest
to fastest; `accent` is the streamline colour.

The field is `VORTICES` — `(x, y, circulation, core_radius)`. Signs alternate,
and several sit off-canvas so structure runs past the edges instead of
stopping at them. Change them and re-run the tests; if you break isotropy or
coverage, the suite tells you which.

```bash
python3 tools/build_banner.py
python3 tools/test_banner.py
open tools/preview.html
```

## Why two SVG files

An SVG loaded as an image can't see GitHub's theme setting, so it can't
restyle itself. `<picture>` resolves `prefers-color-scheme` on GitHub's side
and hands the browser the right file.

## Known-good failure modes

| Symptom | Cause |
|---|---|
| Banner is a broken image icon | Path is wrong, or `assets/` didn't copy. `ls assets/` should show two SVGs. |
| Banner renders but doesn't animate | Reduced motion is on at the OS level. That's the intended fallback. |
| Field looks striped | You changed `SHEAR` or `VORTICES`. Run the tests — `test_angles_are_isotropic` is exactly this failure. |
| CI fails on "assets are stale" | You edited `assets/*.svg` directly. Edit the generator and rebuild. |
