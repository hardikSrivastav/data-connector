import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_URL || 'http://localhost:3001/api';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    // Log request for debugging
    console.log('Admin login request:', body);
    
    const response = await fetch(`${API_BASE_URL}/admin/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    
    // Log response status for debugging
    console.log('Backend response status:', response.status);
    
    const data = await response.json();
    
    // Log response data for debugging
    console.log('Backend response data:', data);
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Admin login error:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: 'Login failed. Please try again later.'
      },
      { status: 500 }
    );
  }
} 