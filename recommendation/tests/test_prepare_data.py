import json
from pathlib import Path

import pandas as pd
import pytest


# Hand-designed timeline is [0,100), with cutoffs 70 and 85.
ROWS = [
    ['alice', 's0', 'a', 0, 0],
    ['alice', 's1', 'b', 10, 20],
    ['alice', 's2', 'b', 30, 40],
    ['alice', 's3', 'a', 69, 69],
    ['alice', 's4', 'c', 70, 70],
    ['bob', 's5', 'b', 80, 84],
    ['future', 's6', 'new', 85, 90],
    ['alice', 's7', 'd', 99, 99],
    ['alice', 'cross', 'e', 68, 70],
]


def run(tmp_path, rows=ROWS, **kwargs):
    from recommendation.prepare_data import prepare_data
    source = tmp_path / 'source.csv'
    pd.DataFrame(rows).to_csv(source, index=False, header=False)
    out = tmp_path / 'prepared'
    manifest = prepare_data(source, out, **kwargs)
    return out, manifest


def test_round_boundaries_and_training_only_mappings(tmp_path):
    out, m = run(tmp_path)
    assert m['timeline'] == {'lower': 0, 'train_end': 70, 'validation_end': 85, 'upper': 100}
    assert pd.read_parquet(out / 'train.parquet').stream_id.tolist() == ['s0', 's1', 's2', 's3']
    assert pd.read_parquet(out / 'validation.parquet').stream_id.tolist() == ['s4', 's5']
    assert pd.read_parquet(out / 'test.parquet').stream_id.tolist() == ['s6', 's7']
    assert m['counts']['crossing_intervals'] == 1
    assert json.loads((out / 'user_mapping.json').read_text()) == {'alice': 0}
    assert json.loads((out / 'channel_mapping.json').read_text()) == {'a': 0, 'b': 1}


def test_cleaning_keeps_single_round_and_repeats(tmp_path):
    rows = ROWS + [ROWS[0], ['', 's8', 'a', 1, 2], ['alice', 's9', 'a', 4, 3],
                   ['alice', 's10', 'a', '1.5', 2], ['alice', 's11', 'a', -1, 2]]
    out, m = run(tmp_path, rows)
    assert m['counts']['invalid_rows'] == 4
    assert m['counts']['duplicate_rows'] == 1
    train = pd.read_parquet(out / 'train.parquet')
    assert len(train) == 4
    assert len(train[train.channel_name == 'b']) == 2


def test_sampling_is_row_order_invariant(tmp_path):
    left = tmp_path / 'left'; left.mkdir()
    right = tmp_path / 'right'; right.mkdir()
    # Each sampling candidate has train/validation rows, so this checks sampling
    # rather than the empty-split guard.
    rows = ROWS + [['future', 'ft', 'a', 1, 1], ['future', 'fv', 'a', 71, 71],
                   ['bob', 'bt', 'a', 2, 2]]
    a, ma = run(left, rows, max_users=1)
    b, mb = run(right, list(reversed(rows)), max_users=1)
    assert ma['sample']['selected_users'] == ['future']
    assert ma['sample']['selected_users'] == mb['sample']['selected_users']
    for name in ['train', 'validation', 'test']:
        pd.testing.assert_frame_equal(pd.read_parquet(a / f'{name}.parquet'), pd.read_parquet(b / f'{name}.parquet'))


def test_invalid_parameter_and_empty_split_fail(tmp_path):
    with pytest.raises(ValueError, match='max_users'):
        run(tmp_path, max_users=0)
    with pytest.raises(ValueError, match='validation'):
        run(tmp_path, [['alice', 's1', 'a', 0, 0], ['alice', 's2', 'b', 99, 99]])
    assert not (tmp_path / 'prepared' / 'data_manifest.json').exists()


def test_cli_reads_config_and_reports_validation_errors(tmp_path):
    import subprocess
    import sys
    source = tmp_path / 'source.csv'
    pd.DataFrame(ROWS).to_csv(source, index=False, header=False)
    config = tmp_path / 'config.yaml'
    config.write_text('{"max_users": 3, "seed": 7}')
    output = tmp_path / 'cli-output'
    result = subprocess.run([sys.executable, '-m', 'recommendation.prepare_data', '--input', str(source), '--output', str(output), '--config', str(config)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((output / 'data_manifest.json').read_text())
    assert manifest['sample']['seed'] == 7
    assert manifest['sample']['max_users'] == 3
    invalid = subprocess.run([sys.executable, '-m', 'recommendation.prepare_data', '--input', str(source), '--output', str(output), '--max-users', '0'], capture_output=True, text=True)
    assert invalid.returncode != 0
    assert 'max_users' in invalid.stderr
