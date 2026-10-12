import pandas as pd
import pytest
import torch


def fixture():
    from recommendation.model import TwoTower
    train = pd.DataFrame([('u','a'),('u','b'),('v','c')],columns=['user_id','channel_name'])
    val = pd.DataFrame([('u','b'),('u','b'),('u','new'),('new_user','a')],columns=['user_id','channel_name'])
    model = TwoTower(2,3,2)
    with torch.no_grad():
        model.user_embedding.weight.copy_(torch.tensor([[1.,0.],[1.,0.]]))
        model.channel_embedding.weight.copy_(torch.tensor([[0.,0.],[2.,0.],[1.,0.]]))
        model.user_projection.weight.copy_(torch.eye(2))
        model.channel_projection.weight.copy_(torch.eye(2))
    return model, train, val, {'u':0,'v':1}, {'a':0,'b':1,'c':2}


def test_exact_scoring_uses_same_coverage_as_baseline():
    from recommendation.evaluate import evaluate_popular, evaluate_retrieval
    model, train, val, users, channels = fixture()
    result = evaluate_retrieval(model,train,val,users,channels,ks=(1,200))
    assert result['coverage'] == evaluate_popular(train,val,ks=(1,200))['coverage']
    assert result['metrics']['1'] == {'recall':1.,'ndcg':1.}
    assert result['metrics']['200'] == {'recall':1.,'ndcg':1.}


def test_ties_prefer_lower_channel_index_and_preserve_train_mode():
    from recommendation.evaluate import evaluate_retrieval
    model, train, val, users, channels = fixture()
    with torch.no_grad():
        model.channel_embedding.weight.zero_()
    model.train()
    result = evaluate_retrieval(model,train,val,users,channels,ks=(1,))
    assert result['metrics']['1']['recall'] == 0
    assert model.training


def test_bad_mapping_and_nonfinite_scores_are_rejected():
    from recommendation.evaluate import evaluate_retrieval
    model, train, val, users, channels = fixture()
    with pytest.raises(ValueError,match='mapping'):
        evaluate_retrieval(model,train,val,{'u':1,'v':0},channels)
    with torch.no_grad():
        model.channel_embedding.weight[0,0] = float('nan')
    with pytest.raises(ValueError,match='finite'):
        evaluate_retrieval(model,train,val,users,channels)
