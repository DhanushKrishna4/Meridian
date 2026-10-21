# Meridian Open Graph artwork

The website card is [`web/public/og-v1.png`](../../web/public/og-v1.png):
**1200 × 630**, **89,267 bytes**, opaque 8-bit truecolor RGB PNG (color type 2),
with an embedded sRGB profile. It is rendered ahead of time; visitors and social
crawlers receive a static file. No fonts, scripts, API keys or computation are
needed to display it.

## Regenerate

From the repository root, using Node.js 22.8 or newer:

```sh
npm --prefix tools/og ci && npm --prefix tools/og run render
```

After installing the pinned renderer dependencies once, regeneration is fully
local and takes under a second on the development machine. It requires no
browser, system fonts, Python environment or network. The regular website build
copies the checked-in image; it does not install or run the artwork tools.

- **Editable design:** [`artwork.mjs`](artwork.mjs). Text, geometry, colors,
  sizes and typography are explicit in the `finalArtwork()` function.
- **Portable vector export:** [`meridian-og.svg`](meridian-og.svg). Lettering is
  outlined with semantic `data-text` labels, so the file does not depend on font
  installation. Edit copy in the design source and regenerate the SVG/PNG.
- **Export process:** [`render.mjs`](render.mjs). Fontkit shapes the bundled
  fonts, resvg renders at 2× resolution, and Sharp downsamples using Lanczos3 and
  writes an optimized RGB/sRGB PNG. No animation, clock or randomness is used.
- **Image report:** [`export.json`](export.json), including full SHA-256.
- **Visual proofs:** [`proofs/`](proofs/) contains 600×315, 300×158 and crop views.

Render twice and compare the image hash to check repeatability. This was done
with identical results during development. `export.json` contains no changing
timestamp. All renderer versions are pinned in `package-lock.json`.

If replacing the public artwork in future, use a new filename (`og-v2.png`, etc.)
and update the exporter, verifier and all static metadata references together.

## Design decision and actual visual review

Reviewed on 2026-10-21. The live portfolio HTML and its repository's `index.html`
both referenced [`card-v2.png`](https://dhanushkrishna4.github.io/card-v2.png).
That actual PNG was downloaded and visually inspected. A repository tree check
found the published PNG and metadata, but no dedicated editable card generator.
The benchmark informed confidence of scale, sparse copy and optical finish;
its serif/sans pairing, signature, contour field and red palette were not reused.

Meridian's deployed HTML, latest frontend source, local licensed font files,
and retained redesign screenshots established the current identity: DM Sans,
IBM Plex Mono, navy `#0c141d`, pale text `#dce6ee`, teal `#6ee4cf`, amber
`#e4bc83`, square variables and fine causal arrows. Live browser interaction was
not needed or claimed for this static image/metadata task.

Two materially different 1200×630 studies were exported and visually compared:

1. [`study-a-intervention.png`](studies/study-a-intervention.png): a large
   horizontal wordmark over one enlarged chain intervention. A visible cut
   removes the incoming X-to-Y mechanism while Y continues to affect Z.
2. [`study-b-equivalence.png`](studies/study-b-equivalence.png): an asymmetric
   title/text column beside three stacked equivalent causal explanations and
   their distinct intervention means. Those exact mathematical values come
   from [`examples/exact-fixture.json`](../../examples/exact-fixture.json),
   reproducible with `PYTHONPATH=src .venv/bin/python -m meridian_causal.cli fixture`.
   They are exact fixtures, not fitted experimental measurements. Its graphs
   depict the original models, with intervention targets highlighted.

**The intervention cut was selected.** Its name and central action survive a
small link preview more clearly than three miniature explanatory rows. The
final artwork is a conceptual illustration of intervening on `X → Y → Z`,
not a fitted result or an observational identification claim.

The first polished export was then refined: redundant tiny footers were removed,
the wordmark gained space, variable squares grew to 124 pixels, the cut became
more prominent, the old incoming arrowhead was removed, and its caption became
larger and shorter. The `do(Y = 1)` annotation increased to 32 pixels. The final
PNG was inspected at full size, 600×315 and 300×158; the title, highlighted Y and
broken incoming connection remain legible. Fonts are loaded synchronously from
checked-in files, and missing glyphs abort export rather than silently falling
back. An independent visual review of the studies informed the refinement.

The 16:9 and 5% inset crop proofs retain the central idea. The square stress crop
cuts the beginning of the title and outer nodes; this is a deliberately wide
large-image card, not a claim of universal crop safety.

## Fonts and licenses

The fonts are the site's existing Fontsource 5.3.0 assets. DM Sans uses its
variable weight at 500/450/400; IBM Plex Mono uses regular 400. Exact original
WOFF2s, losslessly decoded TTFs, SIL Open Font License notices and SHA-256
provenance are in [`fonts/`](fonts/). TTF decoding used FontTools 4.66.1 and
Brotli 1.2.0 with `recalcTimestamp=False`, `font.flavor=None`, then `font.save()`;
these tools are not required to regenerate the card from the included fonts.
The site's existing [font notices](../../web/public/licenses/index.html) remain
available in the production output. No portfolio assets are redistributed.

## Metadata and delivery checks

The initial [`web/index.html`](../../web/index.html) contains a canonical link,
complete Open Graph metadata and matching Twitter `summary_large_image` metadata,
including descriptive image alt text. The canonical page is
`https://dhanushkrishna4.github.io/Meridian/` and the image is
`https://dhanushkrishna4.github.io/Meridian/og-v1.png`.
The HTTPS URL and case-sensitive project subpath were verified against GitHub's
Pages API. Tags follow the [Open Graph specification](https://ogp.me/).

Build and verify files:

```sh
npm --prefix web run build
node tools/og/verify.mjs
```

Serve the production build, then verify its actual HTTP responses:

```sh
python3 scripts/serve_production.py --port 4175
# In a second terminal:
node tools/og/verify.mjs --base-url http://127.0.0.1:4175/Meridian/ --report tools/og/verification-local.json
```

The completed local report is [`verification-local.json`](verification-local.json).
It checks image dimensions, 8-bit RGB, opacity, sRGB profile, size, identical
production bytes, unique initial-head metadata, canonical URL, matching social
fields, HTTP 200, `image/png`, the PNG signature and the full image hash. An HTML
fallback at the image URL would fail these checks. TypeScript and the production
build passed; [`build.txt`](build.txt) records their output. Python algorithms
and application behavior were not changed, so this task did not rerun the native
numerical suite locally.

The same verifier can target the public origin:

```sh
node tools/og/verify.mjs --base-url https://dhanushkrishna4.github.io/Meridian/ --report tools/og/verification-live.json
```

**Live verification passed on 2026-10-21.** The
[Pages workflow](https://github.com/DhanushKrishna4/Meridian/actions/runs/39621650040)
successfully built and deployed
[`3aa61a1`](https://github.com/DhanushKrishna4/Meridian/commit/3aa61a1177af58d3c208ef9d1cf67ee2a38b8f6e).
The public page's initial metadata passed the same checks as the local build.
The image returned HTTP 200 and `image/png`, with the exact expected SHA-256
`cb3027b8b46063277f17da512c78b1fbf2f30618c79514e93affeaa266425c58`.
The full response checks are in [`verification-live.json`](verification-live.json).
GitHub resolved the author and committer to `DhanushKrishna4`; the contributors
API listed only that account. No co-author trailer was added.

Website metadata does **not** set GitHub's separate repository social-preview
image. That setting was not changed by this work; the finished PNG is suitable
for a separate repository upload. No LinkedIn, WhatsApp, X or other platform
cache refresh is claimed.
