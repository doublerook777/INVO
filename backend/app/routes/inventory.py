"""Read endpoints for the dashboard. Dev A owns this file."""
from fastapi import APIRouter

from .. import db
from ..config import DEMO_SHOP_ID
from ..core import inventory as inv
from ..core import reorder

router = APIRouter(prefix="/api", tags=["inventory"])


@router.get("/inventory")
def get_inventory(shop_id: int = DEMO_SHOP_ID):
    shop = db.query_one("SELECT id, name FROM shops WHERE id = ?", (shop_id,))
    return {"shop": shop, "items": inv.list_inventory(shop_id)}


@router.get("/alerts")
def get_alerts(shop_id: int = DEMO_SHOP_ID):
    return {"alerts": reorder.alerts(shop_id)}
