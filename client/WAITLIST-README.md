# Paid Waitlist System

A complete solution for implementing a paid waitlist, using Razorpay for payment processing.

## Features

- User registration for waitlist with $5 payment
- Razorpay integration for secure payment processing
- Admin dashboard to manage waitlist entries
- Docker containerization for easy deployment
- PostgreSQL database for data persistence

## Architecture

- **Frontend**: Next.js application
- **Backend**: Node.js/Express API
- **Database**: PostgreSQL
- **Payment Gateway**: Razorpay

## Setup

### Prerequisites

- Node.js 18+ and npm
- Docker and Docker Compose
- Razorpay account with API keys

### Installation

1. Clone this repository:

```bash
git clone <repository-url>
cd client
```

2. Install dependencies:

```bash
npm install
```

3. Run the start script to launch both backend and frontend:

```bash
./start-waitlist.sh
```

## Configuration

### Environment Variables

The system uses environment variables for configuration. You can set these in `.env` files.

#### Backend Environment Variables

Create `landing_routes/.env` file with:

```
PORT=3001
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=waitlist_db
RAZORPAY_KEY_ID=rzp_test_Lpk9B9aflaSSbu
RAZORPAY_KEY_SECRET=KaUCdOrSUX70UJunkRr3097i
JWT_SECRET=admin-secret-key-change-in-production
```

#### Frontend Environment Variables

Create `.env.local` file with:

```
NEXT_PUBLIC_API_URL=http://localhost:3001/api
```

## Usage

### User Flow

1. Users visit the waitlist page
2. They fill out the form with their details
3. Upon submission, they're shown the payment modal
4. After successful payment, they're added to the waitlist

### Admin Dashboard

The admin dashboard is accessible at `/admin` and allows:

- Viewing all waitlist entries
- Checking payment status
- Changing waitlist positions
- Approving or rejecting entries
- Adding notes to entries

Default admin credentials:
- Email: admin@ceneca.ai
- Password: adminPassword

## Development

### Backend API

The backend provides the following API endpoints:

- **POST /api/waitlist/register** - Register for waitlist
- **GET /api/waitlist/status/:userId** - Get waitlist status
- **POST /api/payments/create-order** - Create Razorpay order
- **POST /api/payments/verify** - Verify Razorpay payment
- **POST /api/admin/login** - Admin login
- **GET /api/admin/waitlist** - Get all waitlist entries
- **PATCH /api/admin/waitlist/:id** - Update waitlist entry

### Directory Structure

```
client/                     # Next.js frontend
├── src/
│   ├── app/                # Next.js app router
│   ├── components/         # React components
│   ├── lib/                # Utility functions
│   └── hooks/              # Custom React hooks
├── landing_routes/         # Express backend
│   ├── src/
│   │   ├── config/         # Configuration
│   │   ├── controllers/    # API controllers
│   │   ├── models/         # Database models
│   │   ├── routes/         # API routes
│   │   ├── middlewares/    # Express middlewares
│   │   └── utils/          # Utility functions
│   └── index.js            # Entry point
└── docker/                 # Docker configuration
    ├── docker-compose.yml
    └── backend.Dockerfile
```

## Production Deployment

For production deployment:

1. Update Razorpay API keys to production keys
2. Change JWT_SECRET to a secure random string
3. Use environment variables for sensitive information
4. Set up proper SSL/TLS for secure communication
5. Use a production-grade database setup with backups
6. Implement proper error handling and monitoring

## Security Considerations

- All API keys and secrets are stored as environment variables
- Authentication is required for admin operations
- Payment verification is done server-side
- Database connections are secured
- Containers are isolated for security 