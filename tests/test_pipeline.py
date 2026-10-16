import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from soda_openalex.api import Client
from soda_openalex.pipeline import sample, build, validate_release, load_snapshot, seal
from soda_openalex.transform import transform
from soda_openalex.pipeline import validate_tables


CONFIG = dict(dataset_version="test", schema_version="1.0.0", seed=20261016, years=[2011],
              field_ids=[11], works_per_stratum=1, corpus="core", language="en", type="article", has_abstract=True)
WORK = dict(id="https://openalex.org/W1", publication_year=2011, language="en", type="article", is_xpac=False,
    title="A title with Unicode separators \u2028 and \u0085",
    abstract_inverted_index={"Example": [0]}, primary_topic=dict(id="https://openalex.org/T1",
    field=dict(id="https://openalex.org/fields/11", display_name="Field")),
    authorships=[dict(author=dict(id="https://openalex.org/A1", display_name="Author"),
        institutions=[dict(id="https://openalex.org/I1")], countries=["NL"])],
    locations=[dict(source=dict(id="https://openalex.org/S1"), is_oa=True)],
    referenced_works=["https://openalex.org/W999"], funders=[dict(id="https://openalex.org/F1")],
    awards=[dict(id="https://openalex.org/G1", funder_id="https://openalex.org/F1")],
    counts_by_year=[dict(year=2025, cited_by_count=2)])


class FakeClient:
    def get(self, endpoint, **params):
        if endpoint == "fields":
            return dict(results=[dict(id="https://openalex.org/fields/11")])
        if "sample" not in params:
            return dict(meta=dict(count=100))
        return dict(meta=dict(count=1), results=[copy.deepcopy(WORK)])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps(CONFIG))
        self.snapshot = self.root / "snapshot"
        sample(self.config, self.snapshot, FakeClient())

    def test_offline_roundtrip_and_determinism(self):
        a, b = self.root / "a", self.root / "b"
        with patch.object(Client, "get", side_effect=AssertionError("Network forbidden")):
            build(self.snapshot, a)
            build(self.snapshot, b)
            validate_release(self.snapshot, a)
        self.assertEqual((a / "checksums.json").read_bytes(), (b / "checksums.json").read_bytes())
        self.assertIn('"Example"', (self.snapshot / "works.jsonl").read_text())
        with self.assertRaises(ValueError):
            sample(self.config, self.snapshot, FakeClient())

    def test_tampering_detected(self):
        (self.snapshot / "works.jsonl").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            load_snapshot(self.snapshot)

    def test_wrong_stratum_and_missing_abstract(self):
        for key, value in (("publication_year", 2020), ("abstract_inverted_index", None), ("is_xpac", True)):
            with self.subTest(key=key):
                works = [dict(WORK, **{key: value})]
                from soda_openalex.pipeline import validate_raw, read_csv
                with self.assertRaises(ValueError):
                    validate_raw(works, read_csv(self.snapshot / "sample_manifest.csv"), CONFIG)

    def test_duplicate_and_relational_integrity(self):
        config, works, manifest = load_snapshot(self.snapshot)
        tables = transform(works, manifest)
        tables["affiliations"][0]["authorship_index"] = 999
        with self.assertRaisesRegex(ValueError, "authorship FK"):
            validate_tables(tables)
        tables = transform(works, manifest)
        tables["works"].append(tables["works"][0])
        with self.assertRaisesRegex(ValueError, "primary key"):
            validate_tables(tables)

    def test_resealed_incorrect_output_rejected(self):
        output = self.root / "release"
        build(self.snapshot, output)
        p = output / "works.csv"
        p.write_text(p.read_text().replace("2011", "2012"))
        seal(output)
        with self.assertRaisesRegex(ValueError, "differs"):
            validate_release(self.snapshot, output)

    def test_retry_and_secret_redaction(self):
        client = Client(retries=1, interval=0)
        client.key = "super-secret"
        error = HTTPError("https://example.org/?api_key=super-secret", 429, "rate", {}, None)
        with patch("soda_openalex.api.urlopen", side_effect=error), patch("soda_openalex.api.time.sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                client.get("works")
        self.assertNotIn("super-secret", str(ctx.exception))

    def test_full_agreed_sample_design(self):
        from soda_openalex.pipeline import validate_raw
        config = json.loads(Path("config/v1.json").read_text())
        works, rows = [], []
        for year in config["years"]:
            for field in config["field_ids"]:
                for i in range(config["works_per_stratum"]):
                    wid = f"https://openalex.org/W{year}{field}{i:02d}"
                    works.append(dict(id=wid, publication_year=year, language="en", type="article",
                        is_xpac=False, abstract_inverted_index={"Test": [0]},
                        primary_topic={"field": {"id": f"https://openalex.org/fields/{field}"}}))
                    rows.append(dict(work_id=wid, publication_year=year, field_id=field,
                        stratum_id=f"{year}:{field}", seed=config["seed"], population_count=300,
                        inclusion_probability=.1, sampling_weight=10))
        self.assertEqual(len(validate_raw(works, rows, config)), 11700)
        rows[0]["stratum_id"] = rows[-1]["stratum_id"]
        with self.assertRaisesRegex(ValueError, "strata"):
            validate_raw(works, rows, config)

    def test_batch_fetch_and_incomplete_batch(self):
        client = Client()
        ids = [f"https://openalex.org/W{i}" for i in range(101)]
        def fake(endpoint, **params):
            return dict(results=[dict(id=i) for i in params["filter"].removeprefix("openalex:").split("|")])
        with patch.object(client, "get", side_effect=fake) as calls:
            self.assertEqual(len(client.works_by_ids(ids)), 101)
            self.assertEqual(calls.call_count, 2)
        with patch.object(client, "get", return_value=dict(results=[])):
            with self.assertRaises(ValueError):
                client.works_by_ids(ids)


if __name__ == "__main__":
    unittest.main()
