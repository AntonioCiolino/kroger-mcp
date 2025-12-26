"""
Kroger Cart Partner API tools - Requires special partner-level scopes.

⚠️ WARNING: These tools require PARTNER-LEVEL API access that most developers don't have.
If you're getting CART-2216 errors, you don't have partner access.

Use the standard cart tools (add_to_cart, bulk_add_to_cart) instead, which work with
the standard cart.basic:write scope.

Partner API vs Consumer API:
- Partner API: POST /v1/carts/{cart_id}/items - Requires partner-level scopes
- Consumer API: PUT /v1/cart/add - Works with cart.basic:write scope (RECOMMENDED)

These tools are kept for completeness but are DISABLED by default.
Set KROGER_ENABLE_PARTNER_API=true to enable them.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastmcp import Context
from .shared import get_authenticated_client
import requests


# Check if partner API tools should be enabled
PARTNER_API_ENABLED = os.getenv("KROGER_ENABLE_PARTNER_API", "false").lower() == "true"


async def _make_kroger_api_request(
    method: str, endpoint: str, headers: Dict[str, str] = None, data: str = None
) -> Dict[str, Any]:
    """Make a direct HTTP request to the Kroger API using the authenticated client's token"""
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

        # Check for errors
        if response.status_code not in [200, 201, 204]:
            raise Exception(
                f"API request failed with status {response.status_code}: {response.text}"
            )

        # Return JSON response if there's content
        if response.content:
            return response.json()
        else:
            return {"success": True}

    except Exception as e:
        raise Exception(f"Kroger API request failed: {str(e)}")


def register_tools(mcp):
    """
    Register Kroger Cart Partner API tools with the FastMCP server.
    
    These tools are DISABLED by default because they require partner-level API access.
    Set KROGER_ENABLE_PARTNER_API=true environment variable to enable them.
    """
    
    if not PARTNER_API_ENABLED:
        # Register a single informational tool explaining why partner tools are disabled
        @mcp.tool()
        async def partner_api_info(ctx: Context = None) -> Dict[str, Any]:
            """
            Information about Partner API tools.
            
            Partner API tools are DISABLED because they require special partner-level
            API access that most developers don't have.
            
            Use the standard cart tools instead:
            - add_to_cart: Add a single item to cart
            - bulk_add_to_cart: Add multiple items to cart
            
            To enable Partner API tools (if you have partner access):
            Set environment variable: KROGER_ENABLE_PARTNER_API=true
            
            Returns:
                Information about Partner API status
            """
            return {
                "partner_api_enabled": False,
                "message": "Partner API tools are disabled. Use add_to_cart and bulk_add_to_cart instead.",
                "enable_instructions": "Set KROGER_ENABLE_PARTNER_API=true to enable partner tools",
                "recommended_tools": [
                    "add_to_cart - Add single item (Consumer API)",
                    "bulk_add_to_cart - Add multiple items (Consumer API)",
                    "view_current_cart - View cart contents",
                    "remove_from_cart - Remove item from cart",
                    "clear_cart - Clear all items from cart"
                ]
            }
        return

    # Partner API tools - only registered if KROGER_ENABLE_PARTNER_API=true

    @mcp.tool()
    async def get_user_carts_partner(ctx: Context = None) -> Dict[str, Any]:
        """
        [PARTNER API] Get a list of all carts that belong to an authenticated customer.
        
        ⚠️ Requires partner-level API access. Use view_current_cart for standard access.

        Implements: GET /v1/carts

        Returns:
            Dictionary containing the user's carts list
        """
        try:
            if ctx:
                await ctx.info("Fetching user's carts from Kroger Partner API")

            response = await _make_kroger_api_request(
                method="GET",
                endpoint="/v1/carts",
            )

            if ctx:
                await ctx.info("Successfully retrieved user's carts")

            return {
                "success": True,
                "api_type": "partner",
                "data": response,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to get user carts: {str(e)}")

            error_message = str(e)
            if "401" in error_message or "Unauthorized" in error_message:
                return {
                    "success": False,
                    "error": "Authentication failed. Please run force_reauthenticate and try again.",
                    "details": error_message,
                }
            elif "CART-2216" in error_message:
                return {
                    "success": False,
                    "error": "Partner API access required. Use standard cart tools instead.",
                    "details": error_message,
                    "recommendation": "Use view_current_cart, add_to_cart, bulk_add_to_cart instead"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get user carts: {error_message}",
                }

    @mcp.tool()
    async def create_cart_partner(
        items: Optional[List[Dict[str, Any]]] = None, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        [PARTNER API] Create a new cart for an authenticated customer.
        
        ⚠️ Requires partner-level API access.

        Implements: POST /v1/carts

        Args:
            items: Optional list of items to add to the cart. Each item should have:
                   - upc: The product UPC (required)
                   - quantity: Quantity to add (default: 1)
                   - modality: PICKUP or DELIVERY (default: PICKUP)
                   - allowSubstitutes: Allow substitutes (default: true)
                   - specialInstructions: Special instructions (optional)

        Returns:
            Dictionary containing the created cart information
        """
        try:
            if ctx:
                await ctx.info("Creating new cart via Partner API")

            # Prepare request body
            request_body = {}
            if items:
                formatted_items = []
                for item in items:
                    formatted_item = {
                        "upc": item["upc"],
                        "quantity": item.get("quantity", 1),
                        "modality": item.get("modality", "PICKUP"),
                        "allowSubstitutes": item.get("allowSubstitutes", True),
                    }
                    if "specialInstructions" in item:
                        formatted_item["specialInstructions"] = item["specialInstructions"]
                    formatted_items.append(formatted_item)
                request_body["items"] = formatted_items

            response = await _make_kroger_api_request(
                method="POST",
                endpoint="/v1/carts",
                headers={"Content-Type": "application/json"},
                data=json.dumps(request_body) if request_body else None,
            )

            if ctx:
                await ctx.info("Successfully created cart")

            return {
                "success": True,
                "api_type": "partner",
                "data": response,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to create cart: {str(e)}")

            error_message = str(e)
            if "CART-2216" in error_message:
                return {
                    "success": False,
                    "error": "Partner API access required.",
                    "details": error_message,
                    "recommendation": "Use add_to_cart or bulk_add_to_cart instead"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create cart: {error_message}",
                }

    @mcp.tool()
    async def get_cart_by_id_partner(cart_id: str, ctx: Context = None) -> Dict[str, Any]:
        """
        [PARTNER API] Get a specific cart by ID for an authenticated customer.
        
        ⚠️ Requires partner-level API access.

        Implements: GET /v1/carts/{id}

        Args:
            cart_id: The ID of the cart to retrieve

        Returns:
            Dictionary containing the cart information
        """
        try:
            if ctx:
                await ctx.info(f"Fetching cart {cart_id} via Partner API")

            response = await _make_kroger_api_request(
                method="GET",
                endpoint=f"/v1/carts/{cart_id}",
            )

            if ctx:
                await ctx.info("Successfully retrieved cart")

            return {
                "success": True,
                "api_type": "partner",
                "data": response,
                "cart_id": cart_id,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to get cart: {str(e)}")

            error_message = str(e)
            return {
                "success": False,
                "error": f"Failed to get cart: {error_message}",
                "cart_id": cart_id,
            }

    @mcp.tool()
    async def add_item_to_cart_partner(
        cart_id: str,
        upc: str,
        quantity: int = 1,
        modality: str = "PICKUP",
        allow_substitutes: bool = True,
        special_instructions: Optional[str] = None,
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        [PARTNER API] Add an item to an authenticated customer's cart.
        
        ⚠️ Requires partner-level API access. Use add_to_cart instead for standard access.

        Implements: POST /v1/carts/{id}/items

        Args:
            cart_id: The ID of the cart
            upc: The product UPC to add
            quantity: Quantity to add (default: 1)
            modality: PICKUP or DELIVERY (default: PICKUP)
            allow_substitutes: Allow substitutes (default: true)
            special_instructions: Special instructions for the item (optional)

        Returns:
            Dictionary containing the updated cart information
        """
        try:
            if ctx:
                await ctx.info(f"Adding item {upc} to cart {cart_id} via Partner API")

            request_body = {
                "upc": upc,
                "quantity": quantity,
                "modality": modality,
                "allowSubstitutes": allow_substitutes,
            }
            if special_instructions:
                request_body["specialInstructions"] = special_instructions

            response = await _make_kroger_api_request(
                method="POST",
                endpoint=f"/v1/carts/{cart_id}/items",
                headers={"Content-Type": "application/json"},
                data=json.dumps(request_body),
            )

            if ctx:
                await ctx.info("Successfully added item to cart")

            return {
                "success": True,
                "api_type": "partner",
                "data": response,
                "cart_id": cart_id,
                "upc": upc,
                "quantity": quantity,
                "modality": modality,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to add item to cart: {str(e)}")

            error_message = str(e)
            if "CART-2216" in error_message:
                return {
                    "success": False,
                    "error": "Partner API access required.",
                    "details": error_message,
                    "recommendation": "Use add_to_cart instead"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add item to cart: {error_message}",
                    "cart_id": cart_id,
                    "upc": upc,
                }

    @mcp.tool()
    async def update_cart_item_quantity_partner(
        cart_id: str, upc: str, quantity: int, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        [PARTNER API] Update the quantity of an item in an authenticated customer's cart.
        
        ⚠️ Requires partner-level API access.

        Implements: PUT /v1/carts/{id}/items/{upc}

        Args:
            cart_id: The ID of the cart
            upc: The UPC of the item to update (must be exactly 13 characters)
            quantity: New quantity for the item

        Returns:
            Dictionary confirming the quantity update
        """
        try:
            if ctx:
                await ctx.info(f"Updating item {upc} quantity to {quantity} via Partner API")

            if len(upc) != 13:
                return {
                    "success": False,
                    "error": f"UPC must be exactly 13 characters. Got {len(upc)}.",
                }

            request_body = {"quantity": quantity}

            response = await _make_kroger_api_request(
                method="PUT",
                endpoint=f"/v1/carts/{cart_id}/items/{upc}",
                headers={"Content-Type": "application/json"},
                data=json.dumps(request_body),
            )

            if ctx:
                await ctx.info("Successfully updated item quantity")

            return {
                "success": True,
                "api_type": "partner",
                "message": f"Updated quantity of {upc} to {quantity}",
                "cart_id": cart_id,
                "upc": upc,
                "quantity": quantity,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to update item quantity: {str(e)}")

            return {
                "success": False,
                "error": f"Failed to update item quantity: {str(e)}",
                "cart_id": cart_id,
                "upc": upc,
            }

    @mcp.tool()
    async def delete_cart_item_partner(
        cart_id: str, upc: str, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        [PARTNER API] Delete an item from an authenticated customer's cart.
        
        ⚠️ Requires partner-level API access. Use remove_from_cart instead for standard access.

        Implements: DELETE /v1/carts/{id}/items/{upc}

        Args:
            cart_id: The ID of the cart
            upc: The UPC of the item to delete (must be exactly 13 characters)

        Returns:
            Dictionary confirming the item deletion
        """
        try:
            if ctx:
                await ctx.info(f"Deleting item {upc} from cart {cart_id} via Partner API")

            if len(upc) != 13:
                return {
                    "success": False,
                    "error": f"UPC must be exactly 13 characters. Got {len(upc)}.",
                }

            response = await _make_kroger_api_request(
                method="DELETE",
                endpoint=f"/v1/carts/{cart_id}/items/{upc}",
            )

            if ctx:
                await ctx.info("Successfully deleted item from cart")

            return {
                "success": True,
                "api_type": "partner",
                "message": f"Deleted item {upc} from cart",
                "cart_id": cart_id,
                "upc": upc,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to delete item from cart: {str(e)}")

            return {
                "success": False,
                "error": f"Failed to delete item from cart: {str(e)}",
                "cart_id": cart_id,
                "upc": upc,
            }
