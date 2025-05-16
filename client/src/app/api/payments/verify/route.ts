import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    
    if (!body.razorpayOrderId || !body.razorpayPaymentId || !body.razorpaySignature) {
      return NextResponse.json(
        { 
          success: false, 
          message: 'Missing verification parameters'
        },
        { status: 400 }
      );
    }
    
    // Ensure we have userId to connect payment to right user
    if (!body.userId) {
      return NextResponse.json(
        { 
          success: false, 
          message: 'User ID is required for payment verification'
        },
        { status: 400 }
      );
    }
    
    // Call backend API to verify payment
    const response = await fetch(`${API_BASE_URL}/payments/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        razorpayOrderId: body.razorpayOrderId,
        razorpayPaymentId: body.razorpayPaymentId,
        razorpaySignature: body.razorpaySignature,
        userId: body.userId
      }),
    });
    
    const data = await response.json();
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error verifying payment:', error);
    return NextResponse.json(
      { 
        success: false, 
        message: 'Failed to verify payment'
      },
      { status: 500 }
    );
  }
} 