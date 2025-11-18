"""
Utility functions for the application
"""
import base64
import mimetypes
from typing import Optional


def to_data_url(data: bytes, filename: str, mime_type: Optional[str] = None) -> str:
    """Convert binary data to base64 data URL format.
    
    Args:
        data: Binary image data
        filename: File name (to detect MIME type if not provided)
        mime_type: Optional MIME type (if provided, used instead of detecting)
    
    Returns:
        Data URL in format: data:image/{format};base64,{base64_encoded_data}
    """
    if mime_type:
        mime = mime_type
    else:
        mime, _ = mimetypes.guess_type(filename)
        if not mime:
            mime = "application/octet-stream"
    
    base64_encoded = base64.b64encode(data).decode('utf-8')
    return f"data:{mime};base64,{base64_encoded}"


