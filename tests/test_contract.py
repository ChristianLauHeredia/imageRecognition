import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app
from app.schemas import VisionResult, BBox


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def valid_image():
    """Create a minimal valid PNG image"""
    from PIL import Image
    import io
    img = Image.new('RGB', (100, 100), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


@pytest.mark.asyncio
async def test_analyze_success(client, valid_image):
    """Test successful analysis with valid input"""
    mock_result = {
        "found": True,
        "confidence": 0.87,
        "boxes": [
            {"x": 0.12, "y": 0.34, "w": 0.22, "h": 0.19, "confidence": 0.83}
        ]
    }
    
    with patch("app.main.run_vision", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_result
        
        response = client.post(
            "/analyze",
            data={"prompt": "detect a stop sign"},
            files={"image": ("test.png", valid_image, "image/png")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["confidence"] == 0.87
        assert len(data["boxes"]) == 1
        # Validate with Pydantic
        VisionResult.model_validate(data)


def test_analyze_missing_image(client):
    """Test 400 when image is missing"""
    response = client.post(
        "/analyze",
        data={"prompt": "test"}
    )
    assert response.status_code == 400


def test_analyze_missing_prompt(client, valid_image):
    """Test 400 when prompt is missing"""
    response = client.post(
        "/analyze",
        files={"image": ("test.png", valid_image, "image/png")}
    )
    assert response.status_code == 422  # FastAPI validation error


def test_analyze_invalid_image(client):
    """Test 400 when image is invalid"""
    invalid_image = b"not an image"
    response = client.post(
        "/analyze",
        data={"prompt": "test"},
        files={"image": ("test.txt", invalid_image, "text/plain")}
    )
    assert response.status_code == 400
    assert "invalid image" in response.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_invalid_output(client, valid_image):
    """Test 500 when run_vision returns invalid output"""
    invalid_result = {"found": True}  # Missing required fields
    
    with patch("app.main.run_vision", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = invalid_result
        
        response = client.post(
            "/analyze",
            data={"prompt": "test"},
            files={"image": ("test.png", valid_image, "image/png")}
        )
        
        assert response.status_code == 500


@pytest.mark.asyncio
async def test_analyze_no_final_output(client, valid_image):
    """Test 500 when agent doesn't return final_output"""
    from app.agent_def import run_vision
    
    with patch("app.main.run_vision", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = RuntimeError("Agent result is undefined")
        
        response = client.post(
            "/analyze",
            data={"prompt": "test"},
            files={"image": ("test.png", valid_image, "image/png")}
        )
        
        assert response.status_code == 500


