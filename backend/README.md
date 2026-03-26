# Watt Watch Backend

FastAPI backend server for Watt Watch application with human and backpack detection capabilities using YOLO26 models.

## Features

- **Single Image Detection**: Detect humans and backpacks in a single image
- **Batch Processing**: Process multiple images at once
- **Flexible Mode**: Support for bounding box detection, segmentation, or both
- **Class Filtering**: Filter detections by class IDs (person=0, backpack=24)
- **Dotted Box Visualization**: Automatically annotate images with dotted boxes showing detections

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the development server:
```bash
python main.py
```

Or use uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Dotted Box Visualization

The API can automatically draw dotted boxes on detected objects and save annotated images.

### Using the API

Add `save_annotated=true` parameter to any detection endpoint:

**Single image:**
```bash
curl -X POST "http://localhost:8000/detect?save_annotated=true" \
  -F "file=@test.jpg"
```

**Batch processing:**
```bash
curl -X POST "http://localhost:8000/detect/batch?save_annotated=true" \
  -F "files=@test1.jpg" \
  -F "files=@test2.jpg"
```

Annotated images will be saved to `backend/annotated_images/` directory with the prefix `annotated_`.

### Using Python Directly

```python
from main import draw_dotted_boxes, _process_single_image

# Run detection
detection_result = _process_single_image("test.jpg", "test.jpg", classes=[0, 24], mode="bbox")

# Draw dotted boxes and save (saves as test_annotated.jpg in same directory)
annotated_path = draw_dotted_boxes("test.jpg", detection_result)
print(f"Saved to: {annotated_path}")

# Or specify custom output path
annotated_path = draw_dotted_boxes("test.jpg", detection_result, "output/my_annotated.jpg")
```

### Quick Test

Run the provided example script to process test images:

```bash
python run_detection_and_annotate.py
```

This will:
1. Run detection on test images in the backend directory
2. Create annotated versions with `_annotated` suffix
3. Display detection summary in the console

### Box Appearance

- **Person (class 0)**: Green dotted box
- **Backpack (class 24)**: Blue dotted box
- **Other classes**: Yellow dotted box
- Label shows class name and confidence score

## API Endpoints

### Basic Endpoints

- **GET /** - Welcome message
- **GET /health** - Health check endpoint

### Detection Endpoints

#### Single Image Detection
**POST /detect**

Upload a single image to detect humans and backpacks.

**Parameters:**
- `file` (form-data): Image file to process
- `classes` (query, optional): List of class IDs to detect. Default: `[0, 24]` (person and backpack)
- `mode` (query, optional): Detection mode - `bbox`, `seg`, or `both`. Default: `both`
- `save_annotated` (query, optional): Save annotated image with dotted boxes. Default: `false`

**Example:**
```bash
curl -X POST "http://localhost:8000/detect?classes=0&classes=24&mode=both" \
  -F "file=@path/to/image.jpg"
```

**Response:**
```json
{
  "results": [
    {
      "file_name": "image.jpg",
      "height": 1080,
      "width": 1920,
      "boxes": [
        {
          "class_id": 0,
          "class_name": null,
          "confidence": 0.95,
          "xyxy": [100.0, 200.0, 300.0, 500.0]
        }
      ],
      "masks": [
        {
          "class_id": 0,
          "class_name": "person",
          "confidence": 0.95,
          "total_boundary_points": 128,
          "polygon_coordinates": [[x1, y1], [x2, y2], ...]
        }
      ]
    }
  ]
}
```

#### Batch Image Detection
**POST /detect/batch**

Upload multiple images to detect humans and backpacks in all of them.

**Parameters:**
- `files` (form-data): Multiple image files to process
- `classes` (query, optional): List of class IDs to detect. Default: `[0, 24]`
- `mode` (query, optional): Detection mode - `bbox`, `seg`, or `both`. Default: `both`
- `save_annotated` (query, optional): Save annotated images with dotted boxes. Default: `false`

**Example:**
```bash
curl -X POST "http://localhost:8000/detect/batch?classes=0&classes=24&mode=both" \
  -F "files=@image1.jpg" \
  -F "files=@image2.jpg" \
  -F "files=@image3.jpg"
```

**Response:**
```json
{
  "results": [
    {
      "file_name": "image1.jpg",
      "height": 1080,
      "width": 1920,
      "boxes": [...],
      "masks": [...]
    },
    {
      "file_name": "image2.jpg",
      "height": 720,
      "width": 1280,
      "boxes": [...],
      "masks": [...]
    }
  ]
}
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Models

The application uses YOLO26 models:
- **YOLO26n-bbox**: For bounding box detection
- **YOLO26n-seg**: For instance segmentation

Models are automatically downloaded on first run if not found locally.

## Class IDs

- `0`: Person
- `24`: Backpack

You can modify the `classes` parameter to detect other objects supported by YOLO26.
