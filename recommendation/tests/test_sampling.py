import torch


def test_excludes_every_positive_and_samples_unique_negatives():
    from recommendation.sampling import NegativeSampler
    sampler = NegativeSampler({0: {0, 1}, 1: {2}}, 10, 42)
    negatives, mask = sampler.sample([0, 1])
    assert negatives.shape == mask.shape == (2, 5)
    for row, user in enumerate([0, 1]):
        values = negatives[row][mask[row]].tolist()
        assert len(values) == len(set(values)) == 5
        assert not set(values) & sampler.positives[user]


def test_small_and_empty_pools_terminate_and_mask_padding():
    from recommendation.sampling import NegativeSampler
    sampler = NegativeSampler({0: {0, 1}, 1: {0, 1, 2}}, 3, 42)
    negatives, mask = sampler.sample([0, 1])
    assert negatives[0][mask[0]].tolist() == [2]
    assert mask.sum(dim=1).tolist() == [1, 0]
    assert ((negatives >= 0) & (negatives < 3)).all()


def test_seed_and_random_state_are_reproducible():
    from recommendation.sampling import NegativeSampler
    left = NegativeSampler({0: {1}}, 20, 42)
    right = NegativeSampler({0: {1}}, 20, 42)
    assert torch.equal(left.sample([0])[0], right.sample([0])[0])
    state = left.random_state()
    expected = left.sample([0])[0]
    right.restore_random_state(state)
    assert torch.equal(expected, right.sample([0])[0])
