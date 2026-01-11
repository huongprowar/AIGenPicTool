import httpx
import json
import uuid
import base64
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional, Dict, Union

class ImageRequest(BaseModel):
    """OpenAI-compatible image generation request model"""
    model: str
    prompt: str
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"
    quality: Optional[str] = "standard"
    response_format: Optional[str] = "b64_json"
    style: Optional[str] = "vivid"
    user: Optional[str] = None
    seed: Optional[int] = None

    class Config:
        extra = "allow"

class ImageUploadRequest(BaseModel):
    """Request model for uploading images to Google Flow"""
    image: str  # Base64 encoded image
    mime_type: Optional[str] = "image/jpeg"
    aspect_ratio: Optional[str] = "IMAGE_ASPECT_RATIO_PORTRAIT"

class ImageUploadResponse(BaseModel):
    """Response model for image upload"""
    media_generation_id: str
    width: int
    height: int

class ImageToImageRequest(BaseModel):
    """Request model for image-to-image generation"""
    model: str
    prompt: str
    reference_images: List[str]  # List of media generation IDs
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"
    response_format: Optional[str] = "b64_json"
    user: Optional[str] = None
    seed: Optional[int] = None

    class Config:
        extra = "allow"

class ImageEditRequest(BaseModel):
    """Request model for image edit (upload + image-to-image generation)"""
    model: str
    prompt: str
    images: List[str]  # List of base64 encoded images
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"
    response_format: Optional[str] = "b64_json"
    user: Optional[str] = None
    seed: Optional[int] = None

    class Config:
        extra = "allow"

class ImageData(BaseModel):
    """Individual image data in response"""
    b64_json: str
    revised_prompt: Optional[str] = None

class ImageResponse(BaseModel):
    """OpenAI-compatible image generation response model"""
    created: int
    data: List[ImageData]

GOOGLE_FLOW_API_ENDPOINT = "https://aisandbox-pa.googleapis.com/v1:runImageFx"
GOOGLE_FLOW_UPLOAD_ENDPOINT = "https://aisandbox-pa.googleapis.com/v1:uploadUserImage"

def map_size_to_aspect_ratio(size: str) -> str:
    """Map OpenAI size format to Google Flow aspect ratio"""
    size_mapping = {
        "1792x1024": "IMAGE_ASPECT_RATIO_LANDSCAPE",  # 16:9 Landscape
        "1024x1792": "IMAGE_ASPECT_RATIO_PORTRAIT",   # 9:16 Portrait
        "1024x1024": "IMAGE_ASPECT_RATIO_SQUARE",     # 1:1 Square
    }
    return size_mapping.get(size, "IMAGE_ASPECT_RATIO_LANDSCAPE")

def build_google_flow_headers(bearer_token: str) -> dict:
    """Build headers for Google Flow API request"""
    return {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'authorization': f'Bearer {bearer_token}',
        'content-type': 'text/plain;charset=UTF-8',
        'origin': 'https://labs.google',
        'priority': 'u=1, i',
        'referer': 'https://labs.google/',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'x-browser-copyright': 'Copyright 2025 Google LLC. All rights reserved.',
        'x-browser-validation': 'qvLgIVtG4U8GgiRPSI9IJ22mUlI=',
        'x-browser-year': '2025',
        'x-client-data': 'CIa2yQEIpbbJAQipncoBCI6RywEIk6HLAQiGoM0B'
    }

def build_google_flow_upload_body(req: ImageUploadRequest) -> dict:
    """Build request body for Google Flow image upload"""
    return {
        "imageInput": {
            "rawImageBytes": req.image,
            "mimeType": req.mime_type,
            "isUserUploaded": True,
            "aspectRatio": req.aspect_ratio
        },
        "clientContext": {
            "sessionId": f";{int(datetime.utcnow().timestamp() * 1000)}",
            "tool": "ASSET_MANAGER"
        }
    }

def build_google_flow_body(req: ImageRequest) -> dict:
    """Build request body for Google Flow API"""
    size = req.size or "1024x1024"
    num_images = req.n or 1
    
    # Determine model name based on the requested model
    model_name = "IMAGEN_3_5"  # Default to Imagen 3.5
    if req.model == "IMAGEN_4":
        model_name = "IMAGEN_3_5"
    elif req.model == "nano-banana-r2i":
        model_name = "R2I"
    elif req.model == "nano-banana":
        model_name = "GEM_PIX"
    
    return {
        "clientContext": {
            "sessionId": f";{int(datetime.utcnow().timestamp() * 1000)}",
            "tool": "PINHOLE",
            "projectId": str(uuid.uuid4())
        },
        "userInput": {
            "candidatesCount": num_images,  # This controls how many images are generated
            "seed": req.seed if req.seed is not None else int(datetime.utcnow().timestamp() * 1000) % 999999,  # Use provided seed or fallback to random
            "prompts": [req.prompt]
        },
        "aspectRatio": map_size_to_aspect_ratio(size),
        "modelInput": {
            "modelNameType": model_name
        }
    }

def build_google_flow_image_to_image_body(req: ImageToImageRequest) -> dict:
    """Build request body for Google Flow image-to-image generation"""
    size = req.size or "1024x1024"
    num_images = req.n or 1
    
    return {
        "clientContext": {
            "sessionId": f";{int(datetime.utcnow().timestamp() * 1000)}",
            "tool": "PINHOLE",
            "projectId": str(uuid.uuid4())
        },
        "userInput": {
            "candidatesCount": num_images,
            "seed": req.seed if req.seed is not None else int(datetime.utcnow().timestamp() * 1000) % 999999,
            "referenceImageInput": {
                "referenceImages": [
                    {
                        "mediaId": media_id,
                        "imageType": "REFERENCE_IMAGE_TYPE_CONTEXT"
                    }
                    for media_id in req.reference_images
                ]
            },
            "prompts": [req.prompt]
        },
        "aspectRatio": map_size_to_aspect_ratio(size),
        "modelInput": {
            "modelNameType": "R2I"
        }
    }

async def upload_image_to_google_flow(req: ImageUploadRequest, bearer_token: str) -> ImageUploadResponse:
    """Upload image to Google Flow and get media generation ID"""
    headers = build_google_flow_headers(bearer_token)
    body = build_google_flow_upload_body(req)
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            response = await client.post(
                GOOGLE_FLOW_UPLOAD_ENDPOINT,
                headers=headers,
                data=json.dumps(body)
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract media generation ID from response
            media_generation_id = result["mediaGenerationId"]["mediaGenerationId"]
            width = result.get("width", 0)
            height = result.get("height", 0)
            
            return ImageUploadResponse(
                media_generation_id=media_generation_id,
                width=width,
                height=height
            )
            
        except httpx.HTTPStatusError as e:
            print(f"Google upload API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"Error calling Google upload API: {str(e)}")
            raise

async def generate_google_flow_images(req: ImageRequest, bearer_token: str) -> ImageResponse:
    """Generate images using Google API"""
    headers = build_google_flow_headers(bearer_token)
    body = build_google_flow_body(req)
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            response = await client.post(
                GOOGLE_FLOW_API_ENDPOINT,
                headers=headers,
                data=json.dumps(body)  # Use data instead of json for text/plain content-type
            )
            response.raise_for_status()
            
            # Parse the Google Flow response
            result = response.json()
            
            # Extract images from Google Flow response
            images_data = []
            num_images = req.n or 1
            
            # Handle Google Flow API response structure based on actual format
            if "imagePanels" in result and len(result["imagePanels"]) > 0:
                # Extract images from the first image panel
                image_panel = result["imagePanels"][0]
                generated_images = image_panel.get("generatedImages", [])
                
                # Limit to requested number of images
                for image in generated_images[:num_images]:
                    encoded_image = image.get("encodedImage")
                    if encoded_image:
                        # Always return b64_json format regardless of request format
                        images_data.append(ImageData(
                            b64_json=encoded_image,
                            revised_prompt=image.get("prompt", req.prompt)
                        ))
            else:
                # Handle unknown response format or create placeholder for debugging
                print(f"Unexpected Google response format: {result}")
                for i in range(num_images):
                    images_data.append(ImageData(
                        b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",  # 1x1 transparent PNG as placeholder
                        revised_prompt=req.prompt
                    ))
            
            return ImageResponse(
                created=int(datetime.utcnow().timestamp()),
                data=images_data
            )
            
        except httpx.HTTPStatusError as e:
            print(f"Google API error: {e.response.status_code} - {e.response.text}")
            # Log the actual response for debugging
            print(f"Response content: {e.response.text}")
            raise
        except Exception as e:
            print(f"Error calling Google API: {str(e)}")
            raise

async def generate_google_flow_image_to_image(req: ImageToImageRequest, bearer_token: str) -> ImageResponse:
    """Generate images using Google R2I model with reference images"""
    headers = build_google_flow_headers(bearer_token)
    body = build_google_flow_image_to_image_body(req)
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            response = await client.post(
                GOOGLE_FLOW_API_ENDPOINT,
                headers=headers,
                data=json.dumps(body)
            )
            response.raise_for_status()
            
            # Parse the Google Flow response
            result = response.json()
            
            # Extract images from Google Flow response
            images_data = []
            num_images = req.n or 1
            
            # Handle Google Flow API response structure based on actual format
            if "imagePanels" in result and len(result["imagePanels"]) > 0:
                # Extract images from the first image panel
                image_panel = result["imagePanels"][0]
                generated_images = image_panel.get("generatedImages", [])
                
                # Limit to requested number of images
                for image in generated_images[:num_images]:
                    encoded_image = image.get("encodedImage")
                    if encoded_image:
                        # Always return b64_json format regardless of request format
                        images_data.append(ImageData(
                            b64_json=encoded_image,
                            revised_prompt=image.get("prompt", req.prompt)
                        ))
            else:
                # Handle unknown response format or create placeholder for debugging
                print(f"Unexpected Google response format: {result}")
                for i in range(num_images):
                    images_data.append(ImageData(
                        b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",  # 1x1 transparent PNG as placeholder
                        revised_prompt=req.prompt
                    ))
            
            return ImageResponse(
                created=int(datetime.utcnow().timestamp()),
                data=images_data
            )
            
        except httpx.HTTPStatusError as e:
            print(f"Google API error: {e.response.status_code} - {e.response.text}")
            # Log the actual response for debugging
            print(f"Response content: {e.response.text}")
            raise
        except Exception as e:
            print(f"Error calling Google API: {str(e)}")
            raise

async def generate_image_edit(req: ImageEditRequest, bearer_token: str) -> ImageResponse:
    """Generate images using Google R2I model with uploaded reference images"""
    # First, upload all images to get media generation IDs
    media_ids = []
    
    for i, base64_image in enumerate(req.images):
        try:
            # Create upload request for each image
            upload_req = ImageUploadRequest(
                image=base64_image,
                mime_type="image/jpeg",  # Default to JPEG
                aspect_ratio="IMAGE_ASPECT_RATIO_PORTRAIT"  # Default aspect ratio
            )
            
            # Upload image and get media ID
            upload_response = await upload_image_to_google_flow(upload_req, bearer_token)
            media_ids.append(upload_response.media_generation_id)
            
            print(f"Uploaded image {i+1}/{len(req.images)}, media ID: {upload_response.media_generation_id}")
            
        except Exception as e:
            print(f"Error uploading image {i+1}: {str(e)}")
            raise
    
    # Now create image-to-image request using all media IDs
    image_to_image_req = ImageToImageRequest(
        model=req.model,
        prompt=req.prompt,
        reference_images=media_ids,
        n=req.n,
        size=req.size,
        response_format=req.response_format,
        user=req.user,
        seed=req.seed
    )
    
    # Generate images using all uploaded images as references
    return await generate_google_flow_image_to_image(image_to_image_req, bearer_token)
