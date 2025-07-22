import { NextRequest, NextResponse } from 'next/server';

interface DeploymentRequest {
  userId: string;
  deploymentType: string;
  requirements: {
    company: string;
    environment: string;
    licenseKey: string;
  };
  context: {
    source: string;
    timestamp: string;
  };
}

// Mock license validation - matches the pattern from download route
const validateLicense = async (licenseKey: string): Promise<boolean> => {
  const validPattern = /^CENECA-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/;
  
  const testPatterns = [
    'demo-license',
    'test-license',
    'dev-license',
    /^test-\d+$/,
    /^demo-\d+$/,
    /^dev-\d+$/
  ];
  
  if (validPattern.test(licenseKey)) {
    return true;
  }
  
  for (const pattern of testPatterns) {
    if (typeof pattern === 'string' && pattern === licenseKey) {
      return true;
    }
    if (pattern instanceof RegExp && pattern.test(licenseKey)) {
      return true;
    }
  }
  
  return false;
};

export async function POST(request: NextRequest) {
  try {
    const body: DeploymentRequest = await request.json();
    
    // Validate required fields
    if (!body.userId || !body.deploymentType || !body.requirements?.licenseKey) {
      return NextResponse.json(
        { 
          success: false, 
          error: 'Missing required fields: userId, deploymentType, or licenseKey' 
        }, 
        { status: 400 }
      );
    }

    // Validate license key
    const isValidLicense = await validateLicense(body.requirements.licenseKey);
    if (!isValidLicense) {
      return NextResponse.json(
        { 
          success: false, 
          error: 'Invalid license key' 
        }, 
        { status: 403 }
      );
    }

    // Generate a unique session ID
    const sessionId = `deploy-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // Create deployment session with template editor service
    try {
      // Call the template editor service to create a session
      const templateEditorUrl = process.env.NEXT_PUBLIC_TEMPLATE_EDITOR_URL || 'http://localhost:8501';
      
      const sessionResponse = await fetch(`${templateEditorUrl}/api/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: body.userId,
          deployment_type: body.deploymentType,
          requirements: body.requirements,
          context: {
            ...body.context,
            session_id: sessionId,
            license_key: body.requirements.licenseKey
          }
        }),
      });

      if (!sessionResponse.ok) {
        console.warn('Template editor service not available, using fallback');
        
        // Fallback: return a direct URL to the template editor
        const editorBaseUrl = process.env.NEXT_PUBLIC_TEMPLATE_EDITOR_BASE_URL || 'http://localhost:8500';
        const editorUrl = `${editorBaseUrl}?session=${sessionId}&userId=${encodeURIComponent(body.userId)}&deployment=${body.deploymentType}`;
        
        return NextResponse.json({
          success: true,
          sessionId: sessionId,
          editorUrl: editorUrl,
          message: 'Deployment session created (fallback mode)'
        });
      }

      const sessionData = await sessionResponse.json();
      
      // Construct editor URL with session information
      const editorBaseUrl = process.env.NEXT_PUBLIC_TEMPLATE_EDITOR_BASE_URL || 'http://localhost:8500';
      const editorUrl = `${editorBaseUrl}?session=${sessionData.session_id || sessionId}&userId=${encodeURIComponent(body.userId)}&deployment=${body.deploymentType}`;
      
      return NextResponse.json({
        success: true,
        sessionId: sessionData.session_id || sessionId,
        editorUrl: editorUrl,
        message: 'Deployment session created successfully',
        templateService: {
          connected: true,
          sessionData: sessionData
        }
      });

    } catch (templateServiceError) {
      console.error('Template service connection error:', templateServiceError);
      
      // Fallback: create session without template service
      const editorBaseUrl = process.env.NEXT_PUBLIC_TEMPLATE_EDITOR_BASE_URL || 'http://localhost:8500';
      const editorUrl = `${editorBaseUrl}?session=${sessionId}&userId=${encodeURIComponent(body.userId)}&deployment=${body.deploymentType}`;
      
      return NextResponse.json({
        success: true,
        sessionId: sessionId,
        editorUrl: editorUrl,
        message: 'Deployment session created (template service unavailable)',
        templateService: {
          connected: false,
          error: 'Template editor service connection failed'
        }
      });
    }

  } catch (error) {
    console.error('Error creating deployment session:', error);
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to create deployment session. Please try again.' 
      }, 
      { status: 500 }
    );
  }
}