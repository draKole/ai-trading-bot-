"""Dashboard Persistence Service."""

from __future__ import annotations
from typing import TYPE_CHECKING
import json
import structlog
from sqlalchemy import select, desc, delete
from app.models.dashboard import DashboardSnapshot, DashboardPreference, DashboardLayout

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Snapshots ---

    async def save_snapshot(self, snapshot_type: str, data: dict) -> dict:
        s = DashboardSnapshot(
            snapshot_type=snapshot_type,
            data_json=json.dumps(data, default=str),
        )
        self.session.add(s)
        await self.session.flush()
        return {"id": s.id, "snapshot_type": s.snapshot_type, "created_at": s.created_at.isoformat() if s.created_at else None}

    async def get_snapshots(self, snapshot_type: str | None = None, limit: int = 50) -> list[dict]:
        q = select(DashboardSnapshot).order_by(desc(DashboardSnapshot.created_at))
        if snapshot_type:
            q = q.where(DashboardSnapshot.snapshot_type == snapshot_type)
        result = await self.session.execute(q.limit(limit))
        return [
            {"id": s.id, "snapshot_type": s.snapshot_type,
             "data": json.loads(s.data_json) if s.data_json else {},
             "created_at": s.created_at.isoformat() if s.created_at else None}
            for s in result.scalars().all()
        ]

    async def get_snapshot(self, snapshot_id: int) -> dict | None:
        result = await self.session.execute(select(DashboardSnapshot).where(DashboardSnapshot.id == snapshot_id))
        s = result.scalar_one_or_none()
        if not s:
            return None
        return {"id": s.id, "snapshot_type": s.snapshot_type,
                "data": json.loads(s.data_json) if s.data_json else {},
                "created_at": s.created_at.isoformat() if s.created_at else None}

    async def delete_snapshot(self, snapshot_id: int) -> bool:
        result = await self.session.execute(select(DashboardSnapshot).where(DashboardSnapshot.id == snapshot_id))
        s = result.scalar_one_or_none()
        if s:
            await self.session.delete(s)
            await self.session.flush()
            return True
        return False

    # --- Preferences ---

    async def set_preference(self, user_id: int, key: str, value: str) -> dict:
        result = await self.session.execute(
            select(DashboardPreference).where(
                DashboardPreference.user_id == user_id,
                DashboardPreference.preference_key == key,
            )
        )
        pref = result.scalar_one_or_none()
        if pref:
            pref.preference_value = value
        else:
            pref = DashboardPreference(user_id=user_id, preference_key=key, preference_value=value)
            self.session.add(pref)
        await self.session.flush()
        return {"user_id": user_id, "key": key, "value": value}

    async def get_preferences(self, user_id: int) -> list[dict]:
        result = await self.session.execute(
            select(DashboardPreference).where(DashboardPreference.user_id == user_id)
        )
        return [{"key": p.preference_key, "value": p.preference_value}
                for p in result.scalars().all()]

    async def get_preference(self, user_id: int, key: str) -> dict | None:
        result = await self.session.execute(
            select(DashboardPreference).where(
                DashboardPreference.user_id == user_id,
                DashboardPreference.preference_key == key,
            )
        )
        p = result.scalar_one_or_none()
        if not p:
            return None
        return {"key": p.preference_key, "value": p.preference_value}

    async def delete_preference(self, user_id: int, key: str) -> bool:
        result = await self.session.execute(
            select(DashboardPreference).where(
                DashboardPreference.user_id == user_id,
                DashboardPreference.preference_key == key,
            )
        )
        p = result.scalar_one_or_none()
        if p:
            await self.session.delete(p)
            await self.session.flush()
            return True
        return False

    # --- Layouts ---

    async def save_layout(self, user_id: int, layout_name: str, widgets: list[dict]) -> dict:
        result = await self.session.execute(
            select(DashboardLayout).where(
                DashboardLayout.user_id == user_id,
                DashboardLayout.layout_name == layout_name,
            )
        )
        layout = result.scalar_one_or_none()
        if layout:
            layout.widgets_json = json.dumps(widgets)
        else:
            layout = DashboardLayout(
                user_id=user_id, layout_name=layout_name,
                widgets_json=json.dumps(widgets),
            )
            self.session.add(layout)
        await self.session.flush()
        return {"id": layout.id, "user_id": user_id, "layout_name": layout_name}

    async def get_layouts(self, user_id: int) -> list[dict]:
        result = await self.session.execute(
            select(DashboardLayout).where(DashboardLayout.user_id == user_id)
        )
        return [
            {"id": l.id, "layout_name": l.layout_name,
             "widgets": json.loads(l.widgets_json) if l.widgets_json else [],
             "is_active": bool(l.is_active)}
            for l in result.scalars().all()
        ]

    async def get_layout(self, user_id: int, layout_name: str) -> dict | None:
        result = await self.session.execute(
            select(DashboardLayout).where(
                DashboardLayout.user_id == user_id,
                DashboardLayout.layout_name == layout_name,
            )
        )
        l = result.scalar_one_or_none()
        if not l:
            return None
        return {"id": l.id, "layout_name": l.layout_name,
                "widgets": json.loads(l.widgets_json) if l.widgets_json else [],
                "is_active": bool(l.is_active)}

    async def set_active_layout(self, user_id: int, layout_name: str) -> bool:
        # Deactivate all layouts first
        all_layouts = await self.session.execute(
            select(DashboardLayout).where(DashboardLayout.user_id == user_id)
        )
        for layout in all_layouts.scalars().all():
            layout.is_active = 0
        # Activate target
        result = await self.session.execute(
            select(DashboardLayout).where(
                DashboardLayout.user_id == user_id,
                DashboardLayout.layout_name == layout_name,
            )
        )
        target = result.scalar_one_or_none()
        if target:
            target.is_active = 1
            await self.session.flush()
            return True
        return False

    async def delete_layout(self, user_id: int, layout_name: str) -> bool:
        result = await self.session.execute(
            select(DashboardLayout).where(
                DashboardLayout.user_id == user_id,
                DashboardLayout.layout_name == layout_name,
            )
        )
        l = result.scalar_one_or_none()
        if l:
            await self.session.delete(l)
            await self.session.flush()
            return True
        return False
