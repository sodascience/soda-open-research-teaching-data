"""Read a downloaded or built teaching release; --data selects its CSV directory."""
import argparse
import csv
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--data", type=Path, default=Path("data/releases/1.0.0"))
root = parser.parse_args().data
with (root / "works.csv").open(encoding="utf-8", newline="") as stream:
    works = list(csv.DictReader(stream))
with (root / "abstracts.csv").open(encoding="utf-8", newline="") as stream:
    abstracts = {row["work_id"]: json.loads(row["abstract_inverted_index"]) for row in csv.DictReader(stream)}
print(f"Loaded {len(works)} works and {len(abstracts)} abstract indexes")
