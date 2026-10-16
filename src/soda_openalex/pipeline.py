"""Immutable sampling snapshots and deterministic, verified CSV releases."""
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from . import __version__
from .api import Client, MAX_PER_PAGE
from .schema import SCHEMA, KEYS, SCHEMA_VERSION
from .transform import transform


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list, bool)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: cell(row.get(key)) for key in columns} for row in rows)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def stratum(year, field):
    return f"{year}:{field}"


def check_config(config):
    require(config["corpus"] == "core" and config["language"] == "en" and config["type"] == "article"
            and config["has_abstract"] is True, "Unsupported eligibility design")
    require(config["schema_version"] == SCHEMA_VERSION,
            f"Unsupported schema version; this builder implements {SCHEMA_VERSION}")
    require(type(config["works_per_stratum"]) is int and 0 < config["works_per_stratum"] <= MAX_PER_PAGE,
            f"Stratum size must be an integer from 1 to {MAX_PER_PAGE}; this sampler uses one page per stratum")
    for key in ("years", "field_ids"):
        require(len(config[key]) == len(set(config[key])) and bool(config[key]), f"Invalid {key}")


def validate_raw(works, rows, config):
    check_config(config)
    expected = {stratum(y, f) for y in config["years"] for f in config["field_ids"]}
    n = config["works_per_stratum"]
    require(len(rows) == len(works) == n * len(expected), "Incorrect sample size")
    ids = [w["id"] for w in works]
    require(len(set(ids)) == len(ids), "Duplicate raw work IDs")
    manifest = {r["work_id"]: r for r in rows}
    require(len(manifest) == len(rows) and set(ids) == set(manifest), "Manifest/raw ID mismatch")
    require(Counter(r["stratum_id"] for r in rows) == Counter({s: n for s in expected}), "Incorrect strata")
    for w in works:
        m = manifest[w["id"]]
        field = ((w.get("primary_topic") or {}).get("field") or {}).get("id", "").split("/")[-1]
        require(w.get("publication_year") in config["years"] and field.isdigit() and int(field) in config["field_ids"], "Ineligible year/field")
        require(m["stratum_id"] == stratum(w["publication_year"], int(field)), "Stratum/raw mismatch")
        require(int(m["publication_year"]) == w["publication_year"] and int(m["field_id"]) == int(field), "Manifest year/field mismatch")
        require(w.get("language") == "en" and w.get("type") == "article" and w.get("is_xpac") is False, "Ineligible language/type/corpus")
        index = w.get("abstract_inverted_index")
        require(isinstance(index, dict) and bool(index), "Missing abstract index")
        require(all(isinstance(token, str) and isinstance(pos, list) and pos and all(type(p) is int and p >= 0 for p in pos) for token, pos in index.items()), "Malformed abstract index")
        population = int(m["population_count"])
        require(population >= n and int(m["seed"]) == config["seed"], "Invalid population/seed")
        require(abs(float(m["sampling_weight"]) - population / n) < 1e-8 and abs(float(m["inclusion_probability"]) - n / population) < 1e-12, "Invalid sample weights")
    for s in expected:
        require(len({r["population_count"] for r in rows if r["stratum_id"] == s}) == 1, "Inconsistent population counts")
    return manifest


def validate_tables(tables):
    for table, rows in tables.items():
        keys = [tuple(cell(row.get(k)) for k in KEYS[table]) for row in rows]
        require(all(all(k) for k in keys) and len(set(keys)) == len(keys), f"Invalid primary key: {table}")
    work_ids = {r["work_id"] for r in tables["works"]}
    for table, rows in tables.items():
        if "work_id" in SCHEMA[table]:
            require(all(r["work_id"] in work_ids for r in rows), f"Broken work FK: {table}")
    for table, col, target in (("authorships", "author_id", "authors"), ("affiliations", "institution_id", "institutions"),
                               ("works", "source_id", "sources"), ("locations", "source_id", "sources")):
        ids = {r[col] for r in tables[target]}
        require(all(not r.get(col) or r[col] in ids for r in tables[table]), f"Broken FK: {table}.{col}")
    authorships = {(r["work_id"], cell(r["authorship_index"])) for r in tables["authorships"]}
    require(all((r["work_id"], cell(r["authorship_index"])) in authorships for r in tables["affiliations"]), "Broken affiliation/authorship FK")
    require({r["work_id"] for r in tables["abstracts"]} == work_ids, "Missing abstracts")


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and p.name != "checksums.json"}


def seal(root):
    dump(root / "checksums.json", hashes(root))


def verify(root):
    require(json.loads((root / "checksums.json").read_text()) == hashes(root), "Snapshot checksum mismatch")


def sample(config_path, output, client=None):
    config = json.loads(Path(config_path).read_text())
    check_config(config)
    output = Path(output)
    require(not output.exists(), "Snapshot already exists; use a new version/path")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = output.with_name(output.name + ".partial")
    require(not stage.exists(), "Partial snapshot exists; inspect it before retrying")
    stage.mkdir()
    client = client or Client()
    works, manifest = [], []
    try:
        fields = client.get("fields", per_page=100)["results"]
        require({int(f["id"].split("/")[-1]) for f in fields} == set(config["field_ids"]), "Field taxonomy changed; review design")
        dump(stage / "fields.json", fields)
        for year in config["years"]:
            for field in config["field_ids"]:
                filters = f"language:en,type:article,has_abstract:true,publication_year:{year},primary_topic.field.id:{field}"
                params = dict(filter=filters, corpus="core")
                population = client.get("works", per_page=1, **params)["meta"]["count"]
                n = config["works_per_stratum"]
                require(population >= n, f"Undersized stratum {year}:{field}")
                response = client.get("works", sample=n, seed=config["seed"], per_page=n, **params)
                batch = response["results"]
                require(len(batch) == n, f"Incomplete stratum {year}:{field}")
                dump(stage / f"response-{year}-{field}.json", response)
                timestamp = datetime.now(timezone.utc).isoformat()
                for w in batch:
                    manifest.append(dict(work_id=w["id"], publication_year=year, field_id=field,
                        stratum_id=stratum(year, field), seed=config["seed"], population_count=population,
                        inclusion_probability=n / population, sampling_weight=population / n,
                        retrieved_at=timestamp, filter=filters, corpus="core"))
                works.extend(batch)
        validate_raw(works, manifest, config)
        dump(stage / "config.json", config)
        with (stage / "works.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for w in sorted(works, key=lambda w: w["id"]):
                stream.write(json.dumps(w, sort_keys=True, ensure_ascii=False) + "\n")
        write_csv(stage / "sample_manifest.csv", sorted(manifest, key=lambda r: r["work_id"]), list(manifest[0]))
        seal(stage)
        stage.rename(output)
    except Exception:
        # Keep partial responses for diagnosis; never call them a frozen release.
        raise


def load_snapshot(snapshot):
    snapshot = Path(snapshot)
    verify(snapshot)
    config = json.loads((snapshot / "config.json").read_text())
    with (snapshot / "works.jsonl").open(encoding="utf-8") as stream:
        works = [json.loads(line) for line in stream]
    rows = read_csv(snapshot / "sample_manifest.csv")
    return config, works, validate_raw(works, rows, config)


def build(snapshot, output):
    config, works, manifest = load_snapshot(snapshot)
    output = Path(output)
    require(not output.exists(), "Release already exists; use a new output path")
    tables = transform(works, manifest)
    validate_tables(tables)
    stage = output.with_name(output.name + ".partial")
    require(not stage.exists(), "Partial build exists; inspect before retrying")
    stage.mkdir(parents=True)
    for table, rows in tables.items():
        write_csv(stage / (table + ".csv"), rows, SCHEMA[table])
    shutil.copyfile(Path(snapshot) / "sample_manifest.csv", stage / "sample_manifest.csv")
    dump(stage / "schema.json", SCHEMA)
    dump(stage / "release.json", dict(dataset_version=config["dataset_version"], schema_version=config["schema_version"],
        builder_version=__version__, snapshot_checksums=json.loads((Path(snapshot) / "checksums.json").read_text()),
        table_rows={name: len(rows) for name, rows in tables.items()}))
    seal(stage)
    validate_release(snapshot, stage)
    stage.rename(output)


def validate_release(snapshot, output):
    config, works, manifest = load_snapshot(snapshot)
    output = Path(output)
    verify(output)
    expected = transform(works, manifest)
    actual = {table: read_csv(output / (table + ".csv")) for table in SCHEMA}
    validate_tables(actual)
    for table, rows in expected.items():
        require(actual[table] == [{key: cell(row.get(key)) for key in SCHEMA[table]} for row in rows],
                f"Release differs from frozen source: {table}")
    require((output / "sample_manifest.csv").read_bytes() == (Path(snapshot) / "sample_manifest.csv").read_bytes(), "Manifest mismatch")
    require(json.loads((output / "schema.json").read_text()) == SCHEMA, "Schema mismatch")
    release = json.loads((output / "release.json").read_text())
    require(release["dataset_version"] == config["dataset_version"] and release["schema_version"] == config["schema_version"], "Version mismatch")
    require(release["snapshot_checksums"] == json.loads((Path(snapshot) / "checksums.json").read_text()), "Provenance mismatch")
    require(release["table_rows"] == {t: len(r) for t, r in actual.items()}, "Row counts mismatch")
