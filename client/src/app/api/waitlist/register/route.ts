import { NextRequest, NextResponse } from 'next/server';

// Use NEXT_PUBLIC_API_URL as specified in docker-compose.yml
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    console.log(`Connecting to API: ${API_BASE_URL}/waitlist/register`);
    
    const response = await fetch(`${API_BASE_URL}/waitlist/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    
    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error registering for waitlist:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: 'Failed to register for waitlist'
      },
      { status: 500 }
    );
  }
} 