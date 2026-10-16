"""Commands for frozen snapshots, validated tables, and deposit bundles."""
import argparse
import json
import re
from pathlib import Path
from .pipeline import sample, build, validate_release, require
from .package import package_release, find_source_root, source_files


def default_paths(snapshot, release=None, packages=None, config=None):
    snapshot = Path(snapshot)
    config = config or json.loads((snapshot / 'config.json').read_text())
    version = config['dataset_version']
    require(isinstance(version, str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', version)),
            'Dataset version must be a safe filename component')
    root = snapshot.parent.parent if snapshot.parent.name == 'raw' else snapshot.parent
    return (Path(release) if release else root / 'releases' / version,
            Path(packages) if packages else root / 'zenodo' / version)


def check_new_output(path):
    path = Path(path)
    require(not path.exists() and not path.with_name(path.name + '.partial').exists(),
            f'Output or partial output already exists: {path}; choose a new path')


def check_separate_outputs(*paths):
    resolved = [Path(p).resolve() for p in paths]
    for i, path in enumerate(resolved):
        for other in resolved[i + 1:]:
            require(not (path.is_relative_to(other) or other.is_relative_to(path)),
                    'Snapshot, release, and package directories must be separate, non-nested paths')


def sample_pipeline(config_path, snapshot, release_output=None, package_output=None, source_root=None, client=None):
    """The default sampling command completes all three local stages."""
    config = json.loads(Path(config_path).read_text())
    release, packages = default_paths(snapshot, release_output, package_output, config)
    check_separate_outputs(snapshot, release, packages)
    for path in (snapshot, release, packages):
        check_new_output(path)
    source_root = find_source_root(source_root)
    source_files(source_root)  # Fail before API requests when the checkout is incomplete.
    sample(config_path, snapshot, client)
    print(f'Snapshot frozen: {snapshot}', flush=True)
    build(snapshot, release)
    print(f'Release validated: {release}', flush=True)
    package_release(snapshot, release, packages, source_root)
    print(f'Zenodo deposit files: {packages}', flush=True)
    return release, packages


def main():
    parser = argparse.ArgumentParser(description='Build frozen SoDa OpenAlex teaching datasets')
    commands = parser.add_subparsers(dest='command', required=True)
    sampling = commands.add_parser('sample', help='Freeze a NEW sample, build tables, and create Zenodo files')
    sampling.add_argument('--config', default='config/v1.json')
    sampling.add_argument('--output', required=True, help='New raw snapshot directory')
    sampling.add_argument('--snapshot-only', action='store_true', help='Only freeze raw data; skip building and packaging')
    sampling.add_argument('--release-output', help='Defaults to data/releases/<dataset_version>')
    sampling.add_argument('--package-output', help='Defaults to data/zenodo/<dataset_version>')
    sampling.add_argument('--source-root', help='Source checkout to include in the reproducibility archive')
    for name in ('build', 'validate', 'package'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--snapshot', required=True)
        cmd.add_argument('--output', required=True,
                         help='New package directory' if name == 'package' else 'CSV release directory')
        if name == 'build':
            cmd.add_argument('--no-package', action='store_true', help='Build tables without creating deposit files')
            cmd.add_argument('--package-output', help='New deposit directory; defaults to data/zenodo/<dataset_version>')
        if name in ('build', 'package'):
            cmd.add_argument('--source-root', help='Source checkout to include in the reproducibility archive')
        if name == 'package':
            cmd.add_argument('--release', required=True, help='Existing validated CSV release')
    args = parser.parse_args()
    try:
        if args.command == 'sample':
            require(not args.snapshot_only or not (args.release_output or args.package_output),
                    '--snapshot-only cannot be combined with output paths for later stages')
            if args.snapshot_only:
                sample(args.config, args.output)
            else:
                sample_pipeline(args.config, args.output, args.release_output, args.package_output, args.source_root)
        elif args.command == 'build':
            if not args.no_package:
                _, packages = default_paths(args.snapshot, args.output, args.package_output)
                check_separate_outputs(args.snapshot, args.output, packages)
                check_new_output(packages)
                root = find_source_root(args.source_root)
                source_files(root)
            else:
                require(not args.package_output, '--no-package cannot be combined with --package-output')
            build(args.snapshot, args.output)
            if not args.no_package:
                package_release(args.snapshot, args.output, packages, root)
                print(f'Zenodo deposit files: {packages}')
        elif args.command == 'package':
            package_release(args.snapshot, args.release, args.output, args.source_root)
            print(f'Zenodo deposit files: {args.output}')
        else:
            validate_release(args.snapshot, args.output)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print(f'{args.command}: OK')


if __name__ == '__main__':
    main()
