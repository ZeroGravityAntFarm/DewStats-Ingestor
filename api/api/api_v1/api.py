from fastapi import APIRouter
from api.api_v1.endpoints import stats
api_router = APIRouter()
api_router.include_router(stats.router, prefix="/api_v1", tags=["stat-data"])
