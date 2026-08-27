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
| `docs/Richard_Wooding_CV.pdf` | the downloadable CV — **generated**, don't hand-edit |
| `docs/build-pdf.py` | rebuilds the PDF from `index.html` |
| `docs/print.css` | print/ATS layout used only by the PDF build |
| `.github/workflows/pages.yml` | deploy to GitHub Pages on push to `main` |
| `.github/workflows/gloam-sync.yml` | weekly PR when the vendored gloam copy drifts |

## Rebuilding the PDF

`docs/index.html` is the single source of truth for CV content. The PDF is
generated from it, so edit the page and then run:

```sh
docs/build-pdf.py          # --chrome PATH if Chrome isn't at the macOS default
```

The script reads the content back out of `index.html`, re-lays it out in a plain
ATS-friendly format (`print.css`), and prints it to PDF with headless Chrome.
It asserts on every section it expects, so a markup change that breaks
extraction fails the build instead of quietly dropping a section.

MIT.
