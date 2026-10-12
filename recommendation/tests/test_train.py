import json
import math
from pathlib import Path

import pandas as pd
import pytest
import torch


def prepared_fixture(tmp_path):
    from recommendation.prepare_data import prepare_data
    rows = [['alex','s0','a',0,0],['alex','s1','b',10,10],['bob','s2','c',20,20],
            ['bob','s3','d',30,30],['alex','s4','b',70,70],['bob','s5','c',80,80],['alex','s6','d',99,99]]
    source=tmp_path/'source.csv'; pd.DataFrame(rows).to_csv(source,index=False,header=False)
    directory=tmp_path/'prepared'; prepare_data(source,directory)
    return directory


def test_masked_loss_weights_each_positive_equally():
    from recommendation.train import pairwise_loss
    positive=torch.zeros(2,requires_grad=True)
    negative=torch.tensor([[0.,2.],[0.,float('nan')]])
    mask=torch.tensor([[True,True],[True,False]])
    result=pairwise_loss(positive,negative,mask)
    expected=((math.log(2)+math.log1p(math.exp(2)))/2+math.log(2))/2
    assert result.item()==pytest.approx(expected)
    result.backward()
    assert torch.isfinite(positive.grad).all()
    with pytest.raises(ValueError):
        pairwise_loss(positive,torch.zeros(2,2),torch.zeros(2,2,dtype=torch.bool))


def test_best_epoch_uses_recall_and_earlier_ties():
    from recommendation.train import select_best_epoch
    history=[{'epoch':1,'validation':{'metrics':{'200':{'recall':.2}}}},
             {'epoch':2,'validation':{'metrics':{'200':{'recall':.3}}}},
             {'epoch':3,'validation':{'metrics':{'200':{'recall':.3}}}}]
    assert select_best_epoch(history)==2


def test_training_updates_weights_reload_and_never_reads_test(tmp_path):
    from recommendation.model import TwoTower
    from recommendation.train import train_retrieval
    prepared=prepared_fixture(tmp_path)
    (prepared/'test.parquet').write_bytes(b'unreadable test data')
    torch.manual_seed(42)
    initial=TwoTower(2,4,32)
    output=tmp_path/'trained'
    report=train_retrieval(prepared,output,{'training':{'epochs':2}})
    assert report['selected_epoch'] in [1,2]
    assert len(json.loads((output/'training_history.json').read_text()))==2
    assert report['popular']['coverage']==report['two_tower']['coverage']
    saved=torch.load(output/'best_model.pt',weights_only=True)
    assert any(not torch.equal(initial.state_dict()[name],value) for name,value in saved.items())
    first=TwoTower(2,4,32); second=TwoTower(2,4,32)
    first.load_state_dict(saved); second.load_state_dict(torch.load(output/'best_model.pt',weights_only=True))
    assert torch.equal(first(torch.tensor([0]),torch.tensor([1])),second(torch.tensor([0]),torch.tensor([1])))
    checkpoint=torch.load(output/'checkpoints/epoch-001.pt',weights_only=True)
    assert 'optimizer_state' in checkpoint and 'sampler_state' in checkpoint and 'shuffle_state' in checkpoint


def test_mapping_mismatch_fails_before_outputs(tmp_path):
    from recommendation.train import train_retrieval
    prepared=prepared_fixture(tmp_path)
    (prepared/'user_mapping.json').write_text('{"alex":1,"bob":0}')
    output=tmp_path/'trained'
    with pytest.raises(ValueError,match='mapping'):
        train_retrieval(prepared,output,{})
    assert not (output/'best_model.pt').exists()


def test_nonfinite_run_never_publishes_selected_model(tmp_path,monkeypatch):
    from recommendation.model import TwoTower
    from recommendation.train import train_retrieval
    prepared=prepared_fixture(tmp_path)
    original=TwoTower.forward
    monkeypatch.setattr(TwoTower,'forward',lambda self,u,c: original(self,u,c)*float('nan'))
    output=tmp_path/'trained'
    with pytest.raises(ValueError,match='finite'):
        train_retrieval(prepared,output,{})
    assert not (output/'best_model.pt').exists()
