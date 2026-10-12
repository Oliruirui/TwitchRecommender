"""Manual CPU training and validation; never reads frozen test labels."""
import argparse
import json
import math
import platform
import random
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from torch.nn import functional as F

from recommendation.evaluate import checksum, evaluate_popular, evaluate_retrieval, validate_mappings
from recommendation.model import TwoTower
from recommendation.prepare_data import load_config, prepare_data, write_json
from recommendation.sampling import NegativeSampler

DEFAULTS = {'dimension':32, 'negative_count':5, 'learning_rate':.001, 'batch_size':256,
            'epochs':10, 'seed':42, 'threads':1, 'evaluation_user_batch_size':64}


def pairwise_loss(positive: torch.Tensor, negative: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    counts=mask.sum(dim=1)
    valid=counts > 0
    if not valid.any():
        raise ValueError('No eligible negative pairs in batch')
    differences=torch.where(mask, negative-positive[:,None], torch.zeros_like(negative))
    losses=F.softplus(differences)*mask
    return (losses.sum(dim=1)[valid]/counts[valid]).mean()


def select_best_epoch(history: list[dict]) -> int:
    if not history:
        raise ValueError('No validation history')
    # max retains the first occurrence of a tied score.
    return max(history,key=lambda item:item['validation']['metrics']['200']['recall'])['epoch']


def training_config(config: dict) -> dict:
    supplied=config.get('training',{})
    if not isinstance(supplied,dict) or set(supplied)-set(DEFAULTS):
        raise ValueError('Invalid training configuration keys')
    result={**DEFAULTS,**supplied}
    for key in set(DEFAULTS)-{'learning_rate','seed'}:
        if isinstance(result[key],bool) or not isinstance(result[key],int) or result[key]<=0:
            raise ValueError(f'{key} must be a positive integer')
    if isinstance(result['seed'],bool) or not isinstance(result['seed'],int) or result['seed']<0:
        raise ValueError('seed must be a nonnegative integer')
    rate=result['learning_rate']
    if isinstance(rate,bool) or not isinstance(rate,(int,float)) or not math.isfinite(rate) or rate<=0:
        raise ValueError('learning_rate must be finite and positive')
    return result


def train_retrieval(prepared_dir: Path, output_dir: Path, config: dict) -> dict:
    cfg=training_config(config)
    prepared_dir,output_dir=Path(prepared_dir),Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError('Output directory is not empty; choose a new version directory')
    train=pd.read_parquet(prepared_dir/'train.parquet')
    validation=pd.read_parquet(prepared_dir/'validation.parquet')
    users=json.loads((prepared_dir/'user_mapping.json').read_text())
    channels=json.loads((prepared_dir/'channel_mapping.json').read_text())
    validate_mappings(train,users,channels)
    baseline=evaluate_popular(train,validation)
    provenance={name:checksum(prepared_dir/name) for name in ['train.parquet','validation.parquet','user_mapping.json','channel_mapping.json','data_manifest.json']}
    runtime={'python':platform.python_version(),'torch':str(torch.__version__), 'numpy':np.__version__, 'device':'cpu','threads':cfg['threads']}
    torch.set_num_threads(cfg['threads'])
    torch.use_deterministic_algorithms(True)
    random.seed(cfg['seed']); np.random.seed(cfg['seed']); torch.manual_seed(cfg['seed'])
    model=TwoTower(len(users),len(channels),cfg['dimension'])
    optimizer=torch.optim.Adam(model.parameters(),lr=cfg['learning_rate'],weight_decay=0)
    positive_users=torch.tensor(train.user_id.map(users).tolist(),dtype=torch.long)
    positive_channels=torch.tensor(train.channel_name.map(channels).tolist(),dtype=torch.long)
    positives={}
    for user,channel in zip(positive_users.tolist(),positive_channels.tolist()):
        positives.setdefault(user,set()).add(channel)
    eligible=torch.tensor([len(positives[user])<len(channels) for user in positive_users.tolist()])
    skipped=int((~eligible).sum())
    positive_users,positive_channels=positive_users[eligible],positive_channels[eligible]
    if not len(positive_users):
        raise ValueError('No trainable examples: every user has interacted with the entire training catalog')
    sampler=NegativeSampler(positives,len(channels),cfg['seed'],cfg['negative_count'])
    shuffle=torch.Generator().manual_seed(cfg['seed'])
    checkpoint_dir=output_dir/'checkpoints'; checkpoint_dir.mkdir(parents=True,exist_ok=True)
    history=[]
    start=time.perf_counter()
    for epoch in range(1,cfg['epochs']+1):
        model.train(); weighted_loss=0.; seen=0
        order=torch.randperm(len(positive_users),generator=shuffle)
        for offset in range(0,len(order),cfg['batch_size']):
            selected=order[offset:offset+cfg['batch_size']]
            user_batch,channel_batch=positive_users[selected],positive_channels[selected]
            negatives,mask=sampler.sample(user_batch.tolist())
            pos_scores=model(user_batch,channel_batch)
            neg_scores=model(user_batch[:,None].expand_as(negatives).reshape(-1),negatives.reshape(-1)).reshape_as(negatives)
            loss=pairwise_loss(pos_scores,neg_scores,mask)
            if not torch.isfinite(loss):
                raise ValueError(f'Non-finite training loss at epoch {epoch}')
            optimizer.zero_grad(set_to_none=True); loss.backward()
            if any(parameter.grad is not None and not torch.isfinite(parameter.grad).all() for parameter in model.parameters()):
                raise ValueError(f'Non-finite gradient at epoch {epoch}')
            optimizer.step()
            if any(not torch.isfinite(parameter).all() for parameter in model.parameters()):
                raise ValueError(f'Non-finite model weights at epoch {epoch}')
            weighted_loss+=float(loss.detach())*len(selected); seen+=len(selected)
        report=evaluate_retrieval(model,train,validation,users,channels,user_batch_size=cfg['evaluation_user_batch_size'])
        record={'epoch':epoch,'mean_training_loss':weighted_loss/seen,'validation':report,'elapsed_seconds':time.perf_counter()-start}
        history.append(record)
        torch.save({'model_state':model.state_dict(),'optimizer_state':optimizer.state_dict(),'epoch':epoch,
                    'config':cfg,'provenance':provenance,'runtime':runtime,'validation':report,
                    'torch_rng_state':torch.get_rng_state(),'shuffle_state':shuffle.get_state(),
                    'sampler_state':sampler.random_state(),'python_random_state':random.getstate()},
                   checkpoint_dir/f'epoch-{epoch:03d}.pt')
        write_json(output_dir/'training_history.json',history)
        print(json.dumps({'epoch':epoch,'loss':record['mean_training_loss'],'validation':report['metrics']},allow_nan=False),flush=True)
    selected_epoch=select_best_epoch(history)
    checkpoint=torch.load(checkpoint_dir/f'epoch-{selected_epoch:03d}.pt',map_location='cpu',weights_only=True)
    model.load_state_dict(checkpoint['model_state'])
    metadata={'num_users':len(users),'num_channels':len(channels),'dimension':cfg['dimension'],'architecture':'embedding-linear-no-bias-dot-product',
              'selected_epoch':selected_epoch,'training':cfg,'provenance':provenance,'runtime':runtime}
    selected_report=history[selected_epoch-1]['validation']
    comparison={'selected_epoch':selected_epoch,'popular':baseline,'two_tower':selected_report,'provenance':provenance,
                'training':cfg,'runtime':runtime,'trainable_examples':len(positive_users),'skipped_examples':skipped,
                'elapsed_seconds':time.perf_counter()-start,'test_evaluated':False}
    # Only a fully successful run publishes selected weights.
    torch.save(model.state_dict(),output_dir/'best_model.pt')
    write_json(output_dir/'model_config.json',metadata)
    write_json(output_dir/'validation_comparison.json',comparison)
    return comparison


def smoke_data(directory: Path) -> Path:
    rows=[]
    for user in range(4):
        for slot in range(2):
            rows.append([f'u{user}',f't{user}-{slot}',f'c{(user*2+slot)%6}',user*5+slot,user*5+slot])
        rows.append([f'u{user}',f'v{user}',f'c{(user*2)%6}',70+user,70+user])
    rows.append(['u0','end','c0',99,99])
    source=directory/'smoke.csv';pd.DataFrame(rows).to_csv(source,index=False,header=False)
    prepared=directory/'prepared';prepare_data(source,prepared)
    return prepared


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('config.yaml'))
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    if not args.smoke and args.prepared is None:
        parser.error('--prepared is required unless --smoke is selected')
    try:
        config=load_config(args.config)
        if args.smoke:
            config['training']={**config.get('training',{}),'epochs':2}
            with tempfile.TemporaryDirectory() as temp:
                result=train_retrieval(smoke_data(Path(temp)),args.output,config)
            result['synthetic_smoke_run']=True
            write_json(args.output/'validation_comparison.json',result)
        else:
            result=train_retrieval(args.prepared,args.output,config)
    except (ValueError,OSError,KeyError,RuntimeError,yaml.YAMLError) as exc:
        print(f'Training failed: {exc}',file=sys.stderr);return 1
    print(json.dumps({'selected_epoch':result['selected_epoch'],'popular':result['popular']['metrics'],'two_tower':result['two_tower']['metrics'],'test_evaluated':False},indent=2),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
