"""
Map Agent Route
Endpoint for map searches using natural language prompts
"""
from fastapi import APIRouter, HTTPException
from src.schemas.agent import MapAgentRequest, MapAgentResponse
from src.agents.map_agent import run_map_agent

router = APIRouter()


@router.post("/map", response_model=MapAgentResponse, summary="Search places with Map Agent")
async def map_agent_search(request: MapAgentRequest):
    """
    Searches for places on the map using a natural language prompt.
    Examples:
    - "List the best restaurants in Kadıköy"
    - "Where are the open cafes in Beşiktaş?"
    - "Find pizza restaurants near Taksim"
    - "Turkish cuisine restaurants with 4+ stars in Üsküdar"
    """
    try:
        result = await run_map_agent(request.prompt, request.model_name)
        return MapAgentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while running the agent: {str(e)}")
