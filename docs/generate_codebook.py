"""Regenerate the column inventory from the versioned contract."""
import argparse
from pathlib import Path
from soda_openalex.schema import SCHEMA, KEYS, SCHEMA_VERSION

p = Path(__file__).with_name('CODEBOOK.md')
header = '''# Codebook — schema 1.0.0

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

'''
special = {
'work_id':'Sampled OpenAlex work identifier', 'abstract_inverted_index':'JSON token → positions object',
'population_count':'Eligible stratum count N (integer)', 'inclusion_probability':'Nominal n/N (float)',
'sampling_weight':'Nominal N/n (float)', 'stratum_id':'Publication year:integer field ID',
'authors_count':'Number of exported authorship entries, including any repeated author IDs (integer)',
'institutions_count':'Distinct institution IDs across exported authorships (integer)',
'countries_count':'Distinct country codes across exported authorships (integer)',
'funding_index':'Zero-based position across funders followed by awards for this work',
'authorships_truncated':'Possible API truncation flag', 'raw_json':'Full source relationship object (JSON)',
'kind':'Source array: funder or award', 'referenced_work_id':'External cited work identifier; may be outside sample',
'year':'Citation calendar year (integer)', 'publication_year':'Publication year (integer)',
'language':'Detected metadata language (ISO 639-1)', 'type':'OpenAlex work/source/institution type for this table',
'raw_affiliation_strings':'JSON array of original affiliation text; not a one-to-one institution map',
'author_position':'Source first/middle/last authorship role', 'license':'Article/location license string, nullable',
'license_id':'Source license identifier', 'version':'Location publication version',
'has_fulltext':'Source full-text availability flag', 'has_content_pdf':'Source PDF availability flag',
'has_content_grobid_xml':'Source XML availability flag', 'doi':'DOI URL as reported',
'pmid':'PubMed identifier URI', 'pmcid':'PubMed Central identifier URI', 'orcid':'ORCID URI', 'ror':'ROR URI',
'country_code':'Source country code', 'issn_l':'Linking ISSN', 'score':'Source assignment score (numeric)',
'oa_status':'Source open-access category', 'fwci':'Source field-weighted citation impact (float)',
'citation_normalized_percentile':'Source normalized citation percentile value (float)',
'cited_by_count':'Lifetime or annual citations according to table (integer)',
'created_date':'OpenAlex creation date (ISO)', 'updated_date':'OpenAlex update timestamp (ISO)',
'publication_date':'Source publication date (ISO)', 'title':'Work title as reported',
'display_name':'Source display label', 'host_organization':'Source host organization identifier',
'raw_author_name':'Author name as reported', 'funder_award_id':'Funder’s own award number',
'indexed_in':'JSON array of index names', 'issn':'JSON array of ISSNs', 'lineage':'JSON array of ancestor institution IDs',
'countries':'JSON array of authorship country codes', 'is_in_top_1_percent':'Source top-1-percent flag',
'is_in_top_10_percent':'Source top-10-percent flag',
'is_oa':'Open-access flag (boolean)', 'is_in_doaj':'Source is listed in DOAJ (boolean)',
'is_best_oa':'Location object equals the work’s best_oa_location (boolean)',
'is_primary':'Location object equals the work’s primary_location (boolean)'}
text=header.replace('schema 1.0.0', f'schema {SCHEMA_VERSION}')
for table, columns in SCHEMA.items():
 text += f'## {table}.csv\n\nPrimary key: '+', '.join('`'+k+'`' for k in KEYS[table])+'.\n\n| Column | Meaning / representation |\n| --- | --- |\n'
 for c in columns:
  if table == 'works' and c == 'is_oa': desc='Work open_access.is_oa (boolean)'
  elif table == 'works' and c == 'license': desc='License of primary_location, nullable; other location licenses remain in locations.csv'
  elif table == 'works' and c == 'oa_status': desc='Work open_access.oa_status category'
  elif table == 'works' and c == 'oa_url': desc='Work open_access.oa_url; not fetched'
  elif table == 'works' and c == 'source_id': desc='Primary-location source identifier (string)'
  elif table == 'works' and c == 'type': desc='OpenAlex work type (string)'
  elif table == 'sources' and c == 'type': desc='OpenAlex source type (string)'
  elif table == 'institutions' and c == 'type': desc='OpenAlex institution type (string)'
  elif table == 'locations' and c == 'is_oa': desc='Location is_oa flag (boolean)'
  elif table == 'sources' and c == 'is_oa': desc='Source is_oa flag (boolean)'
  elif c in special: desc=special[c]
  elif c.endswith('_index'): desc='Zero-based position within the work array (integer)'
  elif c.endswith('_count'): desc='Count of exported '+c[:-6].replace('_',' ')+' (integer)'
  elif c.endswith('_id'): desc=c[:-3].replace('_',' ').capitalize()+' identifier (string)'
  elif c.endswith('_name'): desc=c[:-5].replace('_',' ').capitalize()+' display label (string)'
  elif c.startswith('is_'): desc=c[3:].replace('_',' ').capitalize()+' flag (boolean)'
  elif c.startswith('apc_'):
   kind = 'list-price' if c.startswith('apc_list_') else 'estimated paid'
   attribute = c.removeprefix('apc_list_').removeprefix('apc_paid_')
   description = {'value': 'amount in the reported currency (numeric)', 'value_usd': 'amount in USD (numeric)', 'currency': 'currency code (string)', 'provenance': 'source or estimation provenance (string)'}
   desc = f'APC {kind} {description[attribute]}'
  elif c.endswith('_url'): desc=c[:-4].replace('_',' ').capitalize()+' URL; not fetched'
  elif c=='source_type': desc='Primary source type (string)'
  else: raise ValueError(c)
  text+=f'| `{c}` | {desc}. |\n'
 text+='\n'
text+='''## sample_manifest.csv

One row per sampled work; primary key `work_id`. Columns: work_id (URL), publication_year (integer), field_id (integer, unlike full URLs in works), stratum_id (year:field), seed (integer), population_count (integer N), inclusion_probability (n/N), sampling_weight (N/n), retrieved_at (UTC ISO timestamp), filter (exact API filter), corpus (core).

## Supporting files

`schema.json` fixes column order. `release.json` records builder/dataset/schema versions, table row counts, and snapshot checksums. `checksums.json` maps relative paths to SHA-256 digests, excluding itself. `fields.json` freezes taxonomy; `config.json` freezes design; `response-<year>-<field>.json` preserves sampled response envelopes. `works.jsonl` contains full work objects sorted by ID.
'''
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true', help='Check that the committed codebook matches the schema and descriptions')
parser.add_argument('--output', type=Path, help='Write to another path instead of docs/CODEBOOK.md')
args = parser.parse_args()
if args.check and args.output:
 parser.error('--check and --output cannot be combined')
if args.check:
 if not p.is_file() or p.read_text(encoding='utf-8') != text:
  parser.exit(1, 'Codebook is out of date; run uv run python docs/generate_codebook.py\n')
 print('Codebook matches the implemented schema and descriptions.')
else:
 (args.output or p).write_text(text, encoding='utf-8', newline='\n')
