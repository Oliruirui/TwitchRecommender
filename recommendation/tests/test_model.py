import torch


def test_pair_score_and_encoding_shapes():
    from recommendation.model import TwoTower
    model = TwoTower(2, 3, 2)
    with torch.no_grad():
        model.user_embedding.weight[0] = torch.tensor([1., 2.])
        model.channel_embedding.weight[1] = torch.tensor([3., 4.])
        model.user_projection.weight.copy_(torch.eye(2))
        model.channel_projection.weight.copy_(torch.eye(2))
    assert model.encode_users(torch.tensor([0, 1])).shape == (2, 2)
    assert model.encode_channels(torch.tensor([0, 1, 2])).shape == (3, 2)
    assert model(torch.tensor([0]), torch.tensor([1])).tolist() == [11.]


def test_gradients_reach_both_towers():
    from recommendation.model import TwoTower
    torch.manual_seed(42)
    model = TwoTower(2, 3)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001)
    before = {k: v.clone() for k, v in model.state_dict().items()}
    model(torch.tensor([0, 1]), torch.tensor([1, 2])).square().sum().backward()
    optimizer.step()
    for name, weight in model.state_dict().items():
        assert not torch.equal(before[name], weight), name
