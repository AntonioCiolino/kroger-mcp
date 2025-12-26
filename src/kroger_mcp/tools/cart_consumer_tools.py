"""
Kroger Cart tools - Standard Consumer API implementation.

These are the PRIMARY cart tools that work with the standard cart.basic:write OAuth scope.
Use these tools for all cart operations.

API Endpoint: PUT /v1/cart/add

For Partner API tools (requires special partner-level access), see cart_partner_tools.py.
Partner tools are DISABLED by default - set KROGER_ENABLE_PARTNER_API=true to enable them.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from fastmcp import Context
from .shared import get_authenticated_client
import requests


async def _make_kroger_api_request(
    method: str, endpoint: str, headers: Dict[str, str] = None, data: str = None
) -> Dict[str, Any]:
    """
    Make a direct HTTP request to the Kroger API.
    
    Uses the standard Consumer API endpoints which work with standard OAuth scopes
    like cart.basic:write.
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
        raise Exception(f"Kroger API request failed: {str(e)}")


def register_tools(mcp):
    """Register standard Kroger Cart tools with the FastMCP server"""

    @mcp.tool()
    async def add_to_cart(
        upc: str,
        quantity: int = 1,
        modality: str = "PICKUP",
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        Add an item to the user's Kroger cart.
        
        This is the standard method for adding items to cart. Works with the
        cart.basic:write OAuth scope.

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
                    f"Adding {quantity}x {upc} to cart with {modality} modality"
                )

            # Prepare the request body
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

            response = await _make_kroger_api_request(
                method="PUT",
                endpoint="/v1/cart/add",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(request_body),
            )

            if ctx:
                await ctx.info("Successfully added item to Kroger cart")

            return {
                "success": True,
                "message": f"Successfully added {quantity}x {upc} to cart",
                "upc": upc,
                "quantity": quantity,
                "modality": modality,
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
    async def bulk_add_to_cart(
        items: Union[List[Dict[str, Any]], str], 
        ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Add multiple items to the user's Kroger cart.
        
        This is the standard method for bulk adding items. Works with the
        cart.basic:write OAuth scope.

        Args:
            items: List of items to add. Each item should have:
                   - upc: The product UPC (required)
                   - quantity: Quantity to add (default: 1)
                   - modality: PICKUP or DELIVERY (default: PICKUP)
                   
                   Can also accept a JSON string containing {"items": [...], "unavailable": [...]}
                   which will be parsed automatically (common when called from LLM-generated plans).

        Returns:
            Dictionary with results for the bulk add operation
        """
        try:
            # Handle case where items is passed as a JSON string (common from LLM plans)
            if isinstance(items, str):
                if ctx:
                    await ctx.info("Received items as JSON string, parsing...")
                try:
                    parsed = json.loads(items)
                    # Handle {"items": [...], "unavailable": [...]} format from LLM
                    if isinstance(parsed, dict) and "items" in parsed:
                        items = parsed["items"]
                        if ctx and parsed.get("unavailable"):
                            await ctx.info(f"Note: {len(parsed['unavailable'])} items marked unavailable by LLM")
                    elif isinstance(parsed, list):
                        items = parsed
                    else:
                        return {
                            "success": False,
                            "error": "Invalid items format. Expected list or {items: [...]}",
                            "received_type": type(parsed).__name__
                        }
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"Failed to parse items JSON string: {str(e)}",
                        "items_preview": items[:200] if len(items) > 200 else items
                    }
            
            if not items or len(items) == 0:
                return {
                    "success": False,
                    "error": "No items to add to cart",
                    "items_count": 0
                }
            
            if ctx:
                await ctx.info(f"Adding {len(items)} items to cart")

            # Format items
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

            response = await _make_kroger_api_request(
                method="PUT",
                endpoint="/v1/cart/add",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(request_body),
            )

            if ctx:
                await ctx.info(f"Successfully added {len(items)} items to cart")

            return {
                "success": True,
                "message": f"Successfully added {len(items)} items to cart",
                "items_added": len(items),
                "items": formatted_items,
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
    
    # Keep backward compatibility aliases
    @mcp.tool()
    async def add_to_cart_consumer(
        upc: str,
        quantity: int = 1,
        modality: str = "PICKUP",
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        [DEPRECATED] Use add_to_cart instead.
        
        This is an alias for backward compatibility. The _consumer suffix is no longer
        needed since the Consumer API is now the default.
        """
        if ctx:
            await ctx.warning("add_to_cart_consumer is deprecated. Use add_to_cart instead.")
        return await add_to_cart(upc=upc, quantity=quantity, modality=modality, ctx=ctx)

    @mcp.tool()
    async def bulk_add_to_cart_consumer(
        items: List[Dict[str, Any]], 
        ctx: Context = None
    ) -> Dict[str, Any]:
        """
        [DEPRECATED] Use bulk_add_to_cart instead.
        
        This is an alias for backward compatibility. The _consumer suffix is no longer
        needed since the Consumer API is now the default.
        """
        if ctx:
            await ctx.warning("bulk_add_to_cart_consumer is deprecated. Use bulk_add_to_cart instead.")
        return await bulk_add_to_cart(items=items, ctx=ctx)
