import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api';

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const authHeader = request.headers.get('authorization');
    
    if (!authHeader) {
      return NextResponse.json(
        { 
          success: false, 
          message: 'Authentication required'
        },
        { status: 401 }
      );
    }
    
    const body = await request.json();
    
    const response = await fetch(`${API_BASE_URL}/admin/waitlist/${params.id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': authHeader,
      },
      body: JSON.stringify(body),
    });
    
    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error updating waitlist entry:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: 'Failed to update waitlist entry'
      },
      { status: 500 }
    );
  }
} 