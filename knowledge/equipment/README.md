# SAMA equipment library

Public read-only catalogue, embedded in `knowledge-base.html` and available at `knowledge/equipment/index.html`.

- Add categories/types/models to `catalog.json`; IDs must be unique and stable.
- Model records specify country/market, manufacturer, exact configuration, verification date and primary source URL.
- `verified: false` is a type guide with no invented technical numbers. Brand directories include brands whose verified model sheets are still pending. A directory entry is not a claim of complete model coverage.
- `specs` values preserve published units; distinguish inner dimensions, transport envelope, operating weight, tare and payload. Missing dimensions stay explicitly unavailable.
- `photo` points to a manufacturer image with a source link; a labelled schematic replaces unavailable images. Photos are illustrative, not a guarantee of the exact configuration.
- Add EN/TR/AR labels through `equipment-i18n.js`, registered with the existing `SamaLanguage` client. Do not create another language preference or translator.
- Country/model filters persist in URL parameters prefixed `eq_`; no business records or visitor data are stored.
- To publish, deploy committed static files through the repository's GitHub Pages branch. Changes must preserve the maps and shared language assets.

Initial source review: 22 October 2026. This release provides the catalogue framework and the explicitly listed source-backed records, not an exhaustive catalogue of every world manufacturer/model.
