import { NextResponse } from 'next/server';

const REDDIT_PIXEL_ID = 'a2_h1mt1445rtou';

// You'll need to securely store this token in an environment variable
// For now, we'll leave it as a placeholder to be replaced with your actual token
const REDDIT_AUTH_TOKEN = process.env.REDDIT_AUTH_TOKEN || '{{Authentication token}}';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { eventType, customEventName, testMode = false } = body;
    
    // Create the current timestamp in ISO 8601 format
    const eventAt = new Date().toISOString();
    
    // Build the request payload based on whether it's a standard or custom event
    let eventData;
    
    if (eventType === 'Custom' && customEventName) {
      // Custom event format
      eventData = {
        test_mode: testMode,
        events: [
          {
            event_at: eventAt,
            event_type: {
              tracking_type: 'Custom',
              custom_event_name: customEventName
            }
          }
        ]
      };
    } else {
      // Standard event format
      eventData = {
        test_mode: testMode,
        events: [
          {
            event_at: eventAt,
            event_type: {
              tracking_type: eventType
            }
          }
        ]
      };
    }
    
    // Make the API request to Reddit
    const response = await fetch(`https://ads-api.reddit.com/api/v2.0/conversions/events/${REDDIT_PIXEL_ID}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${REDDIT_AUTH_TOKEN}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(eventData)
    });
    
    const result = await response.json();
    
    if (!response.ok) {
      return NextResponse.json({ 
        success: false, 
        error: "Failed to track conversion on Reddit", 
        details: result 
      }, { status: response.status });
    }
    
    return NextResponse.json({ 
      success: true, 
      message: "Conversion tracked successfully", 
      data: result 
    });
    
  } catch (error) {
    console.error("Error tracking Reddit conversion:", error);
    return NextResponse.json({ 
      success: false, 
      error: "Server error while tracking conversion" 
    }, { status: 500 });
  }
} 