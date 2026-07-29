from fastapi import APIRouter

from app.plugins.manager import plugin_manager


router = APIRouter()


@router.get("/plugins")
def list_plugins():

    return plugin_manager.plugins()