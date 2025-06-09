# Settings Page Implementation

## Overview

The Settings page provides a comprehensive interface for managing user preferences, monitoring database availability, and configuring system settings. This feature includes real-time database connection monitoring with automatic polling and manual refresh capabilities.

## Features

### 1. Database Availability Monitoring

- **Real-time Status**: Live monitoring of all configured databases with status indicators (online, offline, error)
- **Connection Testing**: Manual refresh capabilities for individual databases or all databases at once
- **Performance Metrics**: Response time tracking and connection health statistics
- **Error Reporting**: Detailed error messages for failed connections
- **User Permissions**: Database access filtered by user permissions (enterprise-ready)

### 2. User Preferences

- **Theme Settings**: Light, dark, and system theme options
- **Query Behavior**: Auto-save queries, default analyze mode
- **Live Updates**: Configurable polling intervals for database monitoring
- **Notifications**: Enable/disable system notifications

### 3. Security & Privacy

- **Session Management**: View and manage active sessions
- **Data Access Logs**: Audit trail of query and data access history
- **API Access**: Manage API keys and external access

### 4. System Information

- **Agent Status**: Connection status to the AI agent
- **Performance Metrics**: System health and diagnostics
- **Advanced Diagnostics**: Developer tools and configuration export

## Technical Implementation

### Backend Components

#### Database Availability Service (`server/agent/services/database_availability.py`)

- **Polling Mechanism**: Background service that tests database connections every 60 seconds
- **Caching**: Thread-safe caching of database status with timestamps
- **Concurrent Testing**: Parallel connection testing for multiple databases
- **Error Handling**: Graceful handling of connection failures with detailed error messages

#### API Endpoints (`server/agent/api/endpoints.py`)

- `GET /api/agent/databases/availability` - Get all database statuses
- `GET /api/agent/databases/{name}/status` - Get specific database status
- `POST /api/agent/databases/check` - Force refresh database connections
- `GET /api/agent/databases/summary` - Get summary statistics

#### Service Integration (`server/application/__init__.py`)

- Automatic service initialization on application startup
- Graceful shutdown handling
- Error recovery and logging

### Frontend Components

#### Settings Page (`server/web/src/pages/Settings.tsx`)

- **Tabbed Interface**: Organized sections for different settings categories
- **Real-time Updates**: Live polling of database status with configurable intervals
- **Interactive Controls**: Manual refresh buttons and preference toggles
- **Responsive Design**: Mobile-friendly layout with proper spacing

#### Agent Client Extensions (`server/web/src/lib/agent-client.ts`)

- `getDatabaseAvailability()` - Fetch all database statuses
- `getDatabaseStatus()` - Get specific database status
- `forceDatabaseCheck()` - Trigger manual database checks
- `getDatabaseSummary()` - Get summary statistics

#### Navigation Integration (`server/web/src/components/Sidebar.tsx`)

- Settings button in sidebar footer
- React Router navigation to `/settings` route

### Data Models

#### DatabaseStatus Interface

```typescript
interface DatabaseStatus {
  name: string;
  type: string;
  status: 'online' | 'offline' | 'error' | 'checking';
  last_checked: string;
  response_time_ms?: number;
  error_message?: string;
  user_accessible: boolean;
  connection_details?: Record<string, any>;
}
```

#### DatabaseAvailabilityResponse Interface

```typescript
interface DatabaseAvailabilityResponse {
  databases: DatabaseStatus[];
  summary: {
    total_databases: number;
    online: number;
    offline: number;
    errors: number;
    last_check?: string;
    uptime_percentage: number;
  };
}
```

## Configuration

### Database Types Supported

- PostgreSQL
- MongoDB
- Qdrant (Vector Database)
- Slack (via MCP)
- Shopify
- Google Analytics 4

### Default Settings

- **Polling Interval**: 60 seconds for background monitoring
- **Manual Refresh**: Individual database testing on demand
- **Cache Duration**: Real-time with thread-safe updates
- **Error Retention**: Full error messages with timestamps

## Security Considerations

### User Permissions

- Database access filtered by user ID
- Connection details sanitized (passwords masked)
- Audit logging for all database access attempts

### Data Privacy

- No sensitive credentials exposed in API responses
- Connection URIs masked in frontend display
- Secure storage of user preferences in localStorage

## Usage

### Accessing Settings

1. Click the "Settings" button in the sidebar footer
2. Navigate to `/settings` route directly
3. Use keyboard shortcut (future enhancement)

### Database Monitoring

1. **View Status**: Database availability tab shows real-time status
2. **Manual Refresh**: Click "Refresh All" or individual "Test" buttons
3. **Configure Polling**: Adjust refresh interval in preferences
4. **View Details**: Expand database cards for connection details and error messages

### User Preferences

1. **Theme**: Select light, dark, or system theme
2. **Query Behavior**: Toggle auto-save and default analyze mode
3. **Live Updates**: Enable/disable automatic polling
4. **Notifications**: Configure system notifications

## Future Enhancements

### Planned Features

- **Database Performance Metrics**: Historical response time charts
- **Alert System**: Email/Slack notifications for database outages
- **Custom Polling Intervals**: Per-database polling configuration
- **Connection Pooling**: Advanced connection management
- **Backup Status**: Monitor database backup health
- **Query Performance**: Track slow queries and optimization suggestions

### Integration Opportunities

- **Monitoring Dashboards**: Integration with Grafana/Prometheus
- **Incident Management**: Integration with PagerDuty/OpsGenie
- **Compliance Reporting**: SOC 2 audit trail generation
- **Multi-tenant Support**: Enterprise workspace isolation

## Troubleshooting

### Common Issues

1. **Database Not Appearing**: Check configuration in `config.yaml`
2. **Connection Failures**: Verify network connectivity and credentials
3. **Slow Response Times**: Check database server performance
4. **Permission Errors**: Verify user has access to database

### Debug Information

- Check browser console for client-side errors
- Review server logs for database connection issues
- Use "Advanced Diagnostics" in System tab for detailed information

## API Reference

### Database Availability Endpoints

```
GET /api/agent/databases/availability?user_id={id}
GET /api/agent/databases/{name}/status
POST /api/agent/databases/check
GET /api/agent/databases/summary
```

### Response Formats

All endpoints return JSON with consistent error handling and status codes:
- `200` - Success
- `404` - Database not found
- `500` - Server error

## Conclusion

The Settings page provides a comprehensive interface for database monitoring and user preference management. The implementation follows enterprise-grade patterns with proper error handling, security considerations, and scalable architecture. The real-time monitoring capabilities ensure administrators can quickly identify and resolve database connectivity issues. 