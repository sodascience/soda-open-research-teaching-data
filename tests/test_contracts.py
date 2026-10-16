"""Checks for documentation, version, configuration, and schema drift."""
import json
import os
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

from soda_openalex import __version__
from soda_openalex.api import MAX_PER_PAGE
from soda_openalex.pipeline import check_config
from soda_openalex.schema import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_software_and_config_versions_match_their_contracts(self):
        project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
        self.assertEqual(project['project']['version'], __version__)
        for path in (ROOT / 'config').glob('*.json'):
            config = json.loads(path.read_text())
            self.assertEqual(config['schema_version'], SCHEMA_VERSION)
            check_config(config)

    def test_codebook_is_current(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, 'docs/generate_codebook.py', '--check'], cwd=ROOT,
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_single_page_sampling_limit(self):
        config = json.loads((ROOT / 'config/v1.json').read_text())
        check_config(dict(config, works_per_stratum=MAX_PER_PAGE))
        for invalid in (0, MAX_PER_PAGE + 1, 1.5, True):
            with self.subTest(size=invalid), self.assertRaisesRegex(ValueError, 'Stratum size'):
                check_config(dict(config, works_per_stratum=invalid))

    def test_unknown_schema_version_is_rejected(self):
        config = json.loads((ROOT / 'config/v1.json').read_text())
        with self.assertRaisesRegex(ValueError, 'Unsupported schema version'):
            check_config(dict(config, schema_version='99.0.0'))


if __name__ == '__main__':
    unittest.main()
