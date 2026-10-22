# SAMA equipment library

Public read-only catalogue at `knowledge/equipment/index.html`, linked from the preview card in `knowledge-base.html`.

- Add categories/types/models to `catalog.json`; IDs must be unique and stable.
- Model records specify country/market, manufacturer, exact configuration, verification date and primary source URL.
- `verified: false` is a type guide with no invented technical numbers. Brand directories include brands whose verified model sheets are still pending. A directory entry is not a claim of complete model coverage.
- `specs` values preserve published units; distinguish inner dimensions, transport envelope, operating weight, tare and payload. Missing dimensions stay explicitly unavailable.
- `photo` points to a manufacturer image or a licensed local photograph. A labelled schematic replaces unavailable images. Photos are illustrative, not a guarantee of the exact configuration.
- Vessel types have a `group` in `seaGroups`. The 50 photographed type guides cover nine operational families; this is not a claim of every possible vessel subtype or model. The existing Damen model sheet remains separate.
- Container types have a `group` in `containerGroups`: 33 types and 51 configurations cover eight families, including regional intermodal equipment, offshore cargo containers and air-cargo ULDs. Options such as controlled atmosphere and bulk liners are explicitly distinguished from standalone container designs.
- Container cards pair translated applications/construction with published source-specific dimensions, openings, volume and weights. Some specialised records publish only a subset. Do not invent missing values or treat one model as a universal standard. Calculated gross/payload values are explicitly labelled. Static storage and lifting ratings are kept separate from transport payload. Manufacturer inconsistencies are disclosed rather than silently reconciled.
- Road transport covers 44 types and 54 manufacturer/reference cards in eight families, with examples from 12 countries/markets. All have real representative photographs; 51 include published technical specifications and three remain descriptive guides. This is broad family coverage, not an inventory of every model worldwide.
- Road dimensions, axles, road tyres, spare tyres, tare, technical gross weight, payload, lifting capacity and volume remain separately labelled. Missing comparison fields are explicitly unavailable. Tyre sizes retain the manufacturer's notation. Axle lines are not ordinary axles; module support ratings and gross combination mass are not cargo payload. Country denotes the example's market, not exclusive availability or legal approval. Source conflicts and family-wide options are disclosed in each card.
- Type guides use `guide` for translated cargo/purpose and distinguishing characteristics. They keep `specs` empty: descriptive guidance must not be presented as verified model dimensions.
- Local photographs live in `assets/knowledge/vessels/`, `assets/knowledge/containers/` and `assets/knowledge/road/`. Each record's `photo_credit` includes the source file page, author, title, license link and resizing/conversion disclosure. Preserve these credits in detail and enlarged views. `photo_type_example` and optional `photo_note` identify representative family photos. Externally hosted operator/manufacturer photos use `photo_credit.external`, author and source attribution; this does not assert a reusable licence.
- Add EN/TR/AR labels through `equipment-i18n.js`, registered with the existing `SamaLanguage` client. Do not create another language preference or translator.
- Country/model/family filters persist in URL parameters prefixed `eq_`; no business records or visitor data are stored. `eq_group` is scoped to the selected sea, container or road category.
- To publish, deploy committed static files through the repository's GitHub Pages branch. Changes must preserve the maps and shared language assets.

Initial source review: 22 October 2026. This release provides the catalogue framework and the explicitly listed source-backed records, not an exhaustive catalogue of every world manufacturer/model.

Run `node knowledge/equipment/validate.mjs` to validate IDs, translated names and guide prose, source links, family membership, photo assets and attribution completeness.
