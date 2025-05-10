"""
Middleware for the FastAPI application.
"""
from fastapi import Request, HTTPException, status
from ipaddress import IPv4Network, IPv4Address
from starlette.middleware.base import BaseHTTPMiddleware
from .config import get_settings

class CIDRMiddleware(BaseHTTPMiddleware):
    """
    Middleware to restrict access based on client IP address.
    This can be used to limit access to VPN clients only.
    """
    
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        
        # Skip IP validation when no CIDR blocks are configured
        if not settings.ALLOWED_CIDR_BLOCKS:
            return await call_next(request)
        
        # Get client IP (in production, you'd need to handle X-Forwarded-For)
        client_ip = request.client.host
        
        # For local development, always allow localhost
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return await call_next(request)
            
        # Check if client IP is in any allowed CIDR blocks
        try:
            client_ip_obj = IPv4Address(client_ip)
            allowed_blocks = settings.ALLOWED_CIDR_BLOCKS.split(",")
            
            for cidr_block in allowed_blocks:
                network = IPv4Network(cidr_block.strip())
                if client_ip_obj in network:
                    return await call_next(request)
                    
            # If we get here, IP is not in any allowed block
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: IP not in allowed range"
            )
            
        except ValueError:
            # Handle invalid IP format
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid IP address format"
            ) 