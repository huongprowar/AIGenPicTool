from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Header
from pydantic import BaseModel
from typing import List, Optional, Dict, Union, Any
from datetime import datetime
import uuid
import json
import os
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from providers.google_flow import (
    generate_google_flow_images,
    upload_image_to_google_flow,
    generate_google_flow_image_to_image,
    generate_image_edit,
    ImageRequest,
    ImageResponse,
    ImageUploadRequest,
    ImageUploadResponse,
    ImageToImageRequest,
    ImageEditRequest
)

"""Local Image Generation API using Google Flow.
This API provides OpenAI-compatible endpoints for image generation and image editing.

Endpoints:
    • GET  /v1/models              → returns available image generation models
    • POST /v1/images/generations   → generate images using Google Flow
    • POST /v1/images/image-edit    → upload images and generate using reference images (R2I model)
    • POST /v1/chat/completions    → disabled (returns error message)

Run locally with:
    uvicorn main:app --reload --port 8000
"""

app = FastAPI(title="Local Image Generation API", version="0.1.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# ---------- Pydantic schemas for image generation ---------- #
# Chat-related schemas are kept for potential future use but not actively used
class ContentPart(BaseModel):
    type: str
    text: str

class Message(BaseModel):
    role: str
    content: Union[str, List[ContentPart]]
    id: Optional[str] = None

class ChatRequest(BaseModel):
    messages: List[Message]
    model: str
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None

    class Config:
        extra = "allow"

class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str

class ChatCompletion(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Dict[str, int]


# Google Flow Token
GOOGLE_FLOW_TOKEN = os.getenv("GOOGLE_FLOW_TOKEN", "")
if not GOOGLE_FLOW_TOKEN:
    token_path = os.path.join(os.path.dirname(__file__), "config/google_flow_token.json")
    if os.path.exists(token_path):
        try:
            with open(token_path, 'r') as f:
                token_data = json.load(f)
                GOOGLE_FLOW_TOKEN = token_data.get("bearer_token", "")
        except Exception:
            GOOGLE_FLOW_TOKEN = ""

# API Key for authentication
ARK_API_KEY = "sk-demo"

def verify_api_key(authorization: Optional[str]) -> bool:
    """Verify API key from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        return False
    api_key = authorization.replace("Bearer ", "")
    return api_key == ARK_API_KEY


# ---------- Routes ---------- #

@app.get("/v1/models")
async def list_models():
    """Return a list of available image generation models."""
    data = [
        # Google Flow Models (Image Generation)
        {"id": "nano-banana", "object": "model", "owned_by": "google"},
        {"id": "nano-banana-r2i", "object": "model", "owned_by": "google"},
        {"id": "IMAGEN_4", "object": "model", "owned_by": "google"},
    ]
    return {"object": "list", "data": data}

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    """Chat completions endpoint - only image generation models are supported."""
    
    # Only Google Flow image generation models are supported
    return JSONResponse(
        content={"error": "Chat completions are not supported. This API only supports image generation via /v1/images/generations endpoint."}, 
        status_code=400
    )

@app.post("/v1/images/generations")
async def image_generations(req: ImageRequest, authorization: Optional[str] = Header(None)):
    """Generate images using Google provider with OpenAI-compatible interface."""
    # Verify API key
    if not verify_api_key(authorization):
        return JSONResponse(
            content={"error": "Invalid API key"},
            status_code=401
        )

    if not GOOGLE_FLOW_TOKEN:
        return JSONResponse(
            content={"error": "Google token not configured"},
            status_code=500
        )

    # Route to Google Flow for image generation
    if req.model in ["nano-banana", "nano-banana-r2i", "IMAGEN_4"]:
        try:
            print(f"--- Generating images with Google using model {req.model} ---")
            print(f"Using bearer token authentication (token length: {len(GOOGLE_FLOW_TOKEN)})")
            response = await generate_google_flow_images(req, GOOGLE_FLOW_TOKEN)
            return JSONResponse(content=response.dict())
        except httpx.HTTPStatusError as e:
            print(f"Error generating images: {str(e)}")
            return JSONResponse(
                content={"error": f"Image generation failed: {e.response.text}"},
                status_code=e.response.status_code
            )
        except Exception as e:
            print(f"Error generating images: {str(e)}")
            return JSONResponse(
                content={"error": f"Image generation failed: {str(e)}"},
                status_code=500
            )
    else:
        return JSONResponse(
            content={"error": "Model not supported for image generation"},
            status_code=400
        )

@app.post("/v1/images/image-edit")
async def image_edit(authorization: Optional[str] = Header(None), req: ImageEditRequest = None):
    """Upload images and generate new images using Google R2I model with reference images."""
    # Verify API key
    if not verify_api_key(authorization):
        return JSONResponse(
            content={"error": "Invalid API key"},
            status_code=401
        )

    if not GOOGLE_FLOW_TOKEN:
        return JSONResponse(
            content={"error": "Google token not configured"},
            status_code=500
        )

    # Only support R2I model for image editing
    if req.model == "nano-banana-r2i":
        try:
            print(f"--- Image editing with Google R2I model ---")
            print(f"Using bearer token authentication (token length: {len(GOOGLE_FLOW_TOKEN)})")
            print(f"Number of reference images: {len(req.images)}")
            print(f"Generating {req.n} images")
            response = await generate_image_edit(req, GOOGLE_FLOW_TOKEN)
            return JSONResponse(content=response.dict())
        except httpx.HTTPStatusError as e:
            print(f"Error in image editing: {str(e)}")
            return JSONResponse(
                content={"error": f"Image editing failed: {e.response.text}"},
                status_code=e.response.status_code
            )
        except Exception as e:
            print(f"Error in image editing: {str(e)}")
            return JSONResponse(
                content={"error": f"Image editing failed: {str(e)}"},
                status_code=500
            )
    else:
        return JSONResponse(
            content={"error": "Only nano-banana-r2i model is supported for image editing"},
            status_code=400
        )


# ---------- Entrypoint ---------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
