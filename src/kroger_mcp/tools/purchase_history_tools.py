"""
Purchase history tools for Kroger MCP server
"""

from typing import Dict, List, Any, Optional
from fastmcp import Context
import requests
from datetime import datetime

from .shared import get_authenticated_client


def register_tools(mcp):
    """Register purchase history tools with the FastMCP server"""

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the search was successful"},
            "purchases": {
                "type": "array",
                "description": "Array of purchase records",
                "items": {"type": "object"}
            },
            "count": {"type": "integer", "description": "Number of purchases found"},
            "meta": {"type": "object", "description": "Metadata about the search results"},
            "loyalty_id": {"type": "string", "description": "The loyalty ID used for the search"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def search_purchase_history(
        loyalty_id: str = None,
        start_date: str = None,
        end_date: str = None,
        store_number: str = None,
        division_number: str = None,
        purchase_type: str = None,
        receipt_type: str = None,
        limit: int = 10,
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        Search purchase history for a customer.

        Args:
            loyalty_id: Customer's loyalty ID (12-13 digits). If not provided, will try to get from profile.
            start_date: Start date for search (YYYY-MM-DD format)
            end_date: End date for search (YYYY-MM-DD format)
            store_number: Filter by store number (5 digits)
            division_number: Filter by division number (3 digits)
            purchase_type: Filter by purchase type (PICKUP, DELIVERY, SHIP, IN_STORE, FUEL_CENTER)
            receipt_type: Filter by receipt type (SALE, REFUND, PARTIAL_SALE)
            limit: Number of results to return (default: 10)

        Returns:
            Dictionary containing purchase history search results
        """
        try:
            if ctx:
                await ctx.info("Searching purchase history")

            client = get_authenticated_client()
            token_info = client.client.token_info
            access_token = token_info.get("access_token")

            if not access_token:
                return {
                    "success": False,
                    "error": "No access token available"
                }

            # If no loyalty_id provided, try to get it from profile
            if not loyalty_id:
                if ctx:
                    await ctx.info("No loyalty ID provided, attempting to get from profile")
                
                # Try to get loyalty info from profile
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/json'
                }
                
                loyalty_response = requests.get(
                    'https://api.kroger.com/v1/identity/profile/loyalty', 
                    headers=headers
                )
                
                if loyalty_response.status_code == 200:
                    loyalty_data = loyalty_response.json()
                    if 'data' in loyalty_data and 'loyalty' in loyalty_data['data']:
                        loyalty_id = loyalty_data['data']['loyalty'].get('cardNumber')
                        if ctx:
                            await ctx.info(f"Retrieved loyalty ID from profile: {loyalty_id}")
                    else:
                        return {
                            "success": False,
                            "error": "No loyalty data found in profile"
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to get loyalty ID from profile. Status: {loyalty_response.status_code}. You may need to re-authenticate with profile.loyalty scope."
                    }

            # Build query parameters
            params = {
                "filter.loyaltyId": loyalty_id,
                "page.size": limit,
                "page.offset": 0
            }

            # Add optional filters
            if start_date and end_date:
                params["filter.transactionDate.range"] = f"({start_date},{end_date})"
            elif start_date:
                params["filter.transactionDate"] = start_date

            if store_number:
                params["filter.storeNumber"] = store_number
            
            if division_number:
                params["filter.divisionNumber"] = division_number
                
            if purchase_type:
                params["filter.purchaseType"] = purchase_type
                
            if receipt_type:
                params["filter.receiptType"] = receipt_type

            # Make API request
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }

            if ctx:
                await ctx.info(f"Making purchase history API request with params: {params}")

            response = requests.get(
                'https://api.kroger.com/purchase-history/v1/search/receipts',
                headers=headers,
                params=params
            )

            if response.status_code == 200:
                data = response.json()
                
                purchases = data.get('data', [])
                meta = data.get('meta', {})
                
                if ctx:
                    await ctx.info(f"Found {len(purchases)} purchase records")

                return {
                    "success": True,
                    "purchases": purchases,
                    "count": len(purchases),
                    "meta": meta,
                    "loyalty_id": loyalty_id
                }
            else:
                error_text = response.text
                if ctx:
                    await ctx.error(f"Purchase history API error: {response.status_code} - {error_text}")
                
                return {
                    "success": False,
                    "error": f"API error {response.status_code}: {error_text}"
                }

        except Exception as e:
            if ctx:
                await ctx.error(f"Error searching purchase history: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "receipts": {
                "type": "array",
                "description": "Array of detailed receipt objects",
                "items": {"type": "object"}
            },
            "count": {"type": "integer", "description": "Number of receipts retrieved"},
            "meta": {"type": "object", "description": "Metadata about the results"},
            "errors": {
                "type": "array",
                "description": "Array of error objects if any receipts failed",
                "items": {"type": "object"}
            },
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def get_receipt_details(
        receipt_keys: List[str],
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        Get detailed receipt information for specific receipt keys.

        Args:
            receipt_keys: List of receipt keys to get details for

        Returns:
            Dictionary containing detailed receipt information
        """
        try:
            if ctx:
                await ctx.info(f"Getting receipt details for {len(receipt_keys)} receipts")

            client = get_authenticated_client()
            token_info = client.client.token_info
            access_token = token_info.get("access_token")

            if not access_token:
                return {
                    "success": False,
                    "error": "No access token available"
                }

            # Build query parameters
            params = {
                "filter.receiptKey": ",".join(receipt_keys)
            }

            # Make API request
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }

            response = requests.get(
                'https://api.kroger.com/purchase-history/v1/receipt-details',
                headers=headers,
                params=params
            )

            if response.status_code == 200:
                data = response.json()
                
                receipts = data.get('data', [])
                meta = data.get('meta', {})
                errors = data.get('errors', [])
                
                if ctx:
                    await ctx.info(f"Retrieved {len(receipts)} receipt details")

                return {
                    "success": True,
                    "receipts": receipts,
                    "count": len(receipts),
                    "meta": meta,
                    "errors": errors
                }
            else:
                error_text = response.text
                if ctx:
                    await ctx.error(f"Receipt details API error: {response.status_code} - {error_text}")
                
                return {
                    "success": False,
                    "error": f"API error {response.status_code}: {error_text}"
                }

        except Exception as e:
            if ctx:
                await ctx.error(f"Error getting receipt details: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the search was successful"},
            "purchases": {
                "type": "array",
                "description": "Array of recent purchase records",
                "items": {"type": "object"}
            },
            "count": {"type": "integer", "description": "Number of purchases found"},
            "meta": {"type": "object", "description": "Metadata about the search results"},
            "loyalty_id": {"type": "string", "description": "The loyalty ID used for the search"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def get_recent_purchases(
        loyalty_id: str = None,
        days: int = 30,
        limit: int = 10,
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        Get recent purchases for a customer.

        Args:
            loyalty_id: Customer's loyalty ID (12-13 digits). If not provided, will try to get from profile.
            days: Number of days back to search (default: 30)
            limit: Number of results to return (default: 10)

        Returns:
            Dictionary containing recent purchase history
        """
        try:
            # Calculate date range
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            if ctx:
                await ctx.info(f"Getting recent purchases from {start_date} to {end_date}")

            return await search_purchase_history(
                loyalty_id=loyalty_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                ctx=ctx
            )

        except Exception as e:
            if ctx:
                await ctx.error(f"Error getting recent purchases: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }