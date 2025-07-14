# ANPR Integration Guide - BOF Protocol Implementation

This document provides comprehensive guidance for integrating the ANPR Management System with BOF (British Optical Foundation) protocol for ANPR data transmission.

## Overview

The ANPR system implements BOF protocol integration for:
- **Hotlist synchronization** from external sources
- **Read record ingestion** via sendCompactCapture and addBinaryCaptureData
- **Real-time ANPR data transmission** to Management Server

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ANPR Camera   │───▶│  ANPR System    │───▶│ BOF Management  │
└─────────────────┘    │                 │    │     Server      │
                       │                 │    └─────────────────┘
                       │                 │
                       │                 │    ┌─────────────────┐
                       │                 │───▶│ Hotlist Sync    │
                       │                 │    │     Source      │
                       └─────────────────┘    └─────────────────┘
```

## Integration Components

### 1. BOF Protocol Integration

**Purpose**: Real-time ANPR data transmission via SOAP web services

**Operations**:
- `sendCompactCapture` - Send textual ANPR data
- `addBinaryCaptureData` - Send binary image data

**Service Endpoint**: `http://<host>/bof/services/AnprService`

**Features**:
- SOAP-based communication
- Separate textual and binary data transmission
- Base64 encoded images
- Real-time processing

### 2. Hotlist Synchronization

**Purpose**: External hotlist data synchronization

**Default Endpoint**: `http://localhost:8000/anpr/hotlists/sync`

**Features**:
- REST API based synchronization
- Configurable sync source
- Automatic duplicate detection
- Background processing

## Configuration

### BOF Server Configuration

Configure the BOF integration via the web interface or API:

```json
{
    "bof_host": "192.168.1.100",
    "bof_username": "anpr_user",
    "bof_password": "password123",
    "feed_id": "FEED001",
    "source_id": "SOURCE001",
    "hotlist_sync_url": "http://external-system/api/hotlists"
}
```

### Configuration Parameters

| Parameter | Description | Required |
|-----------|-------------|----------|
| `bof_host` | BOF Management Server IP/hostname | Yes |
| `bof_username` | BOF authentication username | Yes |
| `bof_password` | BOF authentication password | Yes |
| `feed_id` | Feed identifier for BOF | Yes |
| `source_id` | Source identifier for BOF | Yes |
| `hotlist_sync_url` | External hotlist sync URL | No |

## BOF Protocol Details

### sendCompactCapture Operation

Sends textual ANPR data to BOF Management Server:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" 
               xmlns:bof="http://bof.homeoffice.gov.uk/anpr">
    <soap:Header/>
    <soap:Body>
        <bof:sendCompactCapture>
            <bof:username>anpr_user</bof:username>
            <bof:password>password123</bof:password>
            <bof:feedIdentifier>FEED001</bof:feedIdentifier>
            <bof:sourceIdentifier>SOURCE001</bof:sourceIdentifier>
            <bof:cameraIdentifier>1</bof:cameraIdentifier>
            <bof:compactCapture>ABC123,2024-01-01T12:00:00Z,Location1,95,CAM001</bof:compactCapture>
        </bof:sendCompactCapture>
    </soap:Body>
</soap:Envelope>
```

### addBinaryCaptureData Operation

Sends binary image data (plate crop or context image):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" 
               xmlns:bof="http://bof.homeoffice.gov.uk/anpr">
    <soap:Header/>
    <soap:Body>
        <bof:addBinaryCaptureData>
            <bof:username>anpr_user</bof:username>
            <bof:password>password123</bof:password>
            <bof:feedIdentifier>FEED001</bof:feedIdentifier>
            <bof:sourceIdentifier>SOURCE001</bof:sourceIdentifier>
            <bof:cameraIdentifier>1</bof:cameraIdentifier>
            <bof:plateNumber>ABC123</bof:plateNumber>
            <bof:captureDateTime>2024-01-01T12:00:00Z</bof:captureDateTime>
            <bof:dataType>plate</bof:dataType>
            <bof:binaryData>base64encodedimagedata...</bof:binaryData>
        </bof:addBinaryCaptureData>
    </soap:Body>
</soap:Envelope>
```

## API Endpoints

### Integration Management

- `POST /anpr/configure` - Configure BOF integration
- `GET /anpr/connectivity` - Get integration status
- `POST /anpr/hotlists/sync` - Trigger hotlist sync

### Hotlist Sync

- `GET /anpr/hotlists/sync` - Sample hotlist sync endpoint

Example hotlist sync response:
```json
{
    "hotlists": [
        {
            "license_plate": "ABC123",
            "description": "Stolen vehicle from Manchester",
            "category": "stolen",
            "priority": "high",
            "vehicle_make": "Ford",
            "vehicle_model": "Focus",
            "vehicle_color": "Blue"
        }
    ]
}
```

## Data Flow

### ANPR Read Processing

1. **Capture**: ANPR camera captures license plate
2. **Recognition**: System recognizes plate and extracts data
3. **Hotlist Check**: Check against local hotlist database
4. **BOF Transmission**: 
   - Send textual data via `sendCompactCapture`
   - Send plate image via `addBinaryCaptureData` (if available)
   - Send context image via `addBinaryCaptureData` (if available)

### Hotlist Synchronization

1. **Trigger**: Manual or scheduled sync
2. **Fetch**: Retrieve hotlist data from external source
3. **Process**: Parse and validate hotlist entries
4. **Update**: Add new entries to local database
5. **Cleanup**: Remove outdated entries (optional)

## Image Requirements

### Plate Crop Images
- **Size**: 120x60 pixels maximum
- **Format**: JPEG/PNG
- **Encoding**: Base64 for transmission
- **Data Type**: "plate"

### Context Images
- **Size**: 25KB maximum
- **Format**: JPEG/PNG
- **Encoding**: Base64 for transmission
- **Data Type**: "context"

## Error Handling

### BOF Communication Errors
- Connection timeout: Retry with exponential backoff
- Authentication failure: Check credentials
- Invalid data: Validate before transmission
- Server errors: Log and alert

### Hotlist Sync Errors
- Network issues: Retry mechanism
- Invalid data: Skip and log
- Authentication: Check API keys
- Rate limiting: Implement delays

## Monitoring and Logging

### Integration Status
- BOF connection status
- Last successful transmission
- Error counts and types
- Performance metrics

### Logging
- All BOF operations logged
- Hotlist sync activities
- Error details and stack traces
- Performance metrics

## Security Considerations

### Authentication
- BOF username/password authentication
- Secure credential storage
- Regular credential rotation

### Data Protection
- Encrypted transmission (HTTPS/TLS)
- Secure image handling
- Access logging
- Data retention policies

## Troubleshooting

### Common Issues

1. **BOF Connection Failed**
   - Check network connectivity
   - Verify host/IP address
   - Confirm BOF service is running

2. **Authentication Errors**
   - Verify username/password
   - Check account permissions
   - Confirm service account status

3. **Image Transmission Issues**
   - Check image size limits
   - Verify Base64 encoding
   - Confirm data type parameter

4. **Hotlist Sync Problems**
   - Check sync URL accessibility
   - Verify data format
   - Confirm API authentication

### Performance Optimization

- Batch image transmissions when possible
- Implement connection pooling
- Use compression for large images
- Monitor transmission times

## Testing

### Integration Testing
1. Configure BOF connection
2. Send test ANPR read
3. Verify transmission success
4. Check BOF Management Server logs

### Load Testing
- Simulate high-volume ANPR reads
- Monitor system performance
- Verify error handling
- Test failover mechanisms

## Support

For technical support and configuration assistance:
- Check system logs for detailed error messages
- Use the integration status dashboard
- Test connectivity using the web interface
- Review configuration parameters

## Appendix

### Sample Configuration Files

BOF integration configuration:
```json
{
    "bof_host": "192.168.1.100",
    "bof_username": "anpr_user",
    "bof_password": "secure_password",
    "feed_id": "FEED001",
    "source_id": "SOURCE001",
    "hotlist_sync_url": "http://external-system/api/hotlists"
}
```

### Log Format Examples

BOF transmission log:
```
2024-01-01 12:00:00 INFO Successfully sent compact capture for plate: ABC123
2024-01-01 12:00:01 INFO Successfully sent plate image for plate: ABC123
2024-01-01 12:00:02 ERROR BOF sendCompactCapture failed: 500
```

Hotlist sync log:
```
2024-01-01 12:00:00 INFO Starting hotlist sync
2024-01-01 12:00:01 INFO Successfully synced 150 hotlists
2024-01-01 12:00:02 INFO Hotlist sync completed
``` 