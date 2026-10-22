# SAMA equipment library

Public read-only catalogue at `knowledge/equipment/index.html`, linked from the preview card in `knowledge-base.html`.

- Add categories/types/models to `catalog.json`; IDs must be unique and stable.
- Model records specify country/market, manufacturer, exact configuration, verification date and primary source URL.
- `verified: false` is a type guide with no invented technical numbers. Brand directories include brands whose verified model sheets are still pending. A directory entry is not a claim of complete model coverage.
- `specs` values preserve published units; distinguish inner dimensions, transport envelope, operating weight, tare and payload. Missing dimensions stay explicitly unavailable.
- `photo` points to a manufacturer image or a licensed local vessel photograph. A labelled schematic replaces unavailable images. Photos are illustrative, not a guarantee of the exact configuration.
- Vessel types have a `group` in `seaGroups`. The 50 photographed type guides cover nine operational families; this is not a claim of every possible vessel subtype or model. The existing Damen model sheet remains separate.
- Type guides use `guide` for translated cargo/purpose and distinguishing characteristics. They keep `specs` empty: descriptive guidance must not be presented as verified model dimensions.
- Local photographs live in `assets/knowledge/vessels/`. Each record's `photo_credit` includes the source file page, author, title, license link and resizing/conversion disclosure. Preserve these credits in detail and enlarged views. `photo_type_example` explicitly identifies representative photos used on model cards.
- Add EN/TR/AR labels through `equipment-i18n.js`, registered with the existing `SamaLanguage` client. Do not create another language preference or translator.
- Country/model/family filters persist in URL parameters prefixed `eq_`; no business records or visitor data are stored. `eq_group` applies only to the sea category.
- To publish, deploy committed static files through the repository's GitHub Pages branch. Changes must preserve the maps and shared language assets.

Initial source review: 22 October 2026. This release provides the catalogue framework and the explicitly listed source-backed records, not an exhaustive catalogue of every world manufacturer/model.

Run `node knowledge/equipment/validate.mjs` to validate IDs, translated names and guide prose, source links, family membership, photo assets and attribution completeness.
