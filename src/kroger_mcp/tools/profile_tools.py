"""
User profile and authentication tools for Kroger MCP server
"""

from typing import Dict, List, Any, Optional
from fastmcp import Context

from .shared import get_authenticated_client, invalidate_authenticated_client


def register_tools(mcp):
    """Register profile-related tools with the FastMCP server"""
    
    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "loyalty_card_number": {"type": "string", "description": "The loyalty card number"},
            "message": {"type": "string", "description": "Confirmation or error message"},
            "raw_data": {"type": "object", "description": "Raw API response data"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def get_user_loyalty_info(ctx: Context = None) -> Dict[str, Any]:
        """
        Get the authenticated user's Kroger loyalty information.
        
        Returns:
            Dictionary containing loyalty card information
        """
        if ctx:
            await ctx.info("Getting user loyalty information")
        
        try:
            client = get_authenticated_client()
            
            # Try to get loyalty info directly
            import requests
            token_info = client.client.token_info
            access_token = token_info.get('access_token')
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            response = requests.get('https://api.kroger.com/v1/identity/profile/loyalty', headers=headers)
            
            if response.status_code == 200:
                loyalty_data = response.json()
                if ctx:
                    await ctx.info(f"Loyalty data retrieved: {loyalty_data}")
                
                if 'data' in loyalty_data and 'loyalty' in loyalty_data['data']:
                    card_number = loyalty_data['data']['loyalty'].get('cardNumber')
                    return {
                        "success": True,
                        "loyalty_card_number": card_number,
                        "message": "Loyalty information retrieved successfully",
                        "raw_data": loyalty_data
                    }
                else:
                    return {
                        "success": False,
                        "message": "No loyalty data found in response"
                    }
            else:
                error_text = response.text
                if ctx:
                    await ctx.error(f"Loyalty API error: {response.status_code} - {error_text}")
                
                return {
                    "success": False,
                    "error": f"API error {response.status_code}: {error_text}",
                    "message": "Failed to retrieve loyalty information. You may need to re-authenticate with loyalty scope."
                }
                
        except Exception as e:
            if ctx:
                await ctx.error(f"Error getting loyalty info: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "profile_id": {"type": "string", "description": "User profile ID"},
            "first_name": {"type": "string", "description": "User's first name"},
            "last_name": {"type": "string", "description": "User's last name"},
            "full_name": {"type": "string", "description": "User's full name"},
            "email": {"type": "string", "description": "User's email address"},
            "message": {"type": "string", "description": "Confirmation or error message"},
            "raw_data": {"type": "object", "description": "Raw profile data for debugging"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def get_user_profile(ctx: Context = None) -> Dict[str, Any]:
        """
        Get the authenticated user's Kroger profile information.
        
        Returns:
            Dictionary containing user profile data
        """
        if ctx:
            await ctx.info("Getting user profile information")
        
        try:
            client = get_authenticated_client()
            profile = client.identity.get_profile()
            
            if ctx:
                await ctx.info(f"Full profile response: {profile}")
            
            if profile and "data" in profile:
                profile_data = profile["data"]
                profile_id = profile_data.get("id", "N/A")
                
                # Check for additional fields that might contain user info
                first_name = profile_data.get("firstName") or profile_data.get("first_name")
                last_name = profile_data.get("lastName") or profile_data.get("last_name") 
                full_name = profile_data.get("name") or profile_data.get("fullName")
                email = profile_data.get("email")
                
                if ctx:
                    await ctx.info(f"Retrieved profile for user ID: {profile_id}")
                    if first_name or last_name or full_name:
                        await ctx.info(f"User name info: first={first_name}, last={last_name}, full={full_name}")
                
                result = {
                    "success": True,
                    "profile_id": profile_id,
                    "message": "User profile retrieved successfully",
                    "raw_data": profile_data  # Include all available data for debugging
                }
                
                # Add name fields if available
                if first_name:
                    result["first_name"] = first_name
                if last_name:
                    result["last_name"] = last_name
                if full_name:
                    result["full_name"] = full_name
                if email:
                    result["email"] = email
                
                return result
            else:
                return {
                    "success": False,
                    "message": "Failed to retrieve user profile"
                }
                
        except Exception as e:
            if ctx:
                await ctx.error(f"Error getting user profile: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the test was successful"},
            "token_valid": {"type": "boolean", "description": "Whether the authentication token is valid"},
            "has_refresh_token": {"type": "boolean", "description": "Whether a refresh token is available"},
            "can_auto_refresh": {"type": "boolean", "description": "Whether token can be automatically refreshed"},
            "message": {"type": "string", "description": "Authentication status message"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success", "token_valid"]
    })
    async def test_authentication(ctx: Context = None) -> Dict[str, Any]:
        """
        Test if the current authentication token is valid.
        
        Returns:
            Dictionary indicating authentication status
        """
        if ctx:
            await ctx.info("Testing authentication token validity")
        
        try:
            client = get_authenticated_client()
            is_valid = client.test_current_token()
            
            if ctx:
                await ctx.info(f"Authentication test result: {'valid' if is_valid else 'invalid'}")
            
            result = {
                "success": True,
                "token_valid": is_valid,
                "message": f"Authentication token is {'valid' if is_valid else 'invalid'}"
            }
            
            # Check for refresh token availability
            if hasattr(client.client, 'token_info') and client.client.token_info:
                has_refresh_token = "refresh_token" in client.client.token_info
                result["has_refresh_token"] = has_refresh_token
                result["can_auto_refresh"] = has_refresh_token
                
                if has_refresh_token:
                    result["message"] += ". Token can be automatically refreshed when it expires."
                else:
                    result["message"] += ". No refresh token available - will need to re-authenticate when token expires."
            
            return result
            
        except Exception as e:
            if ctx:
                await ctx.error(f"Error testing authentication: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "token_valid": False
            }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "authenticated": {"type": "boolean", "description": "Whether user is authenticated"},
            "token_type": {"type": "string", "description": "Type of authentication token"},
            "has_refresh_token": {"type": "boolean", "description": "Whether a refresh token is available"},
            "expires_in": {"type": "integer", "description": "Token expiration time in seconds"},
            "scope": {"type": "string", "description": "OAuth scopes granted"},
            "access_token_preview": {"type": "string", "description": "Preview of access token"},
            "refresh_token_preview": {"type": "string", "description": "Preview of refresh token"},
            "token_file": {"type": "string", "description": "Path to token file"},
            "message": {"type": "string", "description": "Status message"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success", "authenticated"]
    })
    async def get_authentication_info(ctx: Context = None) -> Dict[str, Any]:
        """
        Get information about the current authentication state and token.
        
        Returns:
            Dictionary containing authentication information
        """
        if ctx:
            await ctx.info("Getting authentication information")
        
        try:
            client = get_authenticated_client()
            
            result = {
                "success": True,
                "authenticated": True,
                "message": "User is authenticated"
            }
            
            # Get token information if available
            if hasattr(client.client, 'token_info') and client.client.token_info:
                token_info = client.client.token_info
                
                result.update({
                    "token_type": token_info.get("token_type", "Unknown"),
                    "has_refresh_token": "refresh_token" in token_info,
                    "expires_in": token_info.get("expires_in"),
                    "scope": token_info.get("scope", "Unknown")
                })
                
                # Don't expose the actual tokens for security
                result["access_token_preview"] = f"{token_info.get('access_token', '')[:10]}..." if token_info.get('access_token') else "N/A"
                
                if "refresh_token" in token_info:
                    result["refresh_token_preview"] = f"{token_info['refresh_token'][:10]}..."
            
            # Get token file information if available
            if hasattr(client.client, 'token_file') and client.client.token_file:
                result["token_file"] = client.client.token_file
            
            return result
            
        except Exception as e:
            if ctx:
                await ctx.error(f"Error getting authentication info: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "authenticated": False
            }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "message": {"type": "string", "description": "Confirmation message"},
            "note": {"type": "string", "description": "Additional information about re-authentication"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def force_reauthenticate(ctx: Context = None) -> Dict[str, Any]:
        """
        Force re-authentication by clearing the current authentication token.
        Use this if you're having authentication issues or need to log in as a different user.
        
        Returns:
            Dictionary indicating the re-authentication was initiated
        """
        if ctx:
            await ctx.info("Forcing re-authentication by clearing current token")
        
        try:
            # Clear the current authenticated client
            invalidate_authenticated_client()
            
            if ctx:
                await ctx.info("Authentication token cleared. Next cart operation will trigger re-authentication.")
            
            return {
                "success": True,
                "message": "Authentication token cleared. The next cart operation will open your browser for re-authentication.",
                "note": "You will need to log in again when you next use cart-related tools."
            }
            
        except Exception as e:
            if ctx:
                await ctx.error(f"Error clearing authentication: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
