"""Pure transformation of frozen works; no abstract reconstruction."""
from .schema import SCHEMA


def transform(works, manifest):
    tables = {name: [] for name in SCHEMA}
    entities = {name: {} for name in ("authors", "institutions", "sources")}

    def entity(table, obj, key):
        if obj and obj.get("id"):
            row = {key: obj["id"], **{k: obj.get(k) for k in SCHEMA[table] if k != key}}
            # First observation in sorted work order wins; never overwrite with nulls.
            current = entities[table].setdefault(obj["id"], row)
            for k, value in row.items():
                if current.get(k) is None:
                    current[k] = value
            return obj["id"]
        return None

    for w in sorted(works, key=lambda x: x["id"]):
        wid = w["id"]
        m = manifest[wid]
        primary = w.get("primary_location") or {}
        source = primary.get("source") or {}
        topic = w.get("primary_topic") or {}
        authorships = w.get("authorships") or []
        row = {key: w.get(key) for key in SCHEMA["works"]}
        row.update(work_id=wid, primary_topic_id=topic.get("id"), primary_topic_name=topic.get("display_name"),
                   source_id=entity("sources", source, "source_id"), source_name=source.get("display_name"),
                   source_type=source.get("type"), license=primary.get("license"),
                   **{key: m[key] for key in ("stratum_id", "population_count", "inclusion_probability", "sampling_weight")})
        for level in ("subfield", "field", "domain"):
            obj = topic.get(level) or {}
            row[level + "_id"], row[level + "_name"] = obj.get("id"), obj.get("display_name")
        for key in ("is_oa", "oa_status", "oa_url"):
            row[key] = (w.get("open_access") or {}).get(key)
        for key in ("pmid", "pmcid"):
            row[key] = (w.get("ids") or {}).get(key)
        for key in ("pdf", "grobid_xml"):
            row["has_content_" + key] = (w.get("has_content") or {}).get(key)
        percentile = w.get("citation_normalized_percentile") or {}
        row["citation_normalized_percentile"] = percentile.get("value")
        for key in ("is_in_top_1_percent", "is_in_top_10_percent"):
            row[key] = percentile.get(key)
        for kind in ("list", "paid"):
            for key in ("value", "currency", "value_usd", "provenance"):
                row[f"apc_{kind}_{key}"] = (w.get("apc_" + kind) or {}).get(key)
        institutions, countries = set(), set()
        for i, a in enumerate(authorships):
            aid = entity("authors", a.get("author"), "author_id")
            tables["authorships"].append(dict(work_id=wid, authorship_index=i, author_id=aid,
                **{k: a.get(k) for k in SCHEMA["authorships"][3:]}))
            countries.update(a.get("countries") or [])
            seen_institutions = set()
            for inst in a.get("institutions") or []:
                iid = entity("institutions", inst, "institution_id")
                if iid and iid not in seen_institutions:
                    seen_institutions.add(iid)
                    institutions.add(iid)
                    tables["affiliations"].append(dict(work_id=wid, authorship_index=i, institution_id=iid))
        row.update(authors_count=len(authorships), institutions_count=len(institutions), countries_count=len(countries),
                   authorships_truncated=len(authorships) >= 100)
        tables["abstracts"].append(dict(work_id=wid, abstract_inverted_index=w.get("abstract_inverted_index")))
        for table, attribute, stem in (("topics", "topics", "topic"), ("keywords", "keywords", "keyword"),
                ("sdgs", "sustainable_development_goals", "sdg"), ("study_designs", "study_designs", "study_design")):
            values = w.get(attribute) or []
            if table != "topics":
                row[table + "_count"] = len(values)
            for i, obj in enumerate(values):
                child = dict(work_id=wid, **{stem + "_index": i, stem + "_id": obj.get("id")},
                             display_name=obj.get("display_name"), score=obj.get("score"))
                if table == "topics":
                    for level in ("subfield", "field", "domain"):
                        child[level + "_id"] = (obj.get(level) or {}).get("id")
                        child[level + "_name"] = (obj.get(level) or {}).get("display_name")
                tables[table].append(child)
        refs = w.get("referenced_works") or []
        row["references_count"] = len(refs)
        for i, ref in enumerate(refs):
            tables["references"].append(dict(work_id=wid, reference_index=i, referenced_work_id=ref))
        locations = w.get("locations") or []
        row["locations_count"] = len(locations)
        for i, loc in enumerate(locations):
            sid = entity("sources", loc.get("source"), "source_id")
            tables["locations"].append(dict(work_id=wid, location_index=i, source_id=sid,
                is_primary=loc == primary, is_best_oa=loc == w.get("best_oa_location"), raw_json=loc,
                **{k: loc.get(k) for k in SCHEMA["locations"][5:-1]}))
        funding_index = 0
        for attribute, kind in (("funders", "funder"), ("awards", "award")):
            values = w.get(attribute) or []
            row[attribute + "_count"] = len(values)
            for obj in values:
                tables["funding"].append(dict(work_id=wid,
                    funding_index=funding_index, kind=kind,
                    funder_id=obj.get("id") if kind == "funder" else obj.get("funder_id"),
                    funder_name=obj.get("display_name") if kind == "funder" else obj.get("funder_display_name"),
                    award_id=obj.get("id") if kind == "award" else None,
                    award_name=obj.get("display_name") if kind == "award" else None,
                    funder_award_id=obj.get("funder_award_id"), doi=obj.get("doi"), raw_json=obj))
                funding_index += 1
        for counts in w.get("counts_by_year") or []:
            tables["citations_by_year"].append(dict(work_id=wid, year=counts["year"], cited_by_count=counts["cited_by_count"]))
        tables["works"].append(row)
    for table, values in entities.items():
        tables[table] = [values[key] for key in sorted(values)]
    return tables
