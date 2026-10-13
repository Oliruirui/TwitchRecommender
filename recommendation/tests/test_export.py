import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch


def fixture(tmp_path, tied=False):
    from recommendation.model import TwoTower
    from recommendation.prepare_data import prepare_data,write_json
    from recommendation.evaluate import checksum
    rows=[['u','a','a',0,0],['u','b','b',10,10],['v','c','c',20,20],
          ['u','d','b',70,70],['v','e','c',80,80],['u','f','a',99,99]]
    source=tmp_path/'raw.csv';pd.DataFrame(rows).to_csv(source,header=False,index=False)
    prepared=tmp_path/'prepared';prepare_data(source,prepared)
    model_dir=tmp_path/'model';model_dir.mkdir()
    model=TwoTower(2,3,2)
    with torch.no_grad():
        model.user_embedding.weight.copy_(torch.tensor([[1.,0.],[0.,1.]]))
        model.channel_embedding.weight.copy_(torch.tensor([[0.,0.],[2.,0.],[1.,0.]]))
        model.user_projection.weight.copy_(torch.eye(2));model.channel_projection.weight.copy_(torch.eye(2))
        if tied:model.channel_embedding.weight.fill_(1.)
    torch.save(model.state_dict(),model_dir/'best_model.pt')
    write_json(model_dir/'model_config.json',{'architecture':'embedding-linear-no-bias-dot-product','num_users':2,'num_channels':3,'dimension':2,'selected_epoch':30,
        'provenance':{name:checksum(prepared/name) for name in ['train.parquet','validation.parquet','user_mapping.json','channel_mapping.json','data_manifest.json']}})
    return model_dir,prepared,model


def test_bundle_roundtrip_scores_and_index_mapping(tmp_path):
    from recommendation.export import export_bundle,load_bundle
    model_dir,prepared,model=fixture(tmp_path)
    out=tmp_path/'v1';manifest=export_bundle(model_dir,prepared,out,'v1')
    bundle=load_bundle(out)
    query=model.encode_users(torch.tensor([0])).detach().numpy()
    scores,indices=bundle['index'].search(query,3)
    assert indices.tolist()==[[1,2,0]]
    np.testing.assert_allclose(scores,[[2.,1.,0.]],rtol=1e-6,atol=1e-6)
    np.testing.assert_allclose(bundle['channel_vectors'],[[0.,0.],[2.,0.],[1.,0.]])
    assert bundle['channel_mapping']=={'a':0,'b':1,'c':2}
    assert len(bundle['popular_channels'])==3
    assert manifest['model_version']=='v1' and manifest['selected_epoch']==30
    assert manifest['index']['type']=='IndexFlatIP'
    assert manifest['score']=='dot_product' and not manifest['normalized']
    reloaded=bundle['model'].encode_users(torch.tensor([0])).detach().numpy()
    np.testing.assert_array_equal(query,reloaded)
    assert set(manifest['file_checksums'])=={p.name for p in out.iterdir()}-{'manifest.json'}


def test_tied_scores_allow_any_order_and_catalog_smaller_than_k(tmp_path):
    from recommendation.export import export_bundle,load_bundle
    model_dir,prepared,_=fixture(tmp_path,tied=True)
    out=tmp_path/'v1';export_bundle(model_dir,prepared,out,'v1')
    bundle=load_bundle(out)
    query=bundle['model'].encode_users(torch.tensor([0])).detach().numpy()
    scores,ids=bundle['index'].search(query,min(10,bundle['index'].ntotal))
    assert set(ids[0])=={0,1,2}
    np.testing.assert_allclose(scores,[[1.,1.,1.]])


def test_source_mapping_mismatch_is_rejected_before_publication(tmp_path):
    from recommendation.export import export_bundle
    model_dir,prepared,_=fixture(tmp_path)
    (prepared/'channel_mapping.json').write_text('{"a":1,"b":0,"c":2}')
    with pytest.raises(ValueError,match='fingerprint'):
        export_bundle(model_dir,prepared,tmp_path/'out','v1')
    assert not (tmp_path/'out').exists()


def test_nonfinite_model_is_rejected(tmp_path):
    from recommendation.export import export_bundle
    model_dir,prepared,model=fixture(tmp_path)
    with torch.no_grad():model.user_embedding.weight[0,0]=float('nan')
    torch.save(model.state_dict(),model_dir/'best_model.pt')
    with pytest.raises(ValueError,match='finite'):
        export_bundle(model_dir,prepared,tmp_path/'out','v1')
    assert not (tmp_path/'out').exists()


def test_payload_corruption_is_detected_before_faiss_read(tmp_path,monkeypatch):
    import faiss
    from recommendation.export import export_bundle,load_bundle
    model_dir,prepared,_=fixture(tmp_path)
    out=tmp_path/'v1';export_bundle(model_dir,prepared,out,'v1')
    (out/'channels.faiss').write_bytes(b'corrupted')
    monkeypatch.setattr(faiss,'read_index',lambda *a:pytest.fail('Corrupt payload reached native reader'))
    with pytest.raises(ValueError,match='checksum'):
        load_bundle(out)


def test_existing_output_and_failed_export_leave_no_partial_bundle(tmp_path,monkeypatch):
    import faiss
    from recommendation.export import export_bundle
    model_dir,prepared,_=fixture(tmp_path)
    existing=tmp_path/'existing';existing.mkdir();(existing/'keep').write_text('original')
    with pytest.raises(ValueError,match='exist'):
        export_bundle(model_dir,prepared,existing,'v1')
    assert (existing/'keep').read_text()=='original'
    monkeypatch.setattr(faiss,'write_index',lambda *a:(_ for _ in ()).throw(RuntimeError('disk failure')))
    with pytest.raises(RuntimeError,match='disk failure'):
        export_bundle(model_dir,prepared,tmp_path/'failed','v1')
    assert not (tmp_path/'failed').exists()
    assert not list(tmp_path.glob('.failed-*'))


def test_launcher_runs_torch_and_faiss_in_one_process():
    import subprocess,sys
    code = ('import torch,faiss,numpy as np; '
            'torch.set_num_threads(1); '
            'x=np.array([[1,2],[3,4]],dtype="float32"); '
            'index=faiss.IndexFlatIP(2); index.add(x); '
            'scores,ids=index.search(x,1); '
            'assert ids.tolist()==[[1],[1]]; '
            'assert (torch.ones(2)@torch.ones(2)).item()==2; print("native-runtime-ok")')
    result = subprocess.run([sys.executable,'-m','recommendation.run','-c',code],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert 'native-runtime-ok' in result.stdout


def test_loader_rejects_vectors_not_generated_by_bundled_model(tmp_path):
    import faiss
    from recommendation.export import export_bundle,load_bundle
    from recommendation.evaluate import checksum
    model_dir,prepared,_=fixture(tmp_path)
    out=tmp_path/'v1';export_bundle(model_dir,prepared,out,'v1')
    vectors=np.load(out/'channel_vectors.npy');vectors[0]=[9.,9.]
    np.save(out/'channel_vectors.npy',vectors)
    index=faiss.IndexFlatIP(2);index.add(vectors);faiss.write_index(index,str(out/'channels.faiss'))
    manifest=json.loads((out/'manifest.json').read_text())
    for name in ['channel_vectors.npy','channels.faiss']:
        manifest['file_checksums'][name]=checksum(out/name)
    (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='model'):
        load_bundle(out)


def test_loader_rejects_wrong_index_metric(tmp_path):
    import faiss
    from recommendation.export import export_bundle,load_bundle
    from recommendation.evaluate import checksum
    model_dir,prepared,_=fixture(tmp_path)
    out=tmp_path/'v1';export_bundle(model_dir,prepared,out,'v1')
    index=faiss.IndexFlatL2(2);index.add(np.load(out/'channel_vectors.npy'))
    faiss.write_index(index,str(out/'channels.faiss'))
    manifest=json.loads((out/'manifest.json').read_text());manifest['file_checksums']['channels.faiss']=checksum(out/'channels.faiss')
    (out/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='Index'):
        load_bundle(out)


def test_export_cli_does_not_read_held_out_data(tmp_path):
    import subprocess,sys
    from recommendation.export import load_bundle
    model_dir,prepared,_=fixture(tmp_path)
    (prepared/'validation.parquet').write_bytes(b'not read by export')
    (prepared/'test.parquet').write_bytes(b'not read by export')
    out=tmp_path/'v1'
    result=subprocess.run([sys.executable,'-m','recommendation.run','-m','recommendation.export',
        '--model',str(model_dir),'--prepared',str(prepared),'--output',str(out),'--version','v1'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['index']['count']==3
    assert load_bundle(out)['manifest']['selected_epoch']==30
