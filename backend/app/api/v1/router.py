from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.export import router as export_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.profiles import router as profiles_router
from app.api.v1.proposals import router as proposals_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(datasets_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(profiles_router)
api_v1_router.include_router(proposals_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(export_router)
