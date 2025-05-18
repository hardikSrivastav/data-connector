import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    
    // Log web vitals to console in development
    if (process.env.NODE_ENV === 'development') {
      console.log('Web Vitals:', body);
    }
    
    // In production, you would typically:
    // 1. Store this data in a database
    // 2. Send it to an analytics service
    // 3. Or log it to a monitoring system
    
    // Example pseudo-code (commented out):
    /*
    if (process.env.NODE_ENV === 'production') {
      // Send to your analytics/monitoring system
      await fetch('https://your-analytics-endpoint.com/api', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });
    }
    */
    
    return NextResponse.json(
      { success: true },
      { status: 200 }
    );
  } catch (error) {
    console.error('Error logging web vitals:', error);
    return NextResponse.json(
      { success: false },
      { status: 500 }
    );
  }
} 