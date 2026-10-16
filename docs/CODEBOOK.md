# Codebook — schema 1.0.0

UTF-8 CSV; empty cells mean null/unknown. Booleans are `true`/`false`; numbers use decimal notation. IDs, labels, dates, and URLs are strings. Arrays and objects are JSON cells. Relationship indexes are zero-based within each work; funding_index spans funders followed by awards. Full OpenAlex identifier URLs are preserved.

All relationship `work_id` columns join to `works.work_id`. Authorship author IDs join to authors; affiliation institution IDs join to institutions; affiliation `(work_id, authorship_index)` joins to authorships; work/location source IDs join to sources. Reference targets and funding/classification IDs are external IDs and need not occur elsewhere in the sample.

Works are one row per sampled ID. Abstracts contain one inverted index per sampled work. Authors, institutions, and sources are unique observed entity IDs with dehydrated metadata from work responses. Topics, keywords, SDGs, and study designs contain work assignments; they are not entity dimensions. Funding has one observation per funder or award (`kind`); these can overlap and must not be summed as independent grants. Locations contain one row per source array entry. Citations by year contain one reported year per work. Affiliations contain one distinct institution per authorship; raw strings stay on authorships because they do not reliably map to individual institutions.

## Interpretation

- `citation_normalized_percentile` is the source object's `value`; top-1/top-10 flags are copied from that object. `fwci` is expected-relative citation impact. Missing metrics stay null.
- `cited_by_count` is lifetime on works and annual on citations_by_year. Annual series omit zeros and cover a rolling window; they need not sum to lifetime counts.
- Work counts are lengths of exported arrays, with distinct institution IDs and country codes across authorships. Missing arrays yield zero observed rows, not proof of real-world absence. Authors can be capped at 100; `authorships_truncated` flags at least 100 as potentially incomplete.
- APC list/paid value and USD value are numeric; currency and provenance are strings. Paid can be an estimate. Article/location licenses are separate from metadata CC0.
- Abstract indexes are JSON token-to-integer-position-list objects. No plaintext abstracts are generated. `raw_json` preserves full relationship objects. `indexed_in`, `issn`, `lineage`, `countries`, and raw affiliation strings are JSON arrays.
- `is_primary` and `is_best_oa` compare a location object with the corresponding work object. Source links may be null. No linked full text is fetched.
- Assignment scores are source numbers and differ in interpretation by classifier; study designs may have no score. Empty tags are not evidence of absence.
- Dates use ISO strings as supplied. Metadata and citation values reflect retrieval time. Entity metadata uses the first non-null observation in sorted work-ID order.

## works.csv

Primary key: `work_id`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `doi` | DOI URL as reported. |
| `title` | Work title as reported. |
| `publication_date` | Source publication date (ISO). |
| `publication_year` | Publication year (integer). |
| `language` | Detected metadata language (ISO 639-1). |
| `type` | OpenAlex work type (string). |
| `primary_topic_id` | Primary topic identifier (string). |
| `primary_topic_name` | Primary topic display label (string). |
| `subfield_id` | Subfield identifier (string). |
| `subfield_name` | Subfield display label (string). |
| `field_id` | Field identifier (string). |
| `field_name` | Field display label (string). |
| `domain_id` | Domain identifier (string). |
| `domain_name` | Domain display label (string). |
| `source_id` | Primary-location source identifier (string). |
| `source_name` | Source display label (string). |
| `source_type` | Primary source type (string). |
| `is_oa` | Work open_access.is_oa (boolean). |
| `oa_status` | Work open_access.oa_status category. |
| `oa_url` | Work open_access.oa_url; not fetched. |
| `license` | License of primary_location, nullable; other location licenses remain in locations.csv. |
| `cited_by_count` | Lifetime or annual citations according to table (integer). |
| `fwci` | Source field-weighted citation impact (float). |
| `citation_normalized_percentile` | Source normalized citation percentile value (float). |
| `is_in_top_1_percent` | Source top-1-percent flag. |
| `is_in_top_10_percent` | Source top-10-percent flag. |
| `is_retracted` | Retracted flag (boolean). |
| `pmid` | PubMed identifier URI. |
| `pmcid` | PubMed Central identifier URI. |
| `indexed_in` | JSON array of index names. |
| `has_fulltext` | Source full-text availability flag. |
| `has_content_pdf` | Source PDF availability flag. |
| `has_content_grobid_xml` | Source XML availability flag. |
| `authors_count` | Number of exported authorship entries, including any repeated author IDs (integer). |
| `institutions_count` | Distinct institution IDs across exported authorships (integer). |
| `countries_count` | Distinct country codes across exported authorships (integer). |
| `references_count` | Count of exported references (integer). |
| `locations_count` | Count of exported locations (integer). |
| `funders_count` | Count of exported funders (integer). |
| `awards_count` | Count of exported awards (integer). |
| `keywords_count` | Count of exported keywords (integer). |
| `study_designs_count` | Count of exported study designs (integer). |
| `sdgs_count` | Count of exported sdgs (integer). |
| `apc_list_value` | APC list-price amount in the reported currency (numeric). |
| `apc_list_currency` | APC list-price currency code (string). |
| `apc_list_value_usd` | APC list-price amount in USD (numeric). |
| `apc_list_provenance` | APC list-price source or estimation provenance (string). |
| `apc_paid_value` | APC estimated paid amount in the reported currency (numeric). |
| `apc_paid_currency` | APC estimated paid currency code (string). |
| `apc_paid_value_usd` | APC estimated paid amount in USD (numeric). |
| `apc_paid_provenance` | APC estimated paid source or estimation provenance (string). |
| `created_date` | OpenAlex creation date (ISO). |
| `updated_date` | OpenAlex update timestamp (ISO). |
| `stratum_id` | Publication year:integer field ID. |
| `population_count` | Eligible stratum count N (integer). |
| `inclusion_probability` | Nominal n/N (float). |
| `sampling_weight` | Nominal N/n (float). |
| `authorships_truncated` | Possible API truncation flag. |

## abstracts.csv

Primary key: `work_id`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `abstract_inverted_index` | JSON token → positions object. |

## authors.csv

Primary key: `author_id`.

| Column | Meaning / representation |
| --- | --- |
| `author_id` | Author identifier (string). |
| `display_name` | Source display label. |
| `orcid` | ORCID URI. |

## authorships.csv

Primary key: `work_id`, `authorship_index`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `authorship_index` | Zero-based position within the work array (integer). |
| `author_id` | Author identifier (string). |
| `author_position` | Source first/middle/last authorship role. |
| `is_corresponding` | Corresponding flag (boolean). |
| `raw_author_name` | Author name as reported. |
| `raw_affiliation_strings` | JSON array of original affiliation text; not a one-to-one institution map. |
| `countries` | JSON array of authorship country codes. |

## affiliations.csv

Primary key: `work_id`, `authorship_index`, `institution_id`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `authorship_index` | Zero-based position within the work array (integer). |
| `institution_id` | Institution identifier (string). |

## institutions.csv

Primary key: `institution_id`.

| Column | Meaning / representation |
| --- | --- |
| `institution_id` | Institution identifier (string). |
| `display_name` | Source display label. |
| `ror` | ROR URI. |
| `country_code` | Source country code. |
| `type` | OpenAlex institution type (string). |
| `lineage` | JSON array of ancestor institution IDs. |

## sources.csv

Primary key: `source_id`.

| Column | Meaning / representation |
| --- | --- |
| `source_id` | Source identifier (string). |
| `display_name` | Source display label. |
| `issn_l` | Linking ISSN. |
| `issn` | JSON array of ISSNs. |
| `type` | OpenAlex source type (string). |
| `is_oa` | Source is_oa flag (boolean). |
| `is_in_doaj` | Source is listed in DOAJ (boolean). |
| `host_organization` | Source host organization identifier. |
| `host_organization_name` | Host organization display label (string). |

## topics.csv

Primary key: `work_id`, `topic_index`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `topic_index` | Zero-based position within the work array (integer). |
| `topic_id` | Topic identifier (string). |
| `display_name` | Source display label. |
| `score` | Source assignment score (numeric). |
| `subfield_id` | Subfield identifier (string). |
| `subfield_name` | Subfield display label (string). |
| `field_id` | Field identifier (string). |
| `field_name` | Field display label (string). |
| `domain_id` | Domain identifier (string). |
| `domain_name` | Domain display label (string). |

## keywords.csv

Primary key: `work_id`, `keyword_index`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `keyword_index` | Zero-based position within the work array (integer). |
| `keyword_id` | Keyword identifier (string). |
| `display_name` | Source display label. |
| `score` | Source assignment score (numeric). |

## sdgs.csv

Primary key: `work_id`, `sdg_index`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `sdg_index` | Zero-based position within the work array (integer). |
| `sdg_id` | Sdg identifier (string). |
| `display_name` | Source display label. |
| `score` | Source assignment score (numeric). |

## study_designs.csv

Primary key: `work_id`, `study_design_index`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `study_design_index` | Zero-based position within the work array (integer). |
| `study_design_id` | Study design identifier (string). |
| `display_name` | Source display label. |

## references.csv

Primary key: `work_id`, `reference_index`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `reference_index` | Zero-based position within the work array (integer). |
| `referenced_work_id` | External cited work identifier; may be outside sample. |

## funding.csv

Primary key: `work_id`, `funding_index`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `funding_index` | Zero-based position across funders followed by awards for this work. |
| `kind` | Source array: funder or award. |
| `funder_id` | Funder identifier (string). |
| `funder_name` | Funder display label (string). |
| `award_id` | Award identifier (string). |
| `award_name` | Award display label (string). |
| `funder_award_id` | Funder’s own award number. |
| `doi` | DOI URL as reported. |
| `raw_json` | Full source relationship object (JSON). |

## locations.csv

Primary key: `work_id`, `location_index`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `location_index` | Zero-based position within the work array (integer). |
| `source_id` | Source identifier (string). |
| `is_primary` | Location object equals the work’s primary_location (boolean). |
| `is_best_oa` | Location object equals the work’s best_oa_location (boolean). |
| `landing_page_url` | Landing page URL; not fetched. |
| `pdf_url` | Pdf URL; not fetched. |
| `is_oa` | Location is_oa flag (boolean). |
| `license` | Article/location license string, nullable. |
| `license_id` | Source license identifier. |
| `version` | Location publication version. |
| `is_accepted` | Accepted flag (boolean). |
| `is_published` | Published flag (boolean). |
| `raw_json` | Full source relationship object (JSON). |

## citations_by_year.csv

Primary key: `work_id`, `year`.

| Column | Meaning / representation |
| --- | --- |
| `work_id` | Sampled OpenAlex work identifier. |
| `year` | Citation calendar year (integer). |
| `cited_by_count` | Lifetime or annual citations according to table (integer). |

## sample_manifest.csv

One row per sampled work; primary key `work_id`. Columns: work_id (URL), publication_year (integer), field_id (integer, unlike full URLs in works), stratum_id (year:field), seed (integer), population_count (integer N), inclusion_probability (n/N), sampling_weight (N/n), retrieved_at (UTC ISO timestamp), filter (exact API filter), corpus (core).

## Supporting files

`schema.json` fixes column order. `release.json` records builder/dataset/schema versions, table row counts, and snapshot checksums. `checksums.json` maps relative paths to SHA-256 digests, excluding itself. `fields.json` freezes taxonomy; `config.json` freezes design; `response-<year>-<field>.json` preserves sampled response envelopes. `works.jsonl` contains full work objects sorted by ID.
