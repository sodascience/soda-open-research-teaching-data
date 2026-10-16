"""Validated, self-contained archives and local Zenodo deposit materials."""
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from . import __version__
from .pipeline import dump, require, validate_release


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_files(root):
    """Explicit source allowlist: exclude environments, caches, data, and credentials."""
    root = Path(root)
    required = ['pyproject.toml', 'README.md', 'DATASET.md', 'LICENSE', 'LICENSE-DATA',
                'docs/CODEBOOK.md', 'src/soda_openalex/__init__.py']
    require(all((root / name).is_file() for name in required),
            'Packaging requires a source checkout with code, documentation, and licenses; use --source-root')
    files = {name: root / name for name in required}
    for folder, extensions in [('src', {'.py'}), ('tests', {'.py'}), ('config', {'.json'}),
                               ('docs', {'.md', '.txt', '.py'}), ('examples', {'.py', '.R'}),
                               ('.github/workflows', {'.yml', '.yaml'})]:
        for path in (root / folder).rglob('*'):
            if path.is_file() and not path.is_symlink() and path.suffix in extensions and '__pycache__' not in path.parts:
                files[path.relative_to(root).as_posix()] = path
    if (root / 'uv.lock').is_file():
        files['uv.lock'] = root / 'uv.lock'
    require(not any(path.is_symlink() for path in files.values()), 'Source archive cannot contain symlinks')
    return files


def find_source_root(explicit=None):
    if explicit:
        return Path(explicit).resolve()
    for root in (Path.cwd(), Path(__file__).resolve().parents[2]):
        if (root / 'pyproject.toml').is_file() and (root / 'docs/CODEBOOK.md').is_file():
            return root
    raise ValueError('Source checkout not found; use --source-root')


def git_revision(root):
    # Only the revision, never remote URLs, configuration, or environment values.
    try:
        result = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                capture_output=True, text=True, timeout=5, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


VERIFY_SCRIPT = '''"""Verify all original archive payload files with the Python standard library."""
import hashlib
import json
from pathlib import Path
root = Path(__file__).resolve().parent
manifest = json.loads((root / "archive_checksums.json").read_text(encoding="utf-8"))
for name, expected in manifest.items():
    path = root / name
    if not path.is_file():
        raise SystemExit("Missing file: " + name)
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise SystemExit("Integrity check failed: " + name)
print(f"Verified {len(manifest)} archive payload files.")
'''

COMPARE_SCRIPT = '''"""Compare rebuilt tables and schema with the original teaching release."""
import hashlib
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parent
rebuilt = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "rebuilt-release"
expected = json.loads((root / "expected-release/checksums.json").read_text(encoding="utf-8"))
for name, checksum in expected.items():
    # Builder provenance may change when rebuilding with a newer packaged builder.
    if name == "release.json":
        continue
    path = rebuilt / name
    if not path.is_file():
        raise SystemExit("Missing rebuilt file: " + name)
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != checksum:
        raise SystemExit("Rebuilt data differs: " + name)
print("Rebuilt tables, sample manifest, and schema match the original release.")
'''


def write_archive(output, root_name, files, text_files):
    """Stable ordering/timestamps; verify each archived byte before finalization."""
    checksums = {}
    payload = {**files, **{name: text.encode('utf-8') for name, text in text_files.items()}}
    require(len(payload) == len(files) + len(text_files), 'Duplicate archive paths')
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, value in sorted(payload.items()):
            info = zipfile.ZipInfo(root_name + '/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with archive.open(info, 'w', force_zip64=True) as target:
                if isinstance(value, bytes):
                    target.write(value)
                    checksums[name] = hashlib.sha256(value).hexdigest()
                else:
                    checksums[name] = digest(value)
                    with value.open('rb') as source:
                        shutil.copyfileobj(source, target)
        info = zipfile.ZipInfo(root_name + '/archive_checksums.json', date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, json.dumps(checksums, sort_keys=True, indent=2) + '\n')
    with zipfile.ZipFile(output) as archive:
        require(len(archive.namelist()) == len(checksums) + 1, 'Unexpected archive entries')
        for name, expected in checksums.items():
            with archive.open(root_name + '/' + name) as stream:
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == expected,
                        'Archive verification failed: ' + name)
    return len(checksums)


def package_release(snapshot, release, output, source_root=None):
    """Create a NEW local deposit bundle; never upload, publish, or overwrite."""
    snapshot, release, output = (Path(p).resolve() for p in (snapshot, release, output))
    require(not output.exists(), 'Package directory already exists; choose a new output path')
    stage = output.with_name(output.name + '.partial')
    require(not stage.exists(), 'Partial package exists; inspect before retrying')
    require(not any(output.is_relative_to(p) or stage.is_relative_to(p) for p in (snapshot, release)),
            'Package output cannot be inside the frozen snapshot or release')
    source_root = find_source_root(source_root)
    sources = source_files(source_root)
    # Validate before creating ZIPs, including exact agreement with the frozen raw data.
    validate_release(snapshot, release)
    metadata = json.loads((release / 'release.json').read_text(encoding='utf-8'))
    config = json.loads((snapshot / 'config.json').read_text(encoding='utf-8'))
    version = metadata['dataset_version']
    require(isinstance(version, str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', version)),
            'Dataset version must be a safe filename component')
    source_hashes = {name: digest(path) for name, path in sorted(sources.items())}
    provenance = dict(packager_version=__version__, original_builder_version=metadata['builder_version'],
                      source_revision=git_revision(source_root), source_sha256=source_hashes,
                      note='Exact packaged source hashes identify the code; the Git revision may omit uncommitted changes.')
    stage.mkdir(parents=True)
    teaching_name = f'soda-openalex-teaching-{version}'
    repro_name = f'soda-openalex-reproducibility-{version}'
    shared = {name: source_root / name for name in ('DATASET.md', 'LICENSE', 'LICENSE-DATA', 'docs/CODEBOOK.md')}
    teaching_files = {f'data/releases/{version}/' + p.relative_to(release).as_posix(): p
                      for p in release.rglob('*') if p.is_file()}
    teaching_files.update(shared)
    teaching_files.update({name: path for name, path in sources.items() if name.startswith('examples/')})
    sampling_notes = f'''# Sampling specification for dataset {version}

This file describes this packaged release; the full frozen config is in the
reproducibility archive at snapshot/config.json.

- Dataset version: {version}
- Schema version: {metadata['schema_version']}
- Original builder version: {metadata['builder_version']}
- Packager version: {__version__}
- Corpus: {config['corpus']}
- Metadata language: {config['language']}
- Work type: {config['type']}
- Abstract required: {str(config['has_abstract']).lower()}
- Publication years: {', '.join(str(y) for y in config['years'])}
- Primary OpenAlex field IDs: {', '.join(str(f) for f in config['field_ids'])}
- Works per year × primary-field stratum: {config['works_per_stratum']}
- Number of strata: {len(config['years']) * len(config['field_ids'])}
- Validated works: {metadata['table_rows']['works']}
- Seed used for each stratum: {config['seed']}

For each stratum with recorded eligible population N and sample size n,
nominal inclusion probability is n/N and sampling weight is N/n. Values and
retrieval times are recorded per work in sample_manifest.csv. Population counts
and sample queries are adjacent API calls, not an atomic database snapshot.
Fields are assigned through the work's primary topic; secondary topics do not
create additional sampling memberships. The raw field taxonomy is frozen in
snapshot/fields.json in the reproducibility archive.

DATASET.md in the teaching ZIP and code/DATASET.md in the reproducibility ZIP
preserve the project's initial v1 specification and general interpretation notes.
For this release's actual sampling parameters, use this file and the frozen
configuration, which may differ from the initial v1 design.
'''
    teaching_readme = f'''# SoDa OpenAlex teaching dataset {version}

This release contains {metadata['table_rows']['works']:,} sampled works in {len(metadata['table_rows'])} relational CSV tables.
The CSV files and original release checksums are in data/releases/{version}/.
Start with works.csv; join tables using docs/CODEBOOK.md. SAMPLING.md describes
this release’s actual sampling parameters. DATASET.md preserves the initial
v1 specification and general interpretation, limitations, and versioning notes.

Verify the extracted archive with Python 3.11+: python3 verify_archive.py
For Python: python3 examples/load_data.py --data data/releases/{version}/ (from this extracted directory).
For R: Rscript examples/load_data.R data/releases/{version}/ (from this extracted directory).
Other tools can read the UTF-8 CSV files directly. Nested values are JSON cells.
No OpenAlex API key is needed. Abstracts remain inverted indexes.

Dataset contributions: CC0 1.0 (LICENSE-DATA). Example code: MIT (LICENSE).
Linked publications and full text are not included or licensed by this archive.
See CITATION.md for citation guidance. The accompanying reproducibility archive
contains the raw snapshot and Python source for rebuilding these tables.
'''
    citation = f'''# Citation guidance

Dataset: SoDa OpenAlex teaching dataset, version {version}.
Cite the version-specific Zenodo DOI and the creators listed on that record once
published. The stable concept DOI represents all versions and is suitable for a
project-level link; use the version-specific DOI for the data actually analysed.
Both ZIPs share one versioned Zenodo record and its DOI. No DOI or creator names
have been invented for this local bundle.
Schema version: {metadata['schema_version']}.
Source data: OpenAlex (https://openalex.org/); dataset contributions: CC0 1.0.
'''
    teaching_count = write_archive(stage / (teaching_name + '.zip'), teaching_name, teaching_files,
        {'README.md': teaching_readme, 'verify_archive.py': VERIFY_SCRIPT, 'CITATION.md': citation, 'SAMPLING.md': sampling_notes})
    repro_files = {'snapshot/' + p.relative_to(snapshot).as_posix(): p
                   for p in snapshot.rglob('*') if p.is_file()}
    repro_files.update({'code/' + name: path for name, path in sources.items()})
    repro_files.update({'expected-release/' + name: release / name
                        for name in ('checksums.json', 'release.json', 'schema.json')})
    repro_readme = f'''# SoDa OpenAlex reproducibility snapshot {version}

snapshot/ contains the frozen works.jsonl, sample manifest, configuration,
field taxonomy, API sample responses, and original snapshot checksums.
SAMPLING.md describes this release’s actual sampling parameters.
code/ contains the exact source, tests, documentation, and licenses packaged
with this bundle. expected-release/ records the original schema, row counts,
and file checksums. The original CSV tables are in the separate teaching ZIP.

With Python 3.11+ (standard library only), from this extracted directory:

    python3 verify_archive.py
    PYTHONPATH=code/src python3 -m soda_openalex.cli build --snapshot snapshot --output rebuilt-release --no-package
    PYTHONPATH=code/src python3 -m soda_openalex.cli validate --snapshot snapshot --output rebuilt-release
    python3 compare_release.py rebuilt-release

The PYTHONPATH syntax above is for macOS/Linux shells. No OpenAlex connection,
API key, or dependency installation is needed. Use a new output folder.
Comparison checks the tables, manifest, and schema byte for byte. release.json
is excluded from that comparison because its builder-version provenance may
change: the original builder was {metadata['builder_version']}, while this bundle's
packager/builder version is {__version__}. Original provenance is retained.

Dataset contributions: CC0 1.0 (code/LICENSE-DATA); software: MIT (code/LICENSE).
Abstracts remain inverted indexes; no plaintext abstracts or full text are added.
See source_provenance.json for exact source hashes and CITATION.md for citation.
'''
    repro_count = write_archive(stage / (repro_name + '.zip'), repro_name, repro_files,
        {'README.md': repro_readme, 'verify_archive.py': VERIFY_SCRIPT, 'compare_release.py': COMPARE_SCRIPT,
         'CITATION.md': citation, 'SAMPLING.md': sampling_notes, 'source_provenance.json': json.dumps(provenance, sort_keys=True, indent=2) + '\n'})
    dump(stage / 'release_report.json', dict(dataset_version=version, schema_version=metadata['schema_version'],
         original_builder_version=metadata['builder_version'], packager_version=__version__,
         validation='passed', config=config, table_rows=metadata['table_rows'],
         archive_payload_files={teaching_name + '.zip': teaching_count, repro_name + '.zip': repro_count},
         source_provenance=provenance))
    dump(stage / 'zenodo-metadata-draft.json', dict(
        title=f'SoDa OpenAlex teaching dataset {version}', version=version, resource_type='dataset',
        description=f'OpenAlex-derived teaching dataset with {metadata["table_rows"]["works"]:,} works, '
                    f'{len(config["years"])} publication years and {len(config["field_ids"])} primary fields. '
                    'Includes relational teaching tables and a frozen reproducibility snapshot.',
        licenses=[dict(id='CC0-1.0', scope='dataset contributions'), dict(id='MIT', scope='software')],
        keywords=['OpenAlex', 'teaching', 'research methods', 'reproducibility'],
        creators=[], publication_date=None, doi=None, concept_doi=None,
        status='Local metadata worksheet, not an API payload; complete creators and publication details in Zenodo.'))
    (stage / 'CITATION.md').write_text(citation, encoding='utf-8', newline='\n')
    (stage / 'ZENODO.md').write_text(f'''# Zenodo deposit materials — dataset {version}

Upload both ZIPs, SHA256SUMS, release_report.json, and CITATION.md to the same
versioned dataset record. The teaching ZIP serves users; the reproducibility ZIP
serves auditing and rebuilding. Each ZIP includes its own SHA-256 payload manifest,
verification script, README, documentation, and license information.

zenodo-metadata-draft.json is a worksheet for the deposit form, not an API payload.
Complete the actual creators/affiliations and publication date. Reserve a DOI in
Zenodo if desired, then cite the published version-specific DOI. Review the title,
description, dataset resource type, and both licenses (CC0 data; MIT software).
Do not present the source-code license as CC0. No upload or publication is automatic.

Verify these files against SHA256SUMS before uploading. ZIP payload verification:
extract either ZIP, enter its top-level directory, and run python3 verify_archive.py.
Only finalize/publish the deposit after reviewing its files and metadata.

For an updated dataset, use New version on the existing Zenodo record: each
published version receives a distinct version DOI and shares the stable concept
DOI. Both ZIPs belong to the same record/version. Cite the version DOI for an
analysis and use the concept DOI for the project link. Metadata-only edits do not
require a new record version. A software-only change does not require publishing
new dataset files. Repackaging locally does not update an existing Zenodo record.
If you publish changed archive files, use Zenodo's versioning workflow rather
than replacing a previously cited dataset release.

Zenodo documentation: https://help.zenodo.org/docs/deposit/
Mixed licenses: https://help.zenodo.org/docs/deposit/describe-records/licenses/
DOI versioning: https://zenodo.org/help/versioning
''', encoding='utf-8', newline='\n')
    sums = ''.join(f'{digest(path)}  {path.name}\n' for path in sorted(stage.iterdir()) if path.is_file())
    (stage / 'SHA256SUMS').write_text(sums, encoding='utf-8', newline='\n')
    stage.rename(output)
    return output
