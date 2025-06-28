from fastapi import FastAPI
from typing import List, Tuple, Dict, Any

from .search_engine import search as search_kb

app = FastAPI(
    title="P.A.S.C.A.L. API",
    description="Personal Assistant for Scientific and Computational ALgorithms",
    version="0.1.0"
)

@app.get("/", summary="Endpoint di saluto", tags=["General"])
def read_root():
    return {"message": "Benvenuto nell'API di P.A.S.C.A.L."}

@app.get("/search", summary="Esegue una ricerca nella knowledge base", tags=["Search"])
def search_endpoint(q: str, limit: int = 5) -> List[Tuple[Dict[str, Any], float]]:
    results = search_kb(query=q, limit=limit)
    return results
