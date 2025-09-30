import json
import boto3
import os
from PIL import Image
from io import BytesIO
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    try:
        # Get bucket and object key from the event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
        
        logger.info(f"Processing image: {key} from bucket: {bucket}")
        
        # Skip if already processed
        if key.startswith('processed/'):
            logger.info("Image already processed, skipping")
            return {
                'statusCode': 200,
                'body': json.dumps('Already processed')
            }
        
        # Download the image from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        # Process the image
        processed_images = process_image(image_data)
        
        # Upload processed images back to S3
        output_bucket = os.environ.get('OUTPUT_BUCKET', bucket)
        base_key = os.path.splitext(key)[0]
        
        for size_name, processed_data in processed_images.items():
            output_key = f"processed/{base_key}_{size_name}.jpg"
            s3_client.put_object(
                Bucket=output_bucket,
                Key=output_key,
                Body=processed_data,
                ContentType='image/jpeg'
            )
            logger.info(f"Uploaded processed image: {output_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Image processed successfully',
                'original': key,
                'processed': list(processed_images.keys())
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def process_image(image_data):
    processed = {}
    
    # Open image
    img = Image.open(BytesIO(image_data))
    
    # Convert RGBA to RGB if necessary
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    
    # Create thumbnail (200x200)
    thumbnail = img.copy()
    thumbnail.thumbnail((200, 200), Image.Resampling.LANCZOS)
    thumb_buffer = BytesIO()
    thumbnail.save(thumb_buffer, format='JPEG', quality=85, optimize=True)
    processed['thumbnail'] = thumb_buffer.getvalue()
    
    # Create medium size (800x800)
    medium = img.copy()
    medium.thumbnail((800, 800), Image.Resampling.LANCZOS)
    medium_buffer = BytesIO()
    medium.save(medium_buffer, format='JPEG', quality=90, optimize=True)
    processed['medium'] = medium_buffer.getvalue()
    
    # Create optimized original
    optimized = img.copy()
    optimized.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
    optimized_buffer = BytesIO()
    optimized.save(optimized_buffer, format='JPEG', quality=95, optimize=True)
    processed['optimized'] = optimized_buffer.getvalue()
    
    return processed
