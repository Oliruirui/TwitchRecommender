"""Prepare LiveRec's headerless interaction CSV without future-ID leakage."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

COLUMNS = ['user_id', 'stream_id', 'channel_name', 'start', 'stop']
SOURCE_URL = 'https://github.com/JRappaz/liverec#datasets'


def write_json(path: Path, value: dict | list) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def load_config(path: Path) -> dict:
    with path.open() as file:
        value = yaml.safe_load(file)
    if not isinstance(value, dict):
        raise ValueError('Config must be a mapping')
    return value


def prepare_data(input_csv: Path, output_dir: Path, max_users: int = 5000, seed: int = 42) -> dict:
    if isinstance(max_users, bool) or not isinstance(max_users, int) or max_users <= 0:
        raise ValueError('max_users must be positive')
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError('seed must be an integer')
    input_csv, output_dir = Path(input_csv), Path(output_dir)
    with input_csv.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    try:
        rows = pd.read_csv(input_csv, header=None, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError as exc:
        raise ValueError('Input CSV has no rows') from exc
    if rows.shape[1] != 5:
        raise ValueError('Expected five headerless CSV columns')
    rows.columns = COLUMNS
    for name in COLUMNS:
        rows[name] = rows[name].str.strip()
    valid = rows[['user_id', 'stream_id', 'channel_name']].ne('').all(axis=1)
    # Round values must be literal nonnegative integers, not fractional timestamps.
    for name in ['start', 'stop']:
        literal = rows[name].str.fullmatch(r'[0-9]+') & rows[name].str.len().le(18)
        rows[name] = pd.to_numeric(rows[name].where(literal), errors='coerce')
        valid &= literal & rows[name].notna()
    valid &= rows.stop.ge(rows.start)
    invalid_count = int((~valid).sum())
    cleaned = rows[valid].copy()
    cleaned[['start', 'stop']] = cleaned[['start', 'stop']].astype('int64')
    before_dedup = len(cleaned)
    cleaned = cleaned.drop_duplicates(COLUMNS)
    duplicate_count = before_dedup - len(cleaned)
    if cleaned.empty:
        raise ValueError('No valid observations remain after cleaning')

    lower, upper = int(cleaned.start.min()), int(cleaned.stop.max()) + 1
    width = upper - lower
    train_end = lower + width * 70 // 100
    validation_end = lower + width * 85 // 100
    if not lower < train_end < validation_end < upper:
        raise ValueError('Observation timeline is too short for nonempty split windows')
    population = cleaned.user_id.unique().tolist()
    ordered = sorted(population, key=lambda u: (hashlib.sha256(f'{seed}:{u}'.encode()).hexdigest(), u))
    selected = ordered[:max_users]
    sampled = cleaned[cleaned.user_id.isin(selected)].copy()
    parts = {}
    for name, lo, hi in [('train', lower, train_end), ('validation', train_end, validation_end), ('test', validation_end, upper)]:
        part = sampled[(sampled.start >= lo) & (sampled.stop < hi)]
        parts[name] = part.sort_values(['start', 'stop', 'user_id', 'channel_name', 'stream_id']).reset_index(drop=True)
    for name in ['train', 'validation']:
        if parts[name].empty:
            raise ValueError(f'Empty {name} split; increase sample size or inspect observation timeline')
    train = parts['train']
    users = {u: i for i, u in enumerate(sorted(train.user_id.unique()))}
    channels = {c: i for i, c in enumerate(sorted(train.channel_name.unique()))}
    manifest = {
        'schema_version': 1,
        'source': {'filename': input_csv.name, 'sha256': digest, 'documentation': SOURCE_URL},
        'timeline': {'lower': lower, 'train_end': train_end, 'validation_end': validation_end, 'upper': upper},
        'interval_semantics': 'inclusive first/last observed rounds; retained in [lo,hi) when start>=lo and stop<hi',
        'sample': {'seed': seed, 'max_users': max_users, 'population_users': len(population), 'selected_users': sorted(selected), 'method': 'SHA256(seed:raw_user_id), ascending'},
        'mapping_semantics': 'sorted training-only raw identities to zero-based bundle-local embedding indices',
        'counts': {'input_rows': len(rows), 'invalid_rows': invalid_count, 'duplicate_rows': duplicate_count,
                   'cleaned_rows': len(cleaned), 'sampled_rows': len(sampled),
                   'crossing_intervals': len(sampled) - sum(len(p) for p in parts.values()),
                   'split_rows': {name: len(part) for name, part in parts.items()},
                   'training_users': len(users), 'training_channels': len(channels)},
    }
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError('Output directory is not empty; choose a new output directory')
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, part in parts.items():
        part.to_parquet(output_dir / f'{name}.parquet', index=False)
    write_json(output_dir / 'user_mapping.json', users)
    write_json(output_dir / 'channel_mapping.json', channels)
    # Manifest written last marks successful output generation.
    write_json(output_dir / 'data_manifest.json', manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-users', type=int)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('config.yaml'))
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        max_users = args.max_users if args.max_users is not None else config.get('max_users', 5000)
        seed = args.seed if args.seed is not None else config.get('seed', 42)
        manifest = prepare_data(args.input, args.output, max_users, seed)
    except (ValueError, OSError, pd.errors.ParserError, yaml.YAMLError) as exc:
        print(f'Preparation failed: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(manifest['counts'], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
