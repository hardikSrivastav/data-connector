import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api';

export async function GET(request: NextRequest) {
  try {
    const response = await fetch(`${API_BASE_URL}/admin/waitlist`, {
      method: 'GET',
    });
    
    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching waitlist:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: 'Failed to fetch waitlist data'
      },
      { status: 500 }
    );
  }
} 