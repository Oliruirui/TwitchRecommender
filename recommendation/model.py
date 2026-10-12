"""Small ID-based two-tower model shared by training and future serving."""
import torch
from torch import nn


class TwoTower(nn.Module):
    def __init__(self, num_users: int, num_channels: int, dimension: int = 32):
        super().__init__()
        if min(num_users, num_channels, dimension) <= 0:
            raise ValueError('Model dimensions and vocabulary sizes must be positive')
        self.user_embedding = nn.Embedding(num_users, dimension)
        self.channel_embedding = nn.Embedding(num_channels, dimension)
        self.user_projection = nn.Linear(dimension, dimension, bias=False)
        self.channel_projection = nn.Linear(dimension, dimension, bias=False)

    def encode_users(self, ids: torch.Tensor) -> torch.Tensor:
        return self.user_projection(self.user_embedding(ids))

    def encode_channels(self, ids: torch.Tensor) -> torch.Tensor:
        return self.channel_projection(self.channel_embedding(ids))

    def forward(self, user_ids: torch.Tensor, channel_ids: torch.Tensor) -> torch.Tensor:
        return (self.encode_users(user_ids) * self.encode_channels(channel_ids)).sum(dim=-1)
