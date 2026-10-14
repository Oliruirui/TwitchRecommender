"""Read-only, in-memory retrieval using a previously validated bundle."""
import logging

import faiss
import numpy as np
import torch

logger = logging.getLogger(__name__)


class RetrievalEngine:
    def __init__(self, bundle: dict):
        self.model = bundle['model']
        self.index = bundle['index']
        self.users = bundle['user_mapping']
        self.version = bundle['manifest']['model_version']
        self.channels = [name for name, _ in sorted(bundle['channel_mapping'].items(), key=lambda x: x[1])]
        self.popular = bundle['popular_channels']

    def _result(self, method, reason, items):
        return {'model_version': self.version, 'method': method,
                'fallback_reason': reason, 'items': items}

    def _fallback(self, k, reason):
        return self._result('popular', reason, [
            {'channel_id': item['channel_id'], 'channel_name': item['channel_name'], 'retrieval_score': None}
            for item in self.popular[:k]])

    def recommend(self, user_id: str, k: int) -> dict:
        # HTTP validation is separate; guard direct callers against invalid search sizes too.
        if type(k) is not int or not 1 <= k <= 200:
            raise ValueError('k must be an integer from 1 to 200')
        k = min(k, len(self.channels))
        if user_id not in self.users:
            return self._fallback(k, 'unknown_user')
        try:
            with torch.inference_mode():
                query = self.model.encode_users(torch.tensor([self.users[user_id]], dtype=torch.long))
                query = np.ascontiguousarray(query.numpy(), dtype=np.float32)
            if query.shape != (1, self.index.d) or not np.isfinite(query).all():
                raise ValueError('Invalid user vector')
            # OpenMP settings are thread-local: configure the request's search thread.
            faiss.omp_set_num_threads(1)
            scores, ids = self.index.search(query, k)
            if (scores.shape != (1, k) or ids.shape != (1, k)
                    or not np.issubdtype(ids.dtype, np.integer)
                    or not np.isfinite(scores).all()
                    or np.any(ids < 0) or np.any(ids >= len(self.channels))
                    or len(set(ids[0].tolist())) != k):
                raise ValueError('Invalid index search result')
            ranked = sorted(zip(ids[0].tolist(), scores[0].tolist()), key=lambda x: (-x[1], x[0]))
            items = [{'channel_id': str(i), 'channel_name': self.channels[i], 'retrieval_score': float(score)}
                     for i, score in ranked]
            return self._result('two_tower', None, items)
        except Exception:
            logger.exception('Personalized retrieval failed; returning popularity fallback')
            return self._fallback(k, 'retrieval_error')
