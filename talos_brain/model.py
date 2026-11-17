"""The brain v0: eyes (CNN) + body sense (MLP) -> short-term memory (GRU) -> actor & critic."""
from __future__ import annotations

import torch
import torch.nn as nn
from torch.distributions import Normal

from .env import IMAGE_HW, PROPRIO_DIM

ACTION_DIM = 4  # forward, strafe, turn, look


class Brain(nn.Module):
    def __init__(self, hidden: int = 256, image_hw=IMAGE_HW, proprio_dim: int = PROPRIO_DIM):
        super().__init__()
        self.hidden, self.image_hw, self.proprio_dim = hidden, tuple(image_hw), proprio_dim
        conv = nn.Sequential(
            nn.Conv2d(3, 32, 5, stride=2, padding=2), nn.ReLU(),   # 60x80 -> 30x40
            nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(),  # -> 15x20
            nn.Conv2d(64, 64, 3, stride=2, padding=1), nn.ReLU(),  # -> 8x10
            nn.Flatten(),
        )
        with torch.no_grad():
            flat = conv(torch.zeros(1, 3, *self.image_hw)).shape[1]
        self.vision = nn.Sequential(conv, nn.Linear(flat, 256), nn.ReLU())
        self.body = nn.Sequential(nn.Linear(proprio_dim, 64), nn.ReLU())
        self.memory = nn.GRU(256 + 64, hidden)
        self.actor = nn.Linear(hidden, ACTION_DIM)
        self.critic = nn.Linear(hidden, 1)
        self.log_std = nn.Parameter(torch.full((ACTION_DIM,), -0.5))
        nn.init.orthogonal_(self.actor.weight, 0.01)
        nn.init.zeros_(self.actor.bias)
        nn.init.orthogonal_(self.critic.weight, 1.0)

    def initial_state(self, n: int, device="cpu"):
        return torch.zeros(1, n, self.hidden, device=device)

    def forward(self, images, proprio, h, starts):
        """images [T,N,3,H,W] uint8, proprio [T,N,7], h [1,N,hid], starts [T,N] (1 = episode began here)."""
        T, N = images.shape[:2]
        x = self.vision(images.reshape(T * N, *images.shape[2:]).float() / 255.0)
        x = torch.cat([x, self.body(proprio.reshape(T * N, -1).float())], -1).reshape(T, N, -1)
        outs = []
        for t in range(T):  # step-wise so the memory is zeroed exactly at episode boundaries
            h = h * (1.0 - starts[t].float()).view(1, N, 1)
            o, h = self.memory(x[t:t + 1], h)
            outs.append(o)
        z = torch.cat(outs, 0)
        mean = torch.tanh(self.actor(z))
        dist = Normal(mean, self.log_std.exp().expand_as(mean))
        return dist, self.critic(z).squeeze(-1), h
