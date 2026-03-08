from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus.api.routes import experiments, feed, graph, health, hypotheses, query, sessions
from nexus.graph.client import graph_client


@asynccontextmanager
async def lifespan(app: FastAPI):
	await graph_client.connect()
	yield
	await graph_client.close()


app = FastAPI(
	title="Nexus API",
	description="Autonomous Biological Discovery Platform",
	version="0.1.0",
	lifespan=lifespan,
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:3000"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(feed.router, prefix="/api", tags=["feed"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(hypotheses.router, prefix="/api", tags=["hypotheses"])
app.include_router(experiments.router, prefix="/api", tags=["experiments"])
