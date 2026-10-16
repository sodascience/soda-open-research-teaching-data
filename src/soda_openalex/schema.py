"""Versioned CSV column contracts. Nested source metadata uses JSON cells."""
SCHEMA_VERSION = "1.0.0"

SCHEMA = {
    "works": "work_id doi title publication_date publication_year language type primary_topic_id primary_topic_name subfield_id subfield_name field_id field_name domain_id domain_name source_id source_name source_type is_oa oa_status oa_url license cited_by_count fwci citation_normalized_percentile is_in_top_1_percent is_in_top_10_percent is_retracted pmid pmcid indexed_in has_fulltext has_content_pdf has_content_grobid_xml authors_count institutions_count countries_count references_count locations_count funders_count awards_count keywords_count study_designs_count sdgs_count apc_list_value apc_list_currency apc_list_value_usd apc_list_provenance apc_paid_value apc_paid_currency apc_paid_value_usd apc_paid_provenance created_date updated_date stratum_id population_count inclusion_probability sampling_weight authorships_truncated",
    "abstracts": "work_id abstract_inverted_index",
    "authors": "author_id display_name orcid",
    "authorships": "work_id authorship_index author_id author_position is_corresponding raw_author_name raw_affiliation_strings countries",
    "affiliations": "work_id authorship_index institution_id",
    "institutions": "institution_id display_name ror country_code type lineage",
    "sources": "source_id display_name issn_l issn type is_oa is_in_doaj host_organization host_organization_name",
    "topics": "work_id topic_index topic_id display_name score subfield_id subfield_name field_id field_name domain_id domain_name",
    "keywords": "work_id keyword_index keyword_id display_name score",
    "sdgs": "work_id sdg_index sdg_id display_name score",
    "study_designs": "work_id study_design_index study_design_id display_name",
    "references": "work_id reference_index referenced_work_id",
    "funding": "work_id funding_index kind funder_id funder_name award_id award_name funder_award_id doi raw_json",
    "locations": "work_id location_index source_id is_primary is_best_oa landing_page_url pdf_url is_oa license license_id version is_accepted is_published raw_json",
    "citations_by_year": "work_id year cited_by_count",
}
SCHEMA = {name: columns.split() for name, columns in SCHEMA.items()}
KEYS = {name: cols[:2] for name, cols in SCHEMA.items()}
for name in ("works", "abstracts", "authors", "institutions", "sources"):
    KEYS[name] = SCHEMA[name][:1]
KEYS["affiliations"] = ["work_id", "authorship_index", "institution_id"]
