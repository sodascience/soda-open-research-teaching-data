# Dataset specification: OpenAlex teaching sample v1

Purpose: a reusable, moderately sized relational dataset for joins, missingness, visualization, sampling, bibliometrics, research methods, and AI-assisted analysis. It is a teaching resource rather than a representative cross-section of all scholarship.

## Sampling frame

The initial `config/v1.json` defines core corpus, language `en`, type `article`, `has_abstract:true`, years 2011–2025, and primary field IDs 11–36. The live `/fields` taxonomy is frozen and must match these 26 fields before sampling. Each year × field receives 30 sampled works with API seed 20261016. Classification uses `primary_topic.field.id`, avoiding overlap from secondary topics. No additional exclusions are applied to retracted or closed-access works.

For each stratum a separate filtered count query records eligible population N, followed by a seeded sample query. The manifest records ID, year, field, stratum, seed, N, nominal inclusion probability 30/N, weight N/30, timestamp, corpus, and exact filter. Count and sample are adjacent API calls, not an atomic database snapshot; population changes between calls remain possible. Weights are approximate design weights conditional on OpenAlex's sampling behavior and the recorded eligible frame; they do not correct coverage or classification errors.

## Contents

Full raw JSON records and per-stratum API responses preserve source fields even when not projected into tables. Public abstract representation remains `abstract_inverted_index` only. Relational CSV output includes all 16 tables in the codebook. Entity dimensions are dehydrated metadata present in sampled work responses, not independently enriched author/institution/source profiles. First non-null observed entity metadata in sorted work-ID order wins if observations disagree; raw JSON preserves all observations.

## Interpretation and limits

- Equal allocation overrepresents smaller fields and years relative to their corpus sizes. Apply design weights only for eligible-frame estimates with appropriate survey methods.
- English refers to detected metadata language, and abstracts are required. This excludes many works and languages. `article` does not include every scholarly publication format.
- OpenAlex topic, keyword, SDG, and study-design labels are machine-generated and may be wrong or missing. Empty study designs do not imply absence of a study.
- Citation metrics and retraction status reflect retrieval time. Recent publications have shorter citation exposure. FWCI and percentiles can be absent. APC paid can be an estimate rather than an observed payment; retain provenance.
- Authorships can be capped at 100. Computed counts describe exported arrays, not necessarily complete real-world teams. `authorships_truncated` flags arrays of at least 100 as potentially truncated.
- Reference targets may lie outside the sample. Only the citing work is a foreign key; this is not a closed citation network.
- Citation-year records are a rolling window and omit zero years; they need not sum to lifetime `cited_by_count`. Missing years must not automatically be treated as observed zeros outside that window.
- OA status, metadata CC0 status, and an article's license are distinct. Null article licenses remain null.

## Version policy

Dataset 1.0.0 and schema 1.0.0 define this initial design. Freeze and archive IDs **and metadata** together. Create a new dataset version for any new retrieval, sample, source correction, or transformation change that alters data. Bump schema version for changed table contracts. Keep config, source revision, release metadata, and checksums with each archive. `checksums.json` detects accidental modification, not malicious modification by someone who can replace checksums too.

The initial production snapshot was generated locally on 2026-10-16 and passed validation: 11,700 distinct eligible works across 390 strata. Raw snapshot: `data/raw/1.0.0`; derived release: `data/releases/1.0.0`. These artifacts are excluded from Git and have not been published. The checksummed `release.json` records actual row counts for all tables.

## Sources checked 2026-10-16

- [Works attributes](https://help.openalex.org/data/works/attributes/)
- [Core and expansion corpus](https://help.openalex.org/data/works/corpus/)
- [API sampling and batch recipes](https://help.openalex.org/how-to/api-recipes/)
- [Filters](https://help.openalex.org/api/filtering/)
- [Authentication](https://help.openalex.org/api/authentication/)
- [Deprecations](https://help.openalex.org/api/deprecations/)

Current API uses `funders` and `awards`; removed `grants` is not used. The active SDG field is retained rather than the deprecated Aurora mirror.

## Deposit packaging

The `sample` command now builds and packages a completed sample automatically.
The `build` command also packages by default (`--no-package` opts out).
For existing snapshots and releases, `package` creates both ZIPs and supporting
Zenodo deposit files in a new output directory without querying OpenAlex.
See the README's automatic packaging section for commands and contents.

Packaging an older release preserves its original `release.json` and checksums.
The included source may be a newer builder; its exact hashes and packager version
are recorded separately. Reproducibility comparison verifies the CSV tables,
manifest, and schema; it excludes builder provenance in a newly generated
`release.json`. No published snapshot or release is modified by packaging.

The builder enforces its implemented `SCHEMA_VERSION` against the config's
`schema_version`. The initial sampler supports integer stratum sizes of 1–100,
using one API page per stratum. The initial config uses 30. Archive `SAMPLING.md`
records the actual release parameters and takes precedence over this initial v1
specification when a later configuration uses different years, fields, or counts.

Both ZIPs belong in one versioned Zenodo record. Each published record version
has a distinct version DOI and shares the concept DOI with all versions. Cite
the version DOI for reproducibility; use the concept DOI for project-level links.
Metadata-only record edits do not need a new DOI. Source-only changes do not
require a dataset publication; publishing changed archive files uses Zenodo's
versioning workflow. See https://zenodo.org/help/versioning.
