import math

import pandas as pd
import pytest


def test_hand_calculated_recall_and_ndcg():
    from recommendation.evaluate import ranking_metrics
    assert ranking_metrics(['b', 'd', 'e'], {'b', 'd'}, 3) == {'recall': 1.0, 'ndcg': 1.0}
    got = ranking_metrics(['a', 'b', 'c'], {'b', 'd'}, 3)
    assert got['recall'] == 0.5
    assert got['ndcg'] == pytest.approx((1 / math.log2(3)) / (1 + 1 / math.log2(3)))


def test_popularity_counts_distinct_users_and_ties():
    from recommendation.evaluate import build_popular
    train = pd.DataFrame([('alice', 'a'), ('alice', 'a'), ('bob', 'b'), ('carol', 'b'), ('alice', 'c')], columns=['user_id', 'channel_name'])
    items = build_popular(train)
    assert [i['channel_name'] for i in items] == ['b', 'a', 'c']
    assert [i['distinct_users'] for i in items] == [2, 1, 1]
    assert [i['channel_id'] for i in items] == ['1', '0', '2']


def test_duplicate_observations_and_unknown_coverage():
    from recommendation.evaluate import evaluate_popular
    train = pd.DataFrame([('alex', 'a'), ('other', 'a'), ('alex', 'b')], columns=['user_id', 'channel_name'])
    val = pd.DataFrame([('alex', 'b'), ('alex', 'b'), ('alex', 'new'), ('other', 'new'), ('new_user', 'a')], columns=['user_id', 'channel_name'])
    result = evaluate_popular(train, val, ks=(1, 3))
    assert result['metrics']['1'] == {'recall': 0.0, 'ndcg': 0.0}
    assert result['metrics']['3']['recall'] == 1.0
    assert result['metrics']['3']['ndcg'] == pytest.approx(1 / math.log2(3))
    assert result['coverage'] == {
        'validation_users': 3, 'known_users': 2, 'unknown_users': 1, 'eligible_users': 1,
        'known_users_without_eligible_labels': 1, 'validation_user_channel_pairs': 4,
        'unknown_channel_pairs': 2, 'unknown_user_pairs': 1,
    }
    assert result['catalog_channels'] == 2


def test_users_are_weighted_equally():
    from recommendation.evaluate import evaluate_popular
    train = pd.DataFrame([('u1','a'),('u2','a'),('u1','b')], columns=['user_id','channel_name'])
    val = pd.DataFrame([('u1','a'),('u1','b'),('u2','a')], columns=['user_id','channel_name'])
    assert evaluate_popular(train, val, ks=(1,))['metrics']['1']['recall'] == 0.75


def test_short_catalog_and_repeat_viewing_remain_eligible():
    from recommendation.evaluate import evaluate_popular
    train = pd.DataFrame([('alex','a')], columns=['user_id','channel_name'])
    assert evaluate_popular(train, train, ks=(200,))['metrics']['200'] == {'recall': 1.0, 'ndcg': 1.0}


def test_no_eligible_users_is_error():
    from recommendation.evaluate import evaluate_popular
    train = pd.DataFrame([('alex','a')], columns=['user_id','channel_name'])
    val = pd.DataFrame([('new_user','a'), ('alex','unknown')], columns=['user_id','channel_name'])
    with pytest.raises(ValueError, match='eligible'):
        evaluate_popular(train, val)


def test_metric_rejects_empty_labels_duplicates_and_invalid_k():
    from recommendation.evaluate import ranking_metrics
    for recommendations, labels, k in [(['a'], set(), 3), (['a','a'], {'a'}, 3), (['a'], {'a'}, 0)]:
        with pytest.raises(ValueError):
            ranking_metrics(recommendations, labels, k)


def test_evaluation_cli_uses_config_and_does_not_read_test_split(tmp_path):
    import json
    import subprocess
    import sys
    from recommendation.prepare_data import prepare_data
    source = tmp_path / 'source.csv'
    pd.DataFrame([['alex','s0','a',0,0], ['alex','s1','b',10,20],
                  ['alex','s2','b',70,80], ['alex','s3','a',99,99]]).to_csv(source,index=False,header=False)
    prepared = tmp_path / 'prepared'
    prepare_data(source, prepared)
    (prepared / 'test.parquet').write_bytes(b'NOT PARQUET: test labels must not be read')
    config = tmp_path / 'config.yaml'
    config.write_text('{"evaluation_k": [1,3]}')
    output = tmp_path / 'report'
    result = subprocess.run([sys.executable, '-m', 'recommendation.evaluate', '--prepared', str(prepared), '--output', str(output), '--config', str(config)],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads((output / 'validation_report.json').read_text())
    assert set(report['metrics']) == {'1','3'}
    assert report['metrics']['1']['recall'] == 0.0
    assert report['metrics']['3']['recall'] == 1.0
    assert report['provenance']['source_sha256']
