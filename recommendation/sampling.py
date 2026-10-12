"""Training-only uniform negatives, with bounded memory and no rejection loop."""
from collections import OrderedDict
from copy import deepcopy

import numpy as np
import torch


class NegativeSampler:
    def __init__(self, positives_by_user: dict[int, set[int]], num_channels: int, seed: int, count: int = 5):
        if num_channels <= 0 or count <= 0:
            raise ValueError('Catalog and negative count must be positive')
        self.positives = {u: set(values) for u, values in positives_by_user.items()}
        if any(c < 0 or c >= num_channels for values in self.positives.values() for c in values):
            raise ValueError('Positive channel index outside training catalog')
        self.num_channels, self.count = num_channels, count
        self.rng = np.random.default_rng(seed)
        self._catalog = np.arange(num_channels, dtype=np.int64)
        self._cache = OrderedDict()

    def _eligible(self, user: int) -> np.ndarray:
        if user not in self.positives:
            raise ValueError('User is absent from training positives')
        if user not in self._cache:
            self._cache[user] = np.setdiff1d(self._catalog, np.array(sorted(self.positives[user]), dtype=np.int64), assume_unique=True)
            if len(self._cache) > 128:
                self._cache.popitem(last=False)
        self._cache.move_to_end(user)
        return self._cache[user]

    def sample(self, user_indices) -> tuple[torch.Tensor, torch.Tensor]:
        negatives = np.zeros((len(user_indices), self.count), dtype=np.int64)
        mask = np.zeros_like(negatives, dtype=bool)
        for row, user in enumerate(user_indices):
            pool = self._eligible(int(user))
            size = min(self.count, len(pool))
            if size:
                negatives[row, :size] = self.rng.choice(pool, size=size, replace=False)
                mask[row, :size] = True
        return torch.from_numpy(negatives), torch.from_numpy(mask)

    def random_state(self) -> dict:
        return deepcopy(self.rng.bit_generator.state)

    def restore_random_state(self, state: dict) -> None:
        self.rng.bit_generator.state = deepcopy(state)
