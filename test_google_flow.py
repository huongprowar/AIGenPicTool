"""
Script test Google Flow API to generate images
Run: python test_google_flow.py
"""

import asyncio
import base64
import sys
from pathlib import Path

# Add root folder to path
sys.path.insert(0, str(Path(__file__).parent))

from UnlimitedAPI.providers.google_flow import (
    generate_google_flow_images,
    ImageRequest
)
from services.config_service import config_service


def test_google_flow_api(prompt: str = "A beautiful sunset over mountains", save_image: bool = True):
    """
    Test Google Flow API

    Args:
        prompt: Prompt to generate image
        save_image: Save image to file or not
    """
    print("=" * 60)
    print("TEST GOOGLE FLOW API")
    print("=" * 60)

    # Get bearer token from config
    config = config_service.config
    bearer_token = config.google_bearer_token

    if not bearer_token:
        print("ERROR: Google Bearer Token not configured!")
        print("Please add bearer token to config or settings.")
        return False

    print(f"Bearer Token: {bearer_token[:20]}...{bearer_token[-10:]}")
    print(f"Prompt: {prompt}")
    print("-" * 60)

    try:
        # Create request
        request = ImageRequest(
            model="IMAGEN_4",
            prompt=prompt,
            n=1,
            size="1024x1024",
            response_format="b64_json"
        )

        print("Created ImageRequest:")
        print(f"  - Model: {request.model}")
        print(f"  - Size: {request.size}")
        print(f"  - N: {request.n}")
        print("-" * 60)

        # Call API
        print("Calling Google Flow API...")
        result = asyncio.run(generate_google_flow_images(request, bearer_token))

        print(f"Response created: {result.created}")
        print(f"Number of images: {len(result.data)}")
        print("-" * 60)

        if result.data and len(result.data) > 0:
            image_data = result.data[0]
            image_bytes = base64.b64decode(image_data.b64_json)

            print("Image info:")
            print(f"  - Base64 length: {len(image_data.b64_json)} chars")
            print(f"  - Image size: {len(image_bytes)} bytes")
            print(f"  - Revised prompt: {image_data.revised_prompt}")

            if save_image:
                # Save image
                output_path = Path(__file__).parent / "test_output.png"
                with open(output_path, "wb") as f:
                    f.write(image_bytes)
                print(f"  - Saved image: {output_path}")

            print("=" * 60)
            print("TEST SUCCESS!")
            print("=" * 60)
            return True
        else:
            print("ERROR: No image data in response")
            print("=" * 60)
            print("TEST FAILED!")
            print("=" * 60)
            return False

    except Exception as e:
        print(f"ERROR: {str(e)}")
        print("=" * 60)
        print("TEST FAILED!")
        print("=" * 60)
        return False


def test_multiple_sizes():
    """Test with multiple sizes"""
    sizes = ["1024x1024", "1792x1024", "1024x1792"]
    prompt = "A cute cat playing with a ball"

    config = config_service.config
    bearer_token = config.google_bearer_token

    if not bearer_token:
        print("ERROR: Google Bearer Token not configured!")
        return

    print("=" * 60)
    print("TEST MULTIPLE SIZES")
    print("=" * 60)

    for size in sizes:
        print(f"\nTesting size: {size}")
        print("-" * 40)

        try:
            request = ImageRequest(
                model="IMAGEN_4",
                prompt=prompt,
                n=1,
                size=size,
                response_format="b64_json"
            )

            result = asyncio.run(generate_google_flow_images(request, bearer_token))

            if result.data and len(result.data) > 0:
                image_bytes = base64.b64decode(result.data[0].b64_json)
                print(f"  SUCCESS - Image size: {len(image_bytes)} bytes")

                # Save image
                output_path = Path(__file__).parent / f"test_output_{size.replace('x', '_')}.png"
                with open(output_path, "wb") as f:
                    f.write(image_bytes)
                print(f"  Saved: {output_path}")
            else:
                print(f"  FAILED - No image data")

        except Exception as e:
            print(f"  ERROR: {str(e)}")

    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Google Flow API")
    parser.add_argument("--prompt", "-p", type=str, default="A beautiful sunset over mountains",
                        help="Prompt to generate image")
    parser.add_argument("--no-save", action="store_true",
                        help="Do not save image to file")
    parser.add_argument("--multi-size", action="store_true",
                        help="Test with multiple sizes")

    args = parser.parse_args()

    if args.multi_size:
        test_multiple_sizes()
    else:
        test_google_flow_api(prompt=args.prompt, save_image=not args.no_save)
