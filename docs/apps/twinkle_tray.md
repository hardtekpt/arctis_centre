# twinkle_tray

## Purpose

Vendored Twinkle Tray source included under `src/Apps/twinkle_tray` as a reference implementation and/or base for brightness-flyout style and behavior.

Location:

- `src/Apps/twinkle_tray`

## Upstream

- Upstream project: `xanderfrangos/twinkle-tray`
- This module keeps upstream-oriented structure and docs.

## Structure Overview

- `src/`: Electron app code, React components, native modules, styles, assets, localization
- `resources/`: installer and appx resources
- `package.json`: build and packaging scripts

## Notes for This Repository

- The module is large and mostly independent from the Arctis API workflow.
- It serves as a style/UX and packaging reference for tray-based desktop experiences.
- For module-specific usage and packaging details, refer to:
  - `src/Apps/twinkle_tray/README.md`

## Legacy Style-Guide Content Consolidation

Legacy local style-guide notes were merged into:

- `docs/apps/arctis-centre-app.md` (Twinkle-inspired style profile)

Reference extraction basis that informed those notes:

- upstream reference: `xanderfrangos/twinkle-tray`
- confirmed metadata inputs: `package.json`, `package-lock.json`
- build/profile cues:
  - Electron shell
  - React renderer
  - Sass/SCSS pipeline
  - Parcel build path in upstream
  - Electron Builder packaging
