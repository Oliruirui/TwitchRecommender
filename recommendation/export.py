"""Export and validate a trusted local retrieval bundle; no training or HTTP API."""
import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
import torch

from recommendation.evaluate import build_popular, checksum, validate_mappings
from recommendation.model import TwoTower
from recommendation.prepare_data import write_json

PAYLOADS = ('retrieval_model.pt', 'model_config.json', 'user_mapping.json',
            'channel_mapping.json', 'channel_vectors.npy', 'channels.faiss', 'popular_channels.json')
ARCHITECTURE = 'embedding-linear-no-bias-dot-product'


def _read_json(path: Path):
    return json.loads(path.read_text())


def _load_model(config: dict, weights: Path) -> TwoTower:
    if config.get('architecture') != ARCHITECTURE:
        raise ValueError('Unsupported model architecture')
    if any(type(config.get(k)) is not int or config[k] <= 0 for k in ('num_users', 'num_channels', 'dimension')):
        raise ValueError('Model dimensions must be positive integers')
    model = TwoTower(config['num_users'], config['num_channels'], config['dimension']).float()
    model.load_state_dict(torch.load(weights, map_location='cpu', weights_only=True))
    if any(not torch.isfinite(p).all() for p in model.parameters()):
        raise ValueError('Model weights must be finite')
    model.eval()
    return model


def _validate_mapping(mapping: dict, count: int) -> None:
    if not isinstance(mapping, dict) or len(mapping) != count:
        raise ValueError('Mapping count does not match model')
    if any(type(value) is not int for value in mapping.values()):
        raise ValueError('Mapping values must be integer indices')
    if mapping != {name: i for i, name in enumerate(sorted(mapping))}:
        raise ValueError('Mapping must use sorted identities and contiguous indices')


def load_bundle(bundle_dir: Path) -> dict:
    """Validate checksums before native deserialization; load a locally trusted bundle."""
    root = Path(bundle_dir)
    manifest = _read_json(root / 'manifest.json')
    if (manifest.get('schema_version') != 1 or manifest.get('score') != 'dot_product'
            or manifest.get('normalized') is not False or manifest.get('index', {}).get('type') != 'IndexFlatIP'):
        raise ValueError('Unsupported bundle schema or scoring convention')
    if set(manifest.get('file_checksums', {})) != set(PAYLOADS):
        raise ValueError('Incomplete bundle checksum manifest')
    for name in PAYLOADS:
        if checksum(root / name) != manifest['file_checksums'][name]:
            raise ValueError(f'Bundle checksum mismatch: {name}')
    config = _read_json(root / 'model_config.json')
    users = _read_json(root / 'user_mapping.json')
    channels = _read_json(root / 'channel_mapping.json')
    _validate_mapping(users, config['num_users'])
    _validate_mapping(channels, config['num_channels'])
    for name in ('user_mapping.json', 'channel_mapping.json'):
        if checksum(root / name) != config['provenance'][name]:
            raise ValueError(f'Training mapping fingerprint mismatch: {name}')
    if (manifest['index']['dimension'] != config['dimension'] or manifest['index']['count'] != len(channels)
            or manifest['selected_epoch'] != config['selected_epoch']):
        raise ValueError('Bundle metadata disagrees with selected model')
    model = _load_model(config, root / 'retrieval_model.pt')
    vectors = np.load(root / 'channel_vectors.npy', allow_pickle=False)
    if (vectors.dtype != np.float32 or vectors.shape != (len(channels), config['dimension'])
            or not np.isfinite(vectors).all()):
        raise ValueError('Invalid channel vector shape, dtype or finite values')
    with torch.inference_mode():
        expected = model.encode_channels(torch.arange(len(channels))).numpy()
    if not np.allclose(vectors, expected, rtol=1e-5, atol=1e-6):
        raise ValueError('Channel vectors disagree with bundled model')
    index = faiss.read_index(str(root / 'channels.faiss'))
    if (not isinstance(index, faiss.IndexFlatIP) or index.metric_type != faiss.METRIC_INNER_PRODUCT
            or index.d != config['dimension'] or index.ntotal != len(channels)):
        raise ValueError('Index type, dimension or count mismatch')
    if not np.array_equal(index.reconstruct_n(0, index.ntotal), vectors):
        raise ValueError('Index vectors disagree with saved channel vectors')
    popular = _read_json(root / 'popular_channels.json')
    if len(popular) != len(channels) or {item['channel_name'] for item in popular} != set(channels):
        raise ValueError('Popular snapshot does not cover training catalog')
    if any(item['channel_id'] != str(channels[item['channel_name']]) for item in popular):
        raise ValueError('Popular snapshot IDs disagree with channel mapping')
    return {'manifest': manifest, 'model': model, 'index': index, 'channel_vectors': vectors,
            'user_mapping': users, 'channel_mapping': channels, 'popular_channels': popular}


def export_bundle(model_dir: Path, prepared_dir: Path, output_dir: Path, version: str) -> dict:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', version):
        raise ValueError('Invalid model version')
    model_dir, prepared_dir, output_dir = Path(model_dir), Path(prepared_dir), Path(output_dir)
    if output_dir.exists():
        raise ValueError('Output already exists; choose a fresh version directory')
    config = _read_json(model_dir / 'model_config.json')
    # Export needs no held-out labels. Verify only training inputs actually consumed.
    for name in ('train.parquet', 'user_mapping.json', 'channel_mapping.json', 'data_manifest.json'):
        if checksum(prepared_dir / name) != config['provenance'][name]:
            raise ValueError(f'Training input fingerprint mismatch: {name}')
    train = pd.read_parquet(prepared_dir / 'train.parquet')
    users = _read_json(prepared_dir / 'user_mapping.json')
    channels = _read_json(prepared_dir / 'channel_mapping.json')
    validate_mappings(train, users, channels)
    _validate_mapping(users, config['num_users']); _validate_mapping(channels, config['num_channels'])
    torch.set_num_threads(1)
    model = _load_model(config, model_dir / 'best_model.pt')
    with torch.inference_mode():
        vectors = np.ascontiguousarray(model.encode_channels(torch.arange(len(channels))).numpy(), dtype=np.float32)
    if not np.isfinite(vectors).all():
        raise ValueError('Channel vectors must be finite')
    index = faiss.IndexFlatIP(config['dimension'])
    index.add(vectors)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    # Same-filesystem staging: publish only after a complete round-trip validation.
    with tempfile.TemporaryDirectory(prefix=f'.{output_dir.name}-', dir=output_dir.parent) as temp:
        stage = Path(temp) / 'bundle'; stage.mkdir()
        shutil.copyfile(model_dir / 'best_model.pt', stage / 'retrieval_model.pt')
        shutil.copyfile(model_dir / 'model_config.json', stage / 'model_config.json')
        for name in ('user_mapping.json', 'channel_mapping.json'):
            shutil.copyfile(prepared_dir / name, stage / name)
        np.save(stage / 'channel_vectors.npy', vectors, allow_pickle=False)
        faiss.write_index(index, str(stage / 'channels.faiss'))
        write_json(stage / 'popular_channels.json', build_popular(train))
        manifest = {'schema_version': 1, 'model_version': version, 'selected_epoch': config['selected_epoch'],
                    'score': 'dot_product', 'normalized': False,
                    'index': {'type': 'IndexFlatIP', 'dimension': index.d, 'count': index.ntotal},
                    'id_order': 'row i is channel_mapping index i; bundle-local IDs, not Twitch numeric IDs',
                    'ties': 'FAISS may reorder or select different equal-scoring boundary channels',
                    'runtime': {'faiss': str(faiss.__version__), 'torch': str(torch.__version__), 'numpy': np.__version__},
                    'file_checksums': {name: checksum(stage / name) for name in PAYLOADS}}
        write_json(stage / 'manifest.json', manifest)
        load_bundle(stage)
        if output_dir.exists():
            raise ValueError('Output already exists; refusing to replace it')
        stage.rename(output_dir)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    try:
        manifest = export_bundle(args.model, args.prepared, args.output, args.version)
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        print(f'Export failed: {exc}', file=sys.stderr)
        return 1
    print(json.dumps({'model_version': manifest['model_version'], 'selected_epoch': manifest['selected_epoch'],
                      'index': manifest['index'], 'output': str(args.output)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
