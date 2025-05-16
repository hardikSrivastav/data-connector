import { NextRequest, NextResponse } from 'next/server';

// Use NEXT_PUBLIC_API_URL as specified in docker-compose.yml
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    if (!body.email) {
      return NextResponse.json(
        { 
          success: false, 
          message: 'Email is required'
        },
        { status: 400 }
      );
    }
    
    console.log(`Connecting to API: ${API_BASE_URL}/waitlist/check-status`);
    
    // Call backend API to check waitlist status
    const response = await fetch(`${API_BASE_URL}/waitlist/check-status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email: body.email }),
    });
    
    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error checking waitlist status:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: 'Failed to check waitlist status'
      },
      { status: 500 }
    );
  }
} 