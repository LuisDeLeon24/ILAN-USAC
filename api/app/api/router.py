from fastapi import APIRouter

from app.api.routes import agent, alerts, auth, cameras, devices, events, exclusions, metrics, public, sensors, sites, users, zones

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(sites.router)
api_router.include_router(cameras.router)
api_router.include_router(sensors.router)
api_router.include_router(zones.router)
api_router.include_router(exclusions.router)
api_router.include_router(devices.router)
api_router.include_router(events.router)
api_router.include_router(alerts.router)
api_router.include_router(metrics.router)
api_router.include_router(agent.router)
api_router.include_router(public.router)
