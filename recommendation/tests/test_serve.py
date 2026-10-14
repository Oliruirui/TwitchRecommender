import shutil
from uuid import UUID

import pytest
from fastapi.testclient import TestClient


def make_app(bundle_dir):
    from recommendation.serve import create_app
    return create_app(bundle_dir)


def test_ready_api_returns_personalized_top_k_and_fresh_request_ids(bundle_dir):
    with TestClient(make_app(bundle_dir)) as client:
        assert client.get('/health/live').json() == {'status': 'alive'}
        assert client.get('/health/ready').json() == {'status': 'ready', 'model_version': 'test-v1'}
        responses = [client.post('/v1/recommendations', json={'user_id': ' alice ', 'k': 3}) for _ in range(2)]
        for response in responses:
            assert response.status_code == 200
            result = response.json()
            assert UUID(result['request_id']).version == 4
            assert result['method'] == 'two_tower'
            assert result['fallback_reason'] is None
            assert result['model_version'] == 'test-v1'
            assert result['items'] == [{'channel_id': str(i), 'channel_name': f'channel-{i:02}',
                                        'retrieval_score': float(i)} for i in [19, 18, 17]]
        assert responses[0].json()['request_id'] != responses[1].json()['request_id']


def test_default_k_and_unknown_user_fallback(bundle_dir):
    with TestClient(make_app(bundle_dir)) as client:
        result = client.post('/v1/recommendations', json={'user_id': 'new-user'}).json()
        assert len(result['items']) == 10
        assert result['method'] == 'popular'
        assert result['fallback_reason'] == 'unknown_user'
        assert [x['channel_id'] for x in result['items']] == [str(i) for i in range(10)]
        assert all(x['retrieval_score'] is None for x in result['items'])
        assert len(client.post('/v1/recommendations', json={'user_id': 'alice', 'k': 200}).json()['items']) == 20


@pytest.mark.parametrize('body', [
    {}, {'user_id': ''}, {'user_id': ' \t '}, {'user_id': 1}, {'user_id': None},
    {'user_id': 'x'*129}, {'user_id': 'alice', 'k': 0}, {'user_id': 'alice', 'k': 201},
    {'user_id': 'alice', 'k': True}, {'user_id': 'alice', 'k': 3.0},
    {'user_id': 'alice', 'k': '3'}, {'user_id': 'alice', 'k': None},
])
def test_invalid_input_is_rejected_before_retrieval(bundle_dir, body, monkeypatch):
    app = make_app(bundle_dir)
    with TestClient(app) as client:
        monkeypatch.setattr(app.state.engine, 'recommend', lambda *a: pytest.fail('invalid input reached model'))
        assert client.post('/v1/recommendations', json=body).status_code == 422


@pytest.mark.parametrize('problem', ['missing', 'corrupt', 'no_config'])
def test_bad_bundle_keeps_liveness_but_not_readiness_or_recommendations(bundle_dir, monkeypatch, problem):
    monkeypatch.delenv('RECOMMENDER_BUNDLE_DIR', raising=False)
    if problem == 'missing': shutil.rmtree(bundle_dir)
    if problem == 'corrupt': (bundle_dir / 'channels.faiss').write_bytes(b'corrupt')
    with TestClient(make_app(None if problem == 'no_config' else bundle_dir)) as client:
        assert client.get('/health/live').status_code == 200
        ready = client.get('/health/ready')
        assert ready.status_code == 503
        assert ready.json() == {'status': 'not_ready'}
        response = client.post('/v1/recommendations', json={'user_id': 'alice'})
        assert response.status_code == 503
        assert response.json() == {'detail': 'recommendation service unavailable'}


def test_requests_reuse_loaded_artifacts_after_files_are_removed(bundle_dir):
    with TestClient(make_app(bundle_dir)) as client:
        shutil.rmtree(bundle_dir)
        for _ in range(2):
            response = client.post('/v1/recommendations', json={'user_id': 'alice', 'k': 1})
            assert response.status_code == 200
            assert response.json()['items'][0]['channel_id'] == '19'
            assert response.json()['model_version'] == 'test-v1'


def test_search_failure_has_explicit_http_fallback(bundle_dir, monkeypatch):
    app = make_app(bundle_dir)
    with TestClient(app) as client:
        def broken_search(*args): raise RuntimeError('internal path must not leak')
        monkeypatch.setattr(app.state.engine.index, 'search', broken_search)
        response = client.post('/v1/recommendations', json={'user_id': 'alice', 'k': 2})
        assert response.status_code == 200
        result = response.json()
        assert result['method'] == 'popular'
        assert result['fallback_reason'] == 'retrieval_error'
        assert result['items'] == [{'channel_id': str(i), 'channel_name': f'channel-{i:02}',
                                    'retrieval_score': None} for i in [0, 1]]
        assert 'internal path' not in response.text


def test_failed_warmup_does_not_publish_partial_engine(bundle_dir, monkeypatch):
    from recommendation.retrieval import RetrievalEngine
    monkeypatch.setattr(RetrievalEngine, 'recommend', lambda *a: {'method': 'popular'})
    with TestClient(make_app(bundle_dir)) as client:
        assert client.get('/health/ready').status_code == 503
        assert client.post('/v1/recommendations', json={'user_id': 'alice'}).status_code == 503


def test_environment_configuration_and_shutdown(bundle_dir, monkeypatch):
    monkeypatch.setenv('RECOMMENDER_BUNDLE_DIR', str(bundle_dir))
    app = make_app(None)
    with TestClient(app) as client:
        assert client.get('/health/ready').status_code == 200
        assert client.get('/docs').status_code == 200
    assert app.state.engine is None
