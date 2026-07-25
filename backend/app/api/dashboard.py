"""Dashboard API — read-only aggregation of platform state."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.dashboard.engine import DashboardController
from app.services.dashboard.service import DashboardService

router = APIRouter()


def get_controller() -> DashboardController:
    return DashboardController()


async def get_service(session: AsyncSession = Depends(get_db)) -> DashboardService:
    return DashboardService(session)


# --- Snapshot ---

@router.get("/snapshot")
async def get_snapshot(controller: DashboardController = Depends(get_controller)):
    """Generate a full platform state snapshot."""
    return controller.snapshot(
        system=controller.system_overview(),
        trading=controller.trading_overview(),
        scanner=controller.scanner_dashboard(),
        optimization=controller.optimization_dashboard(),
        monitoring=controller.monitoring_dashboard(),
        portfolio=controller.portfolio_dashboard(),
    )


@router.post("/snapshot")
async def save_snapshot(service: DashboardService = Depends(get_service),
                        controller: DashboardController = Depends(get_controller)):
    """Persist current snapshot."""
    snap = controller.snapshot(
        system=controller.system_overview(),
        trading=controller.trading_overview(),
        scanner=controller.scanner_dashboard(),
        optimization=controller.optimization_dashboard(),
        monitoring=controller.monitoring_dashboard(),
        portfolio=controller.portfolio_dashboard(),
    )
    result = await service.save_snapshot("full", snap)
    return result


@router.get("/snapshot/history")
async def snapshot_history(
    snapshot_type: str | None = Query(None, description="Filter by snapshot type"),
    limit: int = Query(50, ge=1, le=200),
    service: DashboardService = Depends(get_service),
):
    """List saved snapshots."""
    return await service.get_snapshots(snapshot_type=snapshot_type, limit=limit)


@router.get("/snapshot/{snapshot_id}")
async def get_saved_snapshot(snapshot_id: int, service: DashboardService = Depends(get_service)):
    """Retrieve a specific saved snapshot."""
    snap = await service.get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


@router.delete("/snapshot/{snapshot_id}")
async def delete_saved_snapshot(snapshot_id: int, service: DashboardService = Depends(get_service)):
    """Delete a saved snapshot."""
    deleted = await service.delete_snapshot(snapshot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"status": "deleted", "snapshot_id": snapshot_id}


# --- Widgets ---

@router.get("/widgets")
async def get_widgets(controller: DashboardController = Depends(get_controller)):
    """Generate default dashboard widget set."""
    snap = controller.snapshot(
        system=controller.system_overview(),
        trading=controller.trading_overview(),
        scanner=controller.scanner_dashboard(),
        optimization=controller.optimization_dashboard(),
        monitoring=controller.monitoring_dashboard(),
        portfolio=controller.portfolio_dashboard(),
    )
    return [w.to_dict() for w in controller.build_widgets(snap)]


# --- Statistics ---

@router.get("/statistics")
async def get_dashboard_statistics(controller: DashboardController = Depends(get_controller)):
    """Compute aggregate dashboard-level statistics."""
    snap = controller.snapshot(
        system=controller.system_overview(),
        trading=controller.trading_overview(),
        scanner=controller.scanner_dashboard(),
        optimization=controller.optimization_dashboard(),
        monitoring=controller.monitoring_dashboard(),
        portfolio=controller.portfolio_dashboard(),
    )
    return controller.statistics(snap)


# --- Timeline ---

@router.get("/timeline")
async def get_timeline(
    limit: int = Query(50, ge=1, le=200),
    controller: DashboardController = Depends(get_controller),
):
    """Build unified activity timeline (empty if no service data provided — use POST)."""
    return controller.activity_timeline(events=[], limit=limit)


@router.post("/timeline")
async def post_timeline(
    events: list[dict],
    limit: int = Query(50, ge=1, le=200),
    controller: DashboardController = Depends(get_controller),
):
    """Build timeline from provided events."""
    return controller.activity_timeline(events=events, limit=limit)


# --- Subsystem Summaries ---

@router.get("/system")
async def system_overview(controller: DashboardController = Depends(get_controller)):
    """System overview widget data."""
    return controller.system_overview()


@router.get("/trading")
async def trading_overview(controller: DashboardController = Depends(get_controller)):
    """Trading overview widget data."""
    return controller.trading_overview()


@router.get("/scanner")
async def scanner_summary(controller: DashboardController = Depends(get_controller)):
    """Scanner dashboard widget data."""
    return controller.scanner_dashboard()


@router.get("/optimization")
async def optimization_summary(controller: DashboardController = Depends(get_controller)):
    """Optimization dashboard widget data."""
    return controller.optimization_dashboard()


@router.get("/monitoring")
async def monitoring_summary(controller: DashboardController = Depends(get_controller)):
    """Monitoring dashboard widget data."""
    return controller.monitoring_dashboard()


@router.get("/portfolio")
async def portfolio_summary(controller: DashboardController = Depends(get_controller)):
    """Portfolio dashboard widget data."""
    return controller.portfolio_dashboard()


# --- Preferences ---

@router.post("/preferences")
async def set_preference(
    user_id: int = Query(0, description="User ID"),
    key: str = Query(..., description="Preference key"),
    value: str = Query("", description="Preference value"),
    service: DashboardService = Depends(get_service),
):
    """Set a dashboard user preference."""
    return await service.set_preference(user_id=user_id, key=key, value=value)


@router.get("/preferences/{user_id}")
async def get_user_preferences(user_id: int, service: DashboardService = Depends(get_service)):
    """Get all preferences for a user."""
    return await service.get_preferences(user_id)


@router.get("/preferences/{user_id}/{key}")
async def get_preference(user_id: int, key: str, service: DashboardService = Depends(get_service)):
    """Get a specific preference."""
    pref = await service.get_preference(user_id, key)
    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")
    return pref


@router.delete("/preferences/{user_id}/{key}")
async def delete_preference(user_id: int, key: str, service: DashboardService = Depends(get_service)):
    """Delete a preference."""
    deleted = await service.delete_preference(user_id, key)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preference not found")
    return {"status": "deleted"}


# --- Layouts ---

@router.post("/layouts")
async def save_layout(
    user_id: int = Query(0),
    layout_name: str = Query("default"),
    widgets: list[dict] | None = None,
    service: DashboardService = Depends(get_service),
):
    """Save a dashboard layout."""
    return await service.save_layout(user_id, layout_name, widgets or [])


@router.get("/layouts/{user_id}")
async def get_layouts(user_id: int, service: DashboardService = Depends(get_service)):
    """Get all layouts for a user."""
    return await service.get_layouts(user_id)


@router.get("/layouts/{user_id}/{layout_name}")
async def get_layout(user_id: int, layout_name: str, service: DashboardService = Depends(get_service)):
    """Get a specific layout."""
    layout = await service.get_layout(user_id, layout_name)
    if not layout:
        raise HTTPException(status_code=404, detail="Layout not found")
    return layout


@router.post("/layouts/{user_id}/{layout_name}/activate")
async def activate_layout(user_id: int, layout_name: str, service: DashboardService = Depends(get_service)):
    """Set a layout as active."""
    ok = await service.set_active_layout(user_id, layout_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Layout not found")
    return {"status": "activated", "layout_name": layout_name}


@router.delete("/layouts/{user_id}/{layout_name}")
async def delete_layout(user_id: int, layout_name: str, service: DashboardService = Depends(get_service)):
    """Delete a layout."""
    deleted = await service.delete_layout(user_id, layout_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Layout not found")
    return {"status": "deleted"}
