# SoDa Open Research Teaching Datasets (SORTD)

Versioned, reusable OpenAlex-derived datasets for teaching research methods, data analysis, and AI-assisted research workflows.

## Use a downloaded dataset

Download the versioned teaching release and use it directly; you do not need to run the build pipeline or access the OpenAlex API.

The teaching release contains 16 UTF-8 CSV tables, `sample_manifest.csv`, schema information, and checksums. Start with `works.csv`, then join the other tables using the keys in the [codebook](docs/CODEBOOK.md). Abstracts are JSON inverted indexes, not plaintext.

```text
data/releases/1.0.0/
├── works.csv
├── abstracts.csv
├── authors.csv
├── authorships.csv
├── ...
├── sample_manifest.csv
├── schema.json
├── release.json
└── checksums.json
```

**Download status:** version 1.0.0 was generated locally on 2026-10-16, with 11,700 works across all 390 strata. A public download has not yet been published. Cloning this repository does not download the data: `data/` is excluded from Git.

Extract the teaching ZIP and enter its top-level folder. Its `data/releases/1.0.0/` directory contains the CSV files. The included examples use only the Python standard library or base R:

```sh
python3 examples/load_data.py --data data/releases/1.0.0
Rscript examples/load_data.R data/releases/1.0.0
```

You can run either example, depending on the language you use. For other releases, replace the data directory with the extracted version's path. The same [Python loader](examples/load_data.py) and [R loader](examples/load_data.R) work from the cloned repository root when its data directory is populated. uv is only needed for the source-checkout development workflow below; it is not required to read the CSVs.

## Rebuild or sample a new dataset

### Python environment with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run these commands from the cloned repository root. The project requires Python 3.11 or newer and has no runtime dependencies.

```sh
uv sync
uv run soda-openalex --help
```

`uv sync` creates the local `.venv`, installs the project, and creates or updates `uv.lock`. `uv run` uses that environment without manual activation.

### Rebuild from the frozen snapshot

Each teaching release is accompanied by a separate reproducibility snapshot for rebuilding or auditing purposes. Place the raw snapshot contents under `data/raw/<version>/`, including `works.jsonl`, `sample_manifest.csv`, `config.json`, `fields.json`, the API response files, and `checksums.json`.

Build into a new output folder, then validate it:

```sh
uv run soda-openalex build --snapshot data/raw/1.0.0 --output data/rebuilt/1.0.0 --no-package
uv run soda-openalex validate --snapshot data/raw/1.0.0 --output data/rebuilt/1.0.0
```

Complete the uv setup before working offline. The build and validation use only local snapshot files: no API key or OpenAlex connection is needed. Existing output folders cannot be overwritten. `--no-package` is useful for reviewing a rebuild without generating new ZIPs. Table, manifest, and schema checksums should match the original release. `release.json` records the builder used, so its checksum can differ when rebuilding with a newer builder.

### Download a new sample from OpenAlex

The command below creates the initial snapshot only if that folder does not already exist:

```sh
uv run soda-openalex sample --config config/v1.json --output data/raw/1.0.0
```

This now runs the complete local workflow: freeze the raw sample, build and validate the CSV tables, then create both ZIP archives and the Zenodo deposit materials. With the initial config, the outputs are `data/raw/1.0.0/`, `data/releases/1.0.0/`, and `data/zenodo/1.0.0/`. Each directory must be new. For later datasets, create a new versioned config with its own `dataset_version` and choose a new raw snapshot path.

Only do this when intentionally creating a new snapshot. Repeating an API request with the same seed can still return different records because the OpenAlex database changes. Use `--snapshot-only` to stop after freezing raw data. `--release-output`, `--package-output`, and `--source-root` let you override the default locations.

The initial config makes 781 API requests before any retries: one taxonomy request plus two requests for each of its 390 strata. The implementation uses one page per stratum, so `works_per_stratum` must be an integer from 1 to 100; this is the current API page limit, not its larger total sampling limit. See [OpenAlex API limits](https://help.openalex.org/api/authentication/). Sampling can take several minutes. Requests use bounded retries for network errors, HTTP 429, and server failures, honoring Retry-After. No full text is downloaded. API quotas may interrupt a run.

#### Optional API key

An OpenAlex API key is **optional for this sampling pipeline**. Without one, requests use OpenAlex's smaller anonymous allowance. A free key provides a larger allowance and higher request limits; see [OpenAlex authentication](https://help.openalex.org/api/authentication/). The initial 11,700-work snapshot was downloaded successfully without a key.

If you have a key, set it in your shell before sampling:

```sh
export OPENALEX_API_KEY="your-key"
```

The client reads this environment variable automatically. Keep keys out of committed files; `.env` files are ignored by Git, but this pipeline does not automatically load them.


## Automatic Zenodo packaging

A successful `sample` command now creates the teaching release and its deposit files automatically. `build` also packages its validated output by default; use `--no-package` when you only want rebuilt tables. Packaging runs locally and does not upload or publish anything.

For the existing dataset, create the deposit files without downloading or rebuilding:

```sh
uv run soda-openalex package --snapshot data/raw/1.0.0 --release data/releases/1.0.0 --output data/zenodo/1.0.0
```

If that package directory already exists, inspect it or choose another output path. Snapshot, release, and package outputs must be separate directories. The default package path for `sample` or `build` is `data/zenodo/<dataset_version>/`. If building from a snapshot outside `data/raw/`, defaults are relative to the snapshot's parent directory. Use `--package-output` to choose explicitly.

```text
data/zenodo/1.0.0/
├── soda-openalex-teaching-1.0.0.zip
├── soda-openalex-reproducibility-1.0.0.zip
├── SHA256SUMS
├── release_report.json
├── zenodo-metadata-draft.json
├── CITATION.md
└── ZENODO.md
```

- **Teaching ZIP:** all 16 CSV tables and original release metadata under `data/releases/<version>/`, plus documentation, licenses, example loaders, a release-specific `SAMPLING.md`, and an archive verification script.
- **Reproducibility ZIP:** frozen raw snapshot, exact packaged source, tests, documentation, licenses, original release checksums, a release-specific `SAMPLING.md`, offline rebuild instructions, and a script that compares rebuilt tables with the original release. Original CSV files are not duplicated in this archive.
- **SHA256SUMS:** hashes of the two ZIPs and accompanying files. Each ZIP also contains a payload checksum manifest and `verify_archive.py`.
- **release_report.json:** successful validation, actual row counts, configuration, software versions, and source hashes. A Git revision is recorded when available; exact source hashes also capture uncommitted files.
- **zenodo-metadata-draft.json, CITATION.md, ZENODO.md:** a metadata worksheet, citation guidance, and upload instructions. Complete the actual creators, publication date, and DOI in Zenodo. The worksheet is not a ready-to-submit API payload. Declare CC0 for dataset contributions and MIT for included software; no creator names or DOI are invented.

Inputs are validated before packaging. ZIP entries use stable ordering and timestamps, and archived bytes are checked before the final package directory appears. Existing bundles cannot be overwritten. Failed packaging may leave a `.partial` directory for inspection; the validated snapshot and CSV release remain available. After fixing the failure, use `package` on those existing inputs rather than rerunning `sample`.

Run packaging from the source checkout. If the command cannot find the codebook or licenses, pass `--source-root /path/to/repository`; these resources are required for self-contained archives. Source files are selected explicitly so `.env`, Git internals, local environments, and caches are excluded.

After extracting either ZIP, enter its top-level folder and run `python3 verify_archive.py`. The reproducibility README includes offline rebuilding and comparison commands. The comparison checks table, manifest, and schema bytes; builder provenance in `release.json` may differ when an older dataset is packaged with newer software.

Upload both ZIPs to the **same versioned Zenodo record**, with the accompanying checksums, report, and citation guidance described in `ZENODO.md`. Each new published record version receives a version-specific DOI and shares a stable concept DOI with the other versions. Use the concept DOI for a project-level README link and the version-specific DOI when citing data used in an analysis. Use **New version** on the existing record for updated data files; metadata-only edits do not need a new version. See [Zenodo DOI versioning](https://zenodo.org/help/versioning).

Software-only changes do not require a new dataset publication. If you choose to publish changed archive files, use Zenodo's versioning workflow. Generating a new local bundle does not update Zenodo. Existing ZIPs are frozen source snapshots and can legitimately contain older documentation; generate a new local package directory to include current code and docs. Keep generated deposit materials out of Git with the rest of `data/`.

## Design and reproducibility

English articles in the OpenAlex core, 2011–2025 inclusive, with abstracts: 30 works for every publication year × primary field, across 26 fields. Total: 390 strata and 11,700 works; seed 20261016. See [DATASET.md](DATASET.md) and [codebook](docs/CODEBOOK.md).

`sample` first creates a new, immutable snapshot containing full API responses, raw `works.jsonl`, `sample_manifest.csv`, taxonomy, configuration, and SHA-256 checksums. Table building and validation use only these frozen data files; packaging additionally reads the source checkout and documentation. A seed alone does not reproduce a changing API. Re-fetching frozen IDs also changes metadata; publish it as a new version, never as a replacement snapshot. The client includes a batched ID retrieval helper for an explicit future refresh workflow.

CSV tables live in `data/releases/<version>/`; nested values are JSON cells. Each build contains `schema.json`, row counts, checksums, and snapshot provenance. Empty tables still have headers. Existing snapshots/releases cannot be overwritten. Builds validate before the final directory rename.

## Structure

- `config/v1.json`: initial versioned sampling design and dataset/schema versions; config filenames need not equal dataset version numbers.
- `src/soda_openalex/`: API client, sampling, transformation, validation, CLI.
- `tests/`: offline integration, failure, reproducibility, and client tests.
- `examples/`: minimal Python and R consumers; no R build pipeline.
- `data/raw/`, `data/releases/`, `data/zenodo/`: frozen records, derived tables, and generated deposit bundles; excluded from Git.

## Development

Run the offline tests from the repository root:

```sh
uv run python -m unittest discover -s tests -v
uv run python docs/generate_codebook.py --check
```

CI also uses uv to set up the project and run these offline tests. To update the codebook after changing its schema or descriptions, run `uv run python docs/generate_codebook.py`; `--check` verifies that the generated document is current.

### Software, dataset, and schema versions

These versions identify different things and do not need to match:

| Version | What it identifies | Where it is defined | When to change it |
| --- | --- | --- | --- |
| Builder (software) version | The Python pipeline implementation | `__version__` in `src/soda_openalex/__init__.py` and `version` in `pyproject.toml` | When releasing code fixes or features. |
| Dataset version | A particular frozen data release | `dataset_version` in the sampling config | When releasing new sampled IDs, refreshed metadata, corrected values, or other changes to the data. |
| Schema version | Table names, columns, keys, representations, and variable meanings | `SCHEMA_VERSION` and the contract in `src/soda_openalex/schema.py`; selected by `schema_version` in the sampling config | When changing the exported structure or meaning of variables. |

The initial release used **builder 0.1.0 to produce dataset 1.0.0 using schema 1.0.0**. Builder 0.2.0 introduced automatic packaging; the current builder is 0.2.1. Packaging an existing release preserves its original builder provenance and separately records the packager version. The builder version tells developers which software was used; the dataset version tells researchers which data they analysed; the schema version tells consumers which table contract to expect. All three are recorded in `release.json`.

Examples:

- Improving API retries can produce builder 0.1.1 without changing the existing dataset or schema.
- Refreshing OpenAlex metadata requires a new dataset release; the builder and schema can stay unchanged.
- Fixing a transformation bug that changes exported values requires a new builder version and dataset release. The schema can stay unchanged if the column contract and intended meaning are unchanged.
- Renaming a column or changing its meaning requires a new schema version, along with new builder and dataset releases. Use a major schema-version increment for incompatible changes.

When releasing the builder, keep `__version__` and the package version in `pyproject.toml` aligned. New releases read `builder_version` from `__version__` automatically. Packaging records both the original release builder and the current packager version.

This builder rejects configs declaring a schema version other than its implemented `SCHEMA_VERSION`. When changing the table contract, update that constant, the configuration, transformations, and generated codebook together. Use the archived source for historical schemas.

For a new dataset release, create a new versioned config and output path. Update the schema version only when its contract changes, and update the codebook to match. Preserve published snapshots and releases; never edit their configuration, metadata, or tables in place.

## Licensing

Code is MIT ([LICENSE](LICENSE)); dataset contributions are CC0 1.0 ([LICENSE-DATA](LICENSE-DATA)). OpenAlex metadata is [CC0](https://help.openalex.org/data/how-its-built/). This does not grant rights to linked articles, PDFs, or other third-party content. Abstracts remain inverted indexes in raw and derived outputs; plaintext abstracts are never published by this pipeline.
