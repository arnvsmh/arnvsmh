# Setup

Everything in this repo is the profile that renders at `github.com/arnvsmh`.

```
README.md                      the profile
assets/banner-dark.svg         generated — do not hand-edit
assets/banner-light.svg        generated — do not hand-edit
tools/build_banner.py          the generator (edit this instead)
tools/test_banner.py           26 tests, stdlib only
tools/preview.html             open in a browser to check both variants
.github/workflows/banner.yml   rebuilds + tests on push
.github/workflows/snake.yml    contribution snake → `output` branch
```

## 1. Drop the files in

From the root of your `arnvsmh/arnvsmh` clone:

```bash
git rm -r --cached assets/.gitkeep 2>/dev/null || true
rm -f assets/banner.svg assets/.gitkeep

# copy README.md, SETUP.md, assets/, tools/, .github/ over the existing tree

python3 tools/build_banner.py     # regenerate to be sure
python3 tools/test_banner.py      # 26 tests, should be all green

git add -A
git commit -m "feat: telemetry banner, rebuilt profile, CI"
git push origin main
```

## 2. Make the repo public

This is the one blocker. A profile README **only renders on your profile if
`arnvsmh/arnvsmh` is public** — right now it's private, which is why GitHub is
showing you the "make this a public repository" prompt in the sidebar. Actions
minutes for public repos are also free, which the snake workflow needs.

Settings → General → Danger Zone → Change repository visibility → Public.

## 3. Turn on write permissions for Actions

The snake workflow pushes to an `output` branch, so it needs write access:

Settings → Actions → General → Workflow permissions → **Read and write
permissions** → Save.

Then run it once by hand: Actions → `snake` → Run workflow. After it finishes,
an `output` branch appears with `snake.svg` and `snake-dark.svg`, and the
contribution graph section of the README starts rendering. Until that first run
completes, that image is a broken icon — that's expected, not a bug.

## 4. Fix the two links I guessed

In `README.md` I used `x.com/arnvsmh` and `linkedin.com/in/arnvsmh`. If your
handles differ, correct them — `test_no_placeholder_links` will catch bare
`x.com/` or `linkedin.com/` stubs, but it can't know your real handle.

---

# How the banner works

`tools/build_banner.py` synthesises a lap — five braking zones, five corner
exits, five straights — as two channels, then plots them: speed as a continuous
teal trace, throttle as a binary step band underneath. It's the picture a race
engineer actually looks at, which is the part of the F1 aesthetic that isn't
just "dark background, teal accent."

Three constraints drove every technical decision, and all three are enforced by
tests:

**No external resources.** GitHub serves README images through its camo proxy
into a sandboxed `<img>` tag. Nothing fetched at render time will load — no
webfonts, no remote images. So the typography comes from system stacks
(Helvetica/Arial for the wordmark, the system mono for data labels) plus heavy
tracking and weight contrast. That's also why the wordmark is nudged 9px left:
a trailing letter-space is appended after the final glyph, which drags a centred
string right by half a step.

**No scripts.** Same sandbox. Every animation is CSS keyframes.

**Reduced motion has to work.** Because the animation is CSS rather than SMIL,
`@media (prefers-reduced-motion: reduce)` can switch it all off. Each animated
element's *base* style is its finished state, with the keyframe supplying the
starting offset — so with motion disabled you get the completed frame, not a
blank one. `test_animation_base_state_is_the_finished_frame` locks this in.

## Editing it

Content lives at the top of `build_banner.py`:

```python
NAME        = "ARNAV SIMHA"
DISCIPLINES = "MACHINE LEARNING  ·  COMPUTATIONAL PHYSICS  ·  ..."
TAGLINE     = "research → simulation → discovery"
HANDLE      = "@arnvsmh"
STATUS      = "TELEMETRY · LIVE"
```

Colour lives in the two `Theme` blocks. `DARK.accent` is `#00D2BE` — the
Petronas teal. Everything else keys off it.

The lap itself is the `LAP` list: `(length, kind)` pairs where kind is
`straight`, `brake`, `corner`, or `exit`. Reorder it and you get a different
circuit. The trace is deterministic, so the SVG is byte-stable across rebuilds
and diffs stay readable.

Then:

```bash
python3 tools/build_banner.py
python3 tools/test_banner.py
open tools/preview.html          # both variants, plus a mobile-width toggle
```

## Why two SVG files

An SVG loaded as an image can't see GitHub's theme setting, so it can't restyle
itself. The `<picture>` element resolves `prefers-color-scheme` on GitHub's side
and hands the browser the right file. Gradient and mask ids are namespaced per
variant (`bg-dark` / `bg-light`) so the two can never collide —
`test_variant_ids_are_namespaced` enforces it.

## A note on the stats cards

`github-readme-stats` runs on a shared Vercel instance that gets rate-limited
hard. If the cards start showing an error box, deploy your own instance (the
project's README has a one-click Vercel button) and swap the hostname in
`README.md`. Nothing else changes.

## Known-good failure modes

| Symptom | Cause |
|---|---|
| Banner is a broken image icon | Repo is still private, or the path is wrong. Relative paths resolve from the repo root. |
| Banner renders but doesn't animate | You're looking at it in a context that strips animation, or reduced motion is on at the OS level. Both are intended fallbacks. |
| Snake section is broken | The `snake` workflow hasn't run successfully yet, or Actions lacks write permission. |
| Stats cards show an error | Upstream rate limit. Self-host. |
| CI fails on "assets are stale" | You edited `assets/*.svg` directly. Edit the generator and rebuild. |
