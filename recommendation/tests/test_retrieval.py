import numpy as np
import pytest
import torch


def engine(bundle):
    from recommendation.retrieval import RetrievalEngine
    return RetrievalEngine(bundle)


def test_known_user_returns_hand_computed_top_k(bundle):
    result = engine(bundle).recommend('alice', 3)
    assert result == {'model_version': 'test-v1', 'method': 'two_tower', 'fallback_reason': None,
                      'items': [{'channel_id': str(i), 'channel_name': f'channel-{i:02}',
                                 'retrieval_score': float(i)} for i in [19, 18, 17]]}


def test_unknown_user_uses_popularity_order_and_null_scores(bundle):
    result = engine(bundle).recommend('new-user', 3)
    assert result['method'] == 'popular'
    assert result['fallback_reason'] == 'unknown_user'
    assert result['items'] == [{'channel_id': str(i), 'channel_name': f'channel-{i:02}',
                                'retrieval_score': None} for i in [0, 1, 2]]


@pytest.mark.parametrize('user', ['alice', 'new-user'])
def test_short_catalog_returns_every_channel_once(bundle, user):
    result = engine(bundle).recommend(user, 200)
    assert len(result['items']) == 20
    assert {x['channel_id'] for x in result['items']} == {str(i) for i in range(20)}


def test_equal_returned_scores_are_ordered_by_numeric_id(bundle):
    items = engine(bundle).recommend('bob', 20)['items']
    assert [x['channel_id'] for x in items] == [str(i) for i in range(20)]
    assert {x['retrieval_score'] for x in items} == {1.}


def test_repeated_queries_do_not_change_model_or_index(bundle):
    retrieval = engine(bundle)
    before = {key: value.clone() for key, value in bundle['model'].state_dict().items()}
    vectors = bundle['index'].reconstruct_n(0, 20).copy()
    # There is no history filter: the same high-scoring channel remains eligible.
    assert retrieval.recommend('alice', 1)['items'][0]['channel_id'] == '19'
    assert retrieval.recommend('alice', 1)['items'][0]['channel_id'] == '19'
    assert all(torch.equal(before[key], value) for key, value in bundle['model'].state_dict().items())
    np.testing.assert_array_equal(vectors, bundle['index'].reconstruct_n(0, 20))
    assert all(parameter.grad is None for parameter in bundle['model'].parameters())


@pytest.mark.parametrize('failure', ['exception', 'nan', 'duplicate', 'padding', 'too_few', 'out_of_range'])
def test_failed_or_invalid_search_returns_real_popular_fallback(bundle, monkeypatch, failure):
    retrieval = engine(bundle)
    def search(query, k):
        if failure == 'exception':
            raise RuntimeError('native search failed')
        scores = np.array([[19., 18., 17.]], dtype='float32')
        ids = np.array([[19, 18, 17]], dtype='int64')
        if failure == 'nan': scores[0, 0] = np.nan
        if failure == 'duplicate': ids[0, 1] = 19
        if failure == 'padding': ids[0, 1] = -1
        if failure == 'out_of_range': ids[0, 1] = 20
        if failure == 'too_few': return scores[:, :2], ids[:, :2]
        return scores, ids
    monkeypatch.setattr(bundle['index'], 'search', search)
    result = retrieval.recommend('alice', 3)
    assert result['method'] == 'popular'
    assert result['fallback_reason'] == 'retrieval_error'
    assert result['items'] == [{'channel_id': str(i), 'channel_name': f'channel-{i:02}',
                                'retrieval_score': None} for i in [0, 1, 2]]
