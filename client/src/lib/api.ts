// API endpoints
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api';

// Waitlist Types
export interface UserData {
  name: string;
  email: string;
  company: string;
}

export interface WaitlistResponse {
  success: boolean;
  data?: {
    userId: string;
    waitlistId: string;
    position: number;
  };
  message?: string;
  error?: string;
}

export interface ApiResponse {
  success: boolean;
  message: string;
  data?: any;
}

// API Functions
export async function registerForWaitlist(userData: UserData): Promise<ApiResponse> {
  try {
    const response = await fetch('/api/waitlist/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(userData),
    });

    return await response.json();
  } catch (error) {
    console.error('Error registering for waitlist:', error);
    return {
      success: false,
      message: 'Failed to register for waitlist. Please try again later.'
    };
  }
}

export async function getWaitlistStatus(userId: string) {
  try {
    const response = await fetch(`${API_BASE_URL}/waitlist/status/${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    return await response.json();
  } catch (error) {
    console.error('Error getting waitlist status:', error);
    return {
      success: false,
      message: 'Network error, please try again later',
    };
  }
}

// Check if user is already in waitlist and their payment status
export async function checkWaitlistStatus(data: { email: string }): Promise<ApiResponse> {
  try {
    const response = await fetch('/api/waitlist/check-status', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    
    return await response.json();
  } catch (error) {
    console.error('Error checking waitlist status:', error);
    return {
      success: false,
      message: 'Failed to check waitlist status. Please try again later.'
    };
  }
} 