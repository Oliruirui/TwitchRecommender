"""Small real artifacts for retrieval and HTTP boundary tests."""
import json

import faiss
import numpy as np
import pytest
import torch

from recommendation.evaluate import checksum
from recommendation.export import ARCHITECTURE, PAYLOADS, load_bundle
from recommendation.model import TwoTower


@pytest.fixture
def bundle_dir(tmp_path):
    root = tmp_path / 'bundle'
    root.mkdir()
    users = {'alice': 0, 'bob': 1}
    channels = {f'channel-{i:02}': i for i in range(20)}
    model = TwoTower(2, 20, 2)
    with torch.no_grad():
        model.user_embedding.weight.copy_(torch.tensor([[1., 0.], [0., 1.]]))
        # Alice's scores are 0..19; Bob's are all 1 (ties).
        model.channel_embedding.weight.copy_(torch.tensor([[float(i), 1.] for i in range(20)]))
        model.user_projection.weight.copy_(torch.eye(2))
        model.channel_projection.weight.copy_(torch.eye(2))
    model.eval()
    torch.save(model.state_dict(), root / 'retrieval_model.pt')
    for name, value in [('user_mapping.json', users), ('channel_mapping.json', channels)]:
        (root / name).write_text(json.dumps(value))
    config = {'architecture': ARCHITECTURE, 'num_users': 2, 'num_channels': 20,
              'dimension': 2, 'selected_epoch': 30,
              'provenance': {name: checksum(root / name) for name in
                             ['user_mapping.json', 'channel_mapping.json']}}
    (root / 'model_config.json').write_text(json.dumps(config))
    with torch.inference_mode():
        vectors = np.ascontiguousarray(model.encode_channels(torch.arange(20)).numpy())
    np.save(root / 'channel_vectors.npy', vectors)
    index = faiss.IndexFlatIP(2)
    index.add(vectors)
    faiss.write_index(index, str(root / 'channels.faiss'))
    popular = [{'channel_id': str(i), 'channel_name': f'channel-{i:02}', 'distinct_users': 20-i}
               for i in range(20)]
    (root / 'popular_channels.json').write_text(json.dumps(popular))
    manifest = {'schema_version': 1, 'model_version': 'test-v1', 'selected_epoch': 30,
                'score': 'dot_product', 'normalized': False,
                'index': {'type': 'IndexFlatIP', 'dimension': 2, 'count': 20},
                'file_checksums': {name: checksum(root / name) for name in PAYLOADS}}
    (root / 'manifest.json').write_text(json.dumps(manifest))
    return root


@pytest.fixture
def bundle(bundle_dir):
    return load_bundle(bundle_dir)
