# ANPR Management System

A comprehensive Automatic Number Plate Recognition (ANPR) management system built with FastAPI and modern web technologies. This system allows for vehicle hotlist management, real-time ANPR camera integration, and monitoring of license plate reads.

## Features

### Core Functionality
- **Vehicle Hotlist Management**: Add, edit, delete, and search vehicle hotlists
- **ANPR Camera Integration**: Receive and process license plate reads from ANPR cameras
- **Real-time Monitoring**: Live dashboard with automatic updates
- **Hotlist Matching**: Automatic matching of ANPR reads against hotlists
- **Search & Filtering**: Advanced search and filtering capabilities
- **Export Functionality**: Export data to CSV format

### Technical Features
- **RESTful API**: Comprehensive API with automatic documentation
- **Database Integration**: SQLite database with SQLAlchemy ORM
- **Modern UI**: Bootstrap-based responsive interface
- **Real-time Updates**: Auto-refresh functionality for live monitoring
- **Professional Design**: Clean, modern interface suitable for security/law enforcement

## Technology Stack

### Backend
- **FastAPI**: High-performance web framework
- **SQLAlchemy**: Database ORM
- **SQLite**: Database (easily changeable to PostgreSQL)
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server

### Frontend
- **Bootstrap 5**: UI framework
- **Vanilla JavaScript**: Frontend logic
- **Font Awesome**: Icons
- **Axios**: HTTP client
- **Jinja2**: Template engine

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd anpr_app
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python main.py
   ```

4. **Access the application**
   - Main Application: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Alternative API Docs: http://localhost:8000/redoc

## Database Schema

### Hotlists Table
- `id`: Primary key
- `license_plate`: Vehicle license plate (unique)
- `description`: Reason for hotlist entry
- `category`: Type (stolen, wanted, bolo, suspicious)
- `priority`: Priority level (low, medium, high, critical)
- `created_by`: User who created the entry
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `is_active`: Active status
- `expiry_date`: Optional expiry date
- Vehicle details (make, model, color, year)
- `owner_name`: Vehicle owner name
- `notes`: Additional notes

### ANPR Reads Table
- `id`: Primary key
- `license_plate`: Detected license plate
- `camera_id`: Camera identifier
- `location`: Camera location
- `timestamp`: Detection timestamp
- `confidence`: Detection confidence (0-100)
- `image_path`: Path to captured image (optional)
- `hotlist_match`: Boolean indicating hotlist match
- `hotlist_id`: Reference to matched hotlist entry
- Additional metadata (direction, speed, lane)

## API Endpoints

### Hotlist Management
- `GET /api/hotlists` - Get all hotlists
- `POST /api/hotlists` - Create new hotlist
- `GET /api/hotlists/{id}` - Get specific hotlist
- `PUT /api/hotlists/{id}` - Update hotlist
- `DELETE /api/hotlists/{id}` - Delete hotlist

### ANPR Reads
- `GET /api/anpr-reads` - Get all ANPR reads
- `POST /api/anpr-reads` - Submit new ANPR read
- `GET /api/anpr-reads/{id}` - Get specific read

### Statistics
- `GET /api/stats` - Get system statistics

## Usage

### Adding a Hotlist Entry
1. Navigate to the Hotlists page
2. Click "Add Hotlist"
3. Fill in the required information:
   - License plate
   - Category (stolen, wanted, bolo, suspicious)
   - Description
   - Priority level
   - Created by
4. Optionally add vehicle details and notes
5. Save the entry

### Monitoring ANPR Reads
1. Navigate to the ANPR Reads page
2. View real-time reads from cameras
3. Use filters to search specific:
   - License plates
   - Cameras
   - Locations
   - Hotlist matches only
4. Auto-refresh keeps the data current

### API Integration
The system provides RESTful APIs for third-party integration:

#### Submitting ANPR Reads
```bash
curl -X POST "http://localhost:8000/api/anpr-reads" \
  -H "Content-Type: application/json" \
  -d '{
    "license_plate": "ABC123",
    "camera_id": "CAM001",
    "location": "Main Street & 1st Ave",
    "confidence": 95,
    "direction": "north",
    "speed": 35
  }'
```

#### Querying Hotlists
```bash
curl "http://localhost:8000/api/hotlists?search=ABC123"
```

## Configuration

### Database
By default, the system uses SQLite. To change to PostgreSQL:

1. Update `database.py`:
   ```python
   SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/anpr_db"
   ```

2. Install PostgreSQL driver:
   ```bash
   pip install psycopg2-binary
   ```

### Environment Variables
- `DATABASE_URL`: Database connection string
- `API_KEY`: Optional API key for authentication

## Security Considerations

- Input validation on all endpoints
- SQL injection prevention through ORM
- CORS configuration for API access
- Rate limiting (can be added)
- Authentication/authorization (can be added)

## Development

### Running in Development Mode
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Add test framework
pip install pytest pytest-asyncio httpx
python -m pytest tests/
```

### Database Migrations
```bash
# Install Alembic for migrations
pip install alembic
alembic init alembic
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Deployment

### Production Deployment
1. Use a production WSGI server (Gunicorn)
2. Configure reverse proxy (Nginx)
3. Set up SSL/TLS certificates
4. Use production database (PostgreSQL)
5. Set up monitoring and logging

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## API Documentation

Full API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Support

For issues, questions, or contributions:
1. Check the API documentation
2. Review the code comments
3. Submit issues or pull requests

## License

This project is licensed under the MIT License.

## Future Enhancements

- User authentication and authorization
- Role-based access control
- Advanced reporting and analytics
- Integration with external databases
- Mobile application
- Advanced search with AI/ML
- Real-time notifications
- Audit logging
- Multi-tenant support 