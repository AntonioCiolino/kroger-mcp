"""
Kroger Cart Consumer API tools - Uses the Consumer API endpoints that work with cart.basic:write scope.

IMPORTANT: This file uses the CONSUMER API endpoints:
- PUT /v1/cart/add - Add items to cart (works with cart.basic:write)

The Partner API endpoints (in cart_tools.py and cart_api_tools.py) require special partner scopes
that most developers don't have access to. Use these Consumer API tools instead.

Consumer API vs Partner API:
- Consumer API: PUT /v1/cart/add - Works with cart.basic:write scope
- Partner API: POST /v1/carts/{cart_id}/items - Requires partner-level scopes (CART-2216 error if missing)
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastmcp import Context
from .shared import get_authenticated_client
import requests


async def _make_kroger_consumer_api_request(
    method: str, endpoint: str, headers: Dict[str, str] = None, data: str = None
) -> Dict[str, Any]:
    """
    Make a direct HTTP request to the Kroger Consumer API.
    
    This uses the Consumer API endpoints which work with standard OAuth scopes
    like cart.basic:write, unlike the Partner API which requires special scopes.
    """
    try:
        client = get_authenticated_client()

        # Get the access token from the client
        token_info = client.client.token_info
        access_token = token_info.get("access_token")

        if not access_token:
            raise Exception("No access token available")

        # Prepare headers
        request_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        # Make the request
        url = f"https://api.kroger.com{endpoint}"

        if method.upper() == "GET":
            response = requests.get(url, headers=request_headers)
        elif method.upper() == "POST":
            response = requests.post(url, headers=request_headers, data=data)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=request_headers, data=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=request_headers)
        else:
            raise Exception(f"Unsupported HTTP method: {method}")

        # Check for errors - Consumer API returns 204 on success for cart operations
        if response.status_code not in [200, 201, 204]:
            raise Exception(
                f"API request failed with status {response.status_code}: {response.text}"
            )

        # Return JSON response if there's content, otherwise success indicator
        if response.content and response.status_code != 204:
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"success": True, "status_code": response.status_code}
        else:
            return {"success": True, "status_code": response.status_code}

    except Exception as e:
        raise Exception(f"Kroger Consumer API request failed: {str(e)}")


def register_tools(mcp):
    """Register Kroger Cart Consumer API tools with the FastMCP server"""

    @mcp.tool()
    async def add_to_cart_consumer(
        upc: str,
        quantity: int = 1,
        modality: str = "PICKUP",
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        Add an item to the user's Kroger cart using the Consumer API.
        
        THIS IS THE RECOMMENDED METHOD for adding items to cart. It uses the Consumer API
        endpoint (PUT /v1/cart/add) which works with the standard cart.basic:write scope.
        
        The Partner API tools (add_items_to_cart, add_item_to_cart) require special partner
        scopes that most developers don't have access to.

        Args:
            upc: The product UPC to add to cart (e.g., "0078142152306")
            quantity: Quantity to add (default: 1)
            modality: Fulfillment method - PICKUP or DELIVERY (default: PICKUP)

        Returns:
            Dictionary confirming the item was added to cart
        """
        try:
            if ctx:
                await ctx.info(
                    f"Adding {quantity}x {upc} to cart via Consumer API with {modality} modality"
                )

            # Prepare the request body for Consumer API
            request_body = {
                "items": [
                    {
                        "upc": upc,
                        "quantity": quantity,
                        "modality": modality
                    }
                ]
            }

            if ctx:
                await ctx.info(f"Request body: {json.dumps(request_body)}")

            # Use Consumer API endpoint
            response = await _make_kroger_consumer_api_request(
                method="PUT",
                endpoint="/v1/cart/add",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(request_body),
            )

            if ctx:
                await ctx.info("Successfully added item to Kroger cart via Consumer API")

            return {
                "success": True,
                "message": f"Successfully added {quantity}x {upc} to cart",
                "upc": upc,
                "quantity": quantity,
                "modality": modality,
                "api_type": "consumer",
                "endpoint": "PUT /v1/cart/add",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to add item to cart: {str(e)}")

            error_message = str(e)
            if "401" in error_message or "Unauthorized" in error_message:
                return {
                    "success": False,
                    "error": "Authentication failed. Please run force_reauthenticate and try again.",
                    "details": error_message,
                }
            elif "400" in error_message or "Bad Request" in error_message:
                return {
                    "success": False,
                    "error": f"Invalid request. Please check the UPC and try again.",
                    "details": error_message,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add item to cart: {error_message}",
                    "upc": upc,
                    "quantity": quantity,
                    "modality": modality,
                }

    @mcp.tool()
    async def bulk_add_to_cart_consumer(
        items: List[Dict[str, Any]], 
        ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Add multiple items to the user's Kroger cart using the Consumer API.
        
        THIS IS THE RECOMMENDED METHOD for bulk adding items. It uses the Consumer API
        endpoint (PUT /v1/cart/add) which works with the standard cart.basic:write scope.

        Args:
            items: List of items to add. Each item should have:
                   - upc: The product UPC (required)
                   - quantity: Quantity to add (default: 1)
                   - modality: PICKUP or DELIVERY (default: PICKUP)

        Returns:
            Dictionary with results for the bulk add operation
        """
        try:
            if ctx:
                await ctx.info(f"Adding {len(items)} items to cart via Consumer API")

            # Format items for Consumer API
            formatted_items = []
            for item in items:
                formatted_items.append({
                    "upc": item.get("upc") or item.get("product_id"),
                    "quantity": item.get("quantity", 1),
                    "modality": item.get("modality", "PICKUP")
                })

            request_body = {"items": formatted_items}

            if ctx:
                await ctx.info(f"Request body: {json.dumps(request_body)}")

            # Use Consumer API endpoint - single call for all items
            response = await _make_kroger_consumer_api_request(
                method="PUT",
                endpoint="/v1/cart/add",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(request_body),
            )

            if ctx:
                await ctx.info(f"Successfully added {len(items)} items to cart via Consumer API")

            return {
                "success": True,
                "message": f"Successfully added {len(items)} items to cart",
                "items_added": len(items),
                "items": formatted_items,
                "api_type": "consumer",
                "endpoint": "PUT /v1/cart/add",
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to bulk add items to cart: {str(e)}")

            error_message = str(e)
            if "401" in error_message or "Unauthorized" in error_message:
                return {
                    "success": False,
                    "error": "Authentication failed. Please run force_reauthenticate and try again.",
                    "details": error_message,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add items to cart: {error_message}",
                    "items_attempted": len(items),
                }
