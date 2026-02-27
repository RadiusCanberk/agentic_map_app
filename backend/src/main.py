import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from src.routes import search, agent, models

app = FastAPI(
    title="Agentic Map API",
    description="Map search API using natural language prompts with LangChain Map Agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    content = {"message": "healthy"}
    return JSONResponse(status_code=200, content=content)


app.include_router(search.router, prefix="/search", tags=["Search"])
app.include_router(agent.router, prefix="/agent", tags=["Map Agent"])
app.include_router(models.router, prefix="/models", tags=["Models"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
