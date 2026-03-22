import os, httpx, dotenv
from fastapi import FastAPI, HTTPException, Header # type: ignore
from pydantic import BaseModel # type: ignore
from typing import List, Optional
app = FastAPI(title="mcpGateway")
ollamaUrl = os.getenv("OLLAMA_URL", "http://ollama-node:11434")
mcpApiKey = os.getenv("MCP_API_KEY")
httpClient: Optional[httpx.AsyncClient] = None
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False

async def checkOllamaConnection() -> tuple[bool, str]:
    if httpClient is None: return False, "Gateway client not initialized"
    try:
        response = await httpClient.get(f"{ollamaUrl}/api/tags")
        if response.is_success: return True, "ok"
        return False, f"Ollama returned status {response.status_code}"
    except httpx.RequestError as e: return False, f"Ollama Node Unreachable: {e}"

@app.on_event("startup")
async def startupEvent():
    global httpClient
    timeout = httpx.Timeout(300.0, connect=10.0)
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    httpClient = httpx.AsyncClient(timeout=timeout, limits=limits)
    healthy, detail = await checkOllamaConnection()
    if healthy: print("[*] Connection to ollama-node verified")
    else: print(f"[!] Critical: Could not reach ollama-node: {detail}")

@app.on_event("shutdown")
async def shutdownEvent():
    global httpClient
    if httpClient is not None:
        await httpClient.aclose()
        httpClient = None


@app.get("/health")
async def healthCheck():
    healthy, detail = await checkOllamaConnection()
    if not healthy: raise HTTPException(status_code=503, detail=detail)
    return {"status": "ok"}

@app.post("/v1/chat")
async def proxyChat(request: ChatRequest, authorization: Optional[str] = Header(default=None)):
    if mcpApiKey:
        expected = f"Bearer {mcpApiKey}"
        if authorization != expected: raise HTTPException(status_code=401, detail="Unauthorized")
    if httpClient is None: raise HTTPException(status_code=500, detail="Gateway client not initialized")

    try:
        payload = request.dict()
        response = await httpClient.post(
            f"{ollamaUrl}/api/chat",
            json=payload)
        if response.status_code != 200: raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()
    except httpx.RequestError as e: raise HTTPException(status_code=500, detail=f"Ollama Node Unreachable: {e}")

if __name__ == "__main__":
    import uvicorn; uvicorn.run(app, host="0.0.0.0", port=8080) # type: ignore
