"""
Map Agent Route
Endpoint for map searches using natural language prompts
"""
import httpx
import json
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from src.core.settings import PLACEMAKING_API_URL
from src.schemas.agent import MapAgentRequest, MapAgentResponse
from src.agents.map_agent import run_map_agent, create_map_agent, _extract_places_from_messages

router = APIRouter()


@router.post("/map", response_model=MapAgentResponse, summary="Search places with Map Agent")
async def map_agent_search(request: MapAgentRequest):
    """
    Searches for places on the map using a natural language prompt.
    """
    try:
        result = await run_map_agent(request.prompt, request.model_name)
        return MapAgentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while running the agent: {str(e)}")
