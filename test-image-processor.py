import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from PIL import Image

# Add parent directory to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda'))

from image_processor import lambda_handler, process_image

@pytest.fixture
def sample_image():
    img = Image.new('RGB', (1000, 1000), color='red')
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    return buffer.getvalue()

@pytest.fixture
def s3_event():
    return {
        'Records': [{
            's3': {
                'bucket': {
                    'name': 'test-bucket'
                },
                'object': {
                    'key': 'uploads/test-image.jpg'
                }
            }
        }]
    }

@pytest.fixture
def mock_s3_client():
    with patch('image_processor.s3_client') as mock:
        yield mock

def test_process_image_creates_three_sizes(sample_image):
    processed = process_image(sample_image)
    
    assert len(processed) == 3
    assert 'thumbnail' in processed
    assert 'medium' in processed
    assert 'optimized' in processed
    
    # Verify all are valid JPEG data
    for size_name, image_data in processed.items():
        img = Image.open(BytesIO(image_data))
        assert img.format == 'JPEG'

def test_process_image_thumbnail_size(sample_image):
    processed = process_image(sample_image)
    thumbnail = Image.open(BytesIO(processed['thumbnail']))
    
    # Thumbnail should be max 200x200
    assert thumbnail.size[0] <= 200
    assert thumbnail.size[1] <= 200

def test_process_image_medium_size(sample_image):
    processed = process_image(sample_image)
    medium = Image.open(BytesIO(processed['medium']))
    
    # Medium should be max 800x800
    assert medium.size[0] <= 800
    assert medium.size[1] <= 800

def test_lambda_handler_success(s3_event, sample_image, mock_s3_client):
    # Mock S3 responses
    mock_s3_client.get_object.return_value = {
        'Body': MagicMock(read=lambda: sample_image)
    }
    mock_s3_client.put_object.return_value = {}
    
    # Execute lambda
    response = lambda_handler(s3_event, None)
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['message'] == 'Image processed successfully'
    assert 'original' in body
    assert len(body['processed']) == 3

def test_lambda_handler_skips_processed_images(mock_s3_client):
    event = {
        'Records': [{
            's3': {
                'bucket': {'name': 'test-bucket'},
                'object': {'key': 'processed/test-image.jpg'}
            }
        }]
    }
    
    response = lambda_handler(event, None)
    
    assert response['statusCode'] == 200
    assert 'Already processed' in response['body']
    mock_s3_client.get_object.assert_not_called()

def test_lambda_handler_error_handling(s3_event, mock_s3_client):
    mock_s3_client.get_object.side_effect = Exception('S3 error')
    
    response = lambda_handler(s3_event, None)
    
    assert response['statusCode'] == 500
    body = json.loads(response['body'])
    assert 'error' in body

def test_process_image_handles_rgba(sample_image):
    # Create RGBA image
    img = Image.new('RGBA', (500, 500), color=(255, 0, 0, 128))
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    processed = process_image(buffer.getvalue())
    
    # Should successfully process without errors
    assert len(processed) == 3
    
    # Verify all outputs are RGB JPEG
    for image_data in processed.values():
        output_img = Image.open(BytesIO(image_data))
        assert output_img.mode == 'RGB'
