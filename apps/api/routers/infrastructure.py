from fastapi import APIRouter

from packages.infrastructure import load_service_registry

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/infrastructure-services")
def infrastructure_services() -> dict[str, object]:
    services = load_service_registry()
    return {"items": services, "total": len(services), "contains_secrets": False}
