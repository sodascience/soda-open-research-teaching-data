"""Offline deposit workflow and extracted-archive tests."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from soda_openalex import __version__
from soda_openalex.cli import main, sample_pipeline
from soda_openalex.package import package_release
from soda_openalex.pipeline import sample, build
from test_pipeline import CONFIG, FakeClient

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config.json'
        self.config.write_text(json.dumps(CONFIG))
        self.snapshot = self.root / 'data/raw/test'
        self.release = self.root / 'data/releases/test'
        sample(self.config, self.snapshot, FakeClient())
        build(self.snapshot, self.release)

    def test_archives_extract_verify_and_rebuild_offline(self):
        output = self.root / 'deposit'
        with patch('soda_openalex.api.Client.get', side_effect=AssertionError('Network forbidden')):
            package_release(self.snapshot, self.release, output, ROOT)
        sums = (output / 'SHA256SUMS').read_text().splitlines()
        for line in sums:
            expected, filename = line.split('  ', 1)
            self.assertEqual(hashlib.sha256((output / filename).read_bytes()).hexdigest(), expected)
        teaching = self.root / 'teaching'
        repro = self.root / 'repro'
        for name, target in [('teaching', teaching), ('reproducibility', repro)]:
            with zipfile.ZipFile(output / f'soda-openalex-{name}-test.zip') as archive:
                self.assertFalse(any('.env' in p or '__pycache__' in p or '.git/' in p for p in archive.namelist()))
                archive.extractall(target)
            unpacked = next(target.iterdir())
            result = subprocess.run([sys.executable, 'verify_archive.py'], cwd=unpacked,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        teach_root = next(teaching.iterdir())
        result = subprocess.run([sys.executable, 'examples/load_data.py', '--data', 'data/releases/test'],
                                cwd=teach_root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Loaded 1 works', result.stdout)
        repro_root = next(repro.iterdir())
        env = dict(os.environ, PYTHONPATH=str(repro_root / 'code/src'), PYTHONDONTWRITEBYTECODE='1')
        for command in ('build', 'validate'):
            args = [sys.executable, '-m', 'soda_openalex.cli', command,
                    '--snapshot', 'snapshot', '--output', 'rebuilt-release']
            if command == 'build':
                args.append('--no-package')
            result = subprocess.run(args, cwd=repro_root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, 'compare_release.py', 'rebuilt-release'], cwd=repro_root,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads((output / 'zenodo-metadata-draft.json').read_text())
        self.assertEqual(metadata['creators'], [])
        self.assertIsNone(metadata['doi'])
        self.assertIsNone(metadata['concept_doi'])
        sampling = (teach_root / 'SAMPLING.md').read_text()
        self.assertIn('Works per year × primary-field stratum: 1', sampling)
        self.assertIn('Validated works: 1', sampling)
        self.assertIn('concept DOI', (teach_root / 'CITATION.md').read_text())
        self.assertEqual(json.loads((output / 'release_report.json').read_text())['packager_version'], __version__)
        # Archived verifier detects a payload that was modified after extraction.
        (teach_root / 'data/releases/test/works.csv').write_text('changed')
        result = subprocess.run([sys.executable, 'verify_archive.py'], cwd=teach_root, capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_deterministic_archives_and_no_overwrite(self):
        a, b = self.root / 'a', self.root / 'b'
        package_release(self.snapshot, self.release, a, ROOT)
        package_release(self.snapshot, self.release, b, ROOT)
        for path in a.iterdir():
            self.assertEqual(path.read_bytes(), (b / path.name).read_bytes(), path.name)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            package_release(self.snapshot, self.release, a, ROOT)

    def test_corrupt_release_creates_no_final_bundle(self):
        (self.release / 'works.csv').write_text('corrupted')
        output = self.root / 'deposit'
        with self.assertRaisesRegex(ValueError, 'checksum'):
            package_release(self.snapshot, self.release, output, ROOT)
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name(output.name + '.partial').exists())

    def test_complete_sampling_pipeline_creates_both_zips(self):
        raw = self.root / 'new/raw/test'
        with patch('soda_openalex.api.Client.get', side_effect=AssertionError('Network forbidden')):
            release, packages = sample_pipeline(self.config, raw, source_root=ROOT, client=FakeClient())
        self.assertTrue((release / 'works.csv').exists())
        self.assertEqual(len(list(packages.glob('*.zip'))), 2)
        with patch('soda_openalex.cli.sample', side_effect=AssertionError('Must preflight before downloading')):
            with self.assertRaisesRegex(ValueError, 'already exists'):
                sample_pipeline(self.config, raw, source_root=ROOT, client=FakeClient())

    def test_build_cli_auto_packages_and_no_package_opt_out(self):
        release = self.root / 'auto/release'
        packages = self.root / 'auto/packages'
        args = ['soda-openalex', 'build', '--snapshot', str(self.snapshot), '--output', str(release),
                '--package-output', str(packages), '--source-root', str(ROOT)]
        with patch.object(sys, 'argv', args):
            main()
        self.assertEqual(len(list(packages.glob('*.zip'))), 2)
        args = ['soda-openalex', 'build', '--snapshot', str(self.snapshot), '--output', str(self.root / 'plain'), '--no-package']
        with patch.object(sys, 'argv', args):
            main()
        self.assertTrue((self.root / 'plain/works.csv').exists())

    def test_failed_packaging_keeps_partial_not_final(self):
        output = self.root / 'deposit'
        with patch('soda_openalex.package.write_archive', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                package_release(self.snapshot, self.release, output, ROOT)
        self.assertFalse(output.exists())
        self.assertTrue(output.with_name(output.name + '.partial').exists())

    def test_packages_cannot_modify_frozen_inputs(self):
        with self.assertRaisesRegex(ValueError, 'cannot be inside'):
            package_release(self.snapshot, self.release, self.snapshot / 'packages', ROOT)


if __name__ == '__main__':
    unittest.main()
