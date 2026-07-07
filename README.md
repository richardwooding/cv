# Richard Wooding — CV

A single-page, [gloam](https://github.com/richardwooding/gloam)-styled CV / résumé site.

**Live:** https://richardwooding.github.io/cv/

## How it's built

A linked gloam consumer: `gloam.css` / `gloam.js` are vendored into `docs/` and kept
current by a weekly sync workflow. The page adds one new, generic component —
**`gl-timeline`** (career & education history) — in `docs/cv.css`, a candidate to upstream
into gloam proper.

| path | purpose |
| --- | --- |
| `docs/index.html` | the page |
| `docs/gloam.css`, `docs/gloam.js` | vendored gloam — **do not edit**; synced from upstream |
| `docs/cv.css` | CV-specific styles + the `gl-timeline` component |
| `docs/Richard_Wooding_CV.pdf` | the downloadable CV |
| `.github/workflows/pages.yml` | deploy to GitHub Pages on push to `main` |
| `.github/workflows/gloam-sync.yml` | weekly PR when the vendored gloam copy drifts |

MIT.
