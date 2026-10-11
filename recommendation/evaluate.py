"""Evaluate training-only popularity on validation; never consume test labels."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import pandas as pd
import yaml

from recommendation.prepare_data import write_json, load_config


def build_popular(train: pd.DataFrame) -> list[dict]:
    if train.empty:
        raise ValueError('Empty training catalog')
    counts = train.groupby('channel_name').user_id.nunique()
    mapping = {name: i for i, name in enumerate(sorted(counts.index))}
    ordered = sorted(counts.index, key=lambda c: (-int(counts[c]), c))
    return [{'channel_id': str(mapping[c]), 'channel_name': c, 'distinct_users': int(counts[c])} for c in ordered]


def ranking_metrics(recommendations: list[str], relevant: set[str], k: int) -> dict:
    if k <= 0 or not relevant:
        raise ValueError('Metrics require positive K and nonempty relevant labels')
    if len(recommendations) != len(set(recommendations)):
        raise ValueError('Recommendations must contain distinct channels')
    hits = [int(c in relevant) for c in recommendations[:k]]
    dcg = sum(hit / math.log2(i + 2) for i, hit in enumerate(hits))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    return {'recall': sum(hits) / len(relevant), 'ndcg': dcg / ideal}


def evaluate_popular(train: pd.DataFrame, validation: pd.DataFrame, ks: tuple[int, ...] = (10, 200)) -> dict:
    if not ks or any(isinstance(k, bool) or not isinstance(k, int) or k <= 0 for k in ks):
        raise ValueError('K values must be positive integers')
    popular = build_popular(train)
    channels = {item['channel_name'] for item in popular}
    users = set(train.user_id)
    pairs = validation[['user_id', 'channel_name']].drop_duplicates()
    known_user = pairs.user_id.isin(users)
    known_channel = pairs.channel_name.isin(channels)
    eligible_pairs = pairs[known_user & known_channel]
    labels = eligible_pairs.groupby('user_id').channel_name.agg(set)
    if labels.empty:
        raise ValueError('No eligible validation users with training-known channel labels')
    coverage = {
        'validation_users': int(pairs.user_id.nunique()),
        'known_users': int(pairs[known_user].user_id.nunique()),
        'unknown_users': int(pairs[~known_user].user_id.nunique()),
        'eligible_users': len(labels),
        'known_users_without_eligible_labels': int(pairs[known_user].user_id.nunique()) - len(labels),
        'validation_user_channel_pairs': len(pairs),
        'unknown_channel_pairs': int((~known_channel).sum()),
        'unknown_user_pairs': int((~known_user).sum()),
    }
    metrics = {}
    for k in ks:
        recommendations = [item['channel_name'] for item in popular[:k]]
        scores = [ranking_metrics(recommendations, relevant, k) for relevant in labels]
        metrics[str(k)] = {key: math.fsum(s[key] for s in scores) / len(scores) for key in ['recall', 'ndcg']}
    return {
        'method': 'popular_distinct_training_users', 'split': 'validation', 'catalog_channels': len(channels),
        'metrics': metrics, 'coverage': coverage,
        'protocol': {
            'queries': 'one per training-known user at validation start; no validation feature updates',
            'relevance': 'distinct validation channels within training catalog; repeat viewing allowed',
            'averaging': 'equal weight per user with at least one eligible label',
            'unknown_coverage': 'unknown_user_pairs and unknown_channel_pairs use all validation_user_channel_pairs as denominator and may overlap; user counts use validation_users',
            'ndcg': 'binary relevance; ideal DCG over min(K, eligible relevant channels)',
        },
    }


def checksum(path: Path) -> str:
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--k', type=int, nargs='+')
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('config.yaml'))
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        ks = args.k if args.k is not None else config.get('evaluation_k', [10, 200])
        if not isinstance(ks, list):
            raise ValueError('evaluation_k must be a list of positive integers')
        if args.output.exists() and any(args.output.iterdir()):
            raise ValueError('Output directory is not empty; choose a new output directory')
        manifest_path = args.prepared / 'data_manifest.json'
        manifest = json.loads(manifest_path.read_text())
        train_path, val_path = args.prepared / 'train.parquet', args.prepared / 'validation.parquet'
        train, validation = pd.read_parquet(train_path), pd.read_parquet(val_path)
        report = evaluate_popular(train, validation, tuple(ks))
        report['provenance'] = {'source_sha256': manifest['source']['sha256'], 'manifest_sha256': checksum(manifest_path),
                                'train_sha256': checksum(train_path), 'validation_sha256': checksum(val_path),
                                'seed': manifest['sample']['seed'], 'timeline': manifest['timeline']}
        args.output.mkdir(parents=True, exist_ok=True)
        write_json(args.output / 'popular_channels.json', build_popular(train))
        write_json(args.output / 'validation_report.json', report)
    except (ValueError, OSError, KeyError, yaml.YAMLError) as exc:
        print(f'Evaluation failed: {exc}', file=sys.stderr)
        return 1
    print(json.dumps({'metrics': report['metrics'], 'coverage': report['coverage']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
