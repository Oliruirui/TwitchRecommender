"""Local retrieval HTTP API. Start with Uvicorn through recommendation.run."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, FiniteFloat, StringConstraints

from recommendation.export import load_bundle
from recommendation.retrieval import RetrievalEngine

logger = logging.getLogger(__name__)
UserID = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128)]


class RecommendationRequest(BaseModel):
    user_id: UserID
    k: Annotated[int, Field(strict=True, ge=1, le=200)] = 10


class RecommendationItem(BaseModel):
    channel_id: str
    channel_name: str
    retrieval_score: FiniteFloat | None


class RecommendationResponse(BaseModel):
    request_id: str
    model_version: str
    method: Literal['two_tower', 'popular']
    fallback_reason: Literal['unknown_user', 'retrieval_error'] | None
    items: list[RecommendationItem]


def create_app(bundle_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application):
        application.state.engine = None
        try:
            configured = bundle_dir if bundle_dir is not None else os.environ.get('RECOMMENDER_BUNDLE_DIR')
            if not configured:
                raise ValueError('RECOMMENDER_BUNDLE_DIR is required')
            torch.set_num_threads(1)
            engine = RetrievalEngine(load_bundle(Path(configured)))
            warmup = engine.recommend(next(iter(engine.users)), 1)
            if warmup['method'] != 'two_tower':
                raise ValueError('Personalized retrieval warmup failed')
            application.state.engine = engine
        except Exception:
            logger.exception('Bundle startup failed; service remains unready')
        try:
            yield
        finally:
            application.state.engine = None

    application = FastAPI(title='Twitch channel retrieval', version='1.0', lifespan=lifespan)
    application.state.engine = None

    @application.get('/health/live')
    def live():
        return {'status': 'alive'}

    @application.get('/health/ready')
    def ready(request: Request):
        engine = request.app.state.engine
        if engine is None:
            return JSONResponse(status_code=503, content={'status': 'not_ready'})
        return {'status': 'ready', 'model_version': engine.version}

    @application.post('/v1/recommendations', response_model=RecommendationResponse)
    def recommendations(body: RecommendationRequest, request: Request):
        engine = request.app.state.engine
        if engine is None:
            raise HTTPException(status_code=503, detail='recommendation service unavailable')
        return {'request_id': str(uuid4()), **engine.recommend(body.user_id, body.k)}

    return application


app = create_app()
