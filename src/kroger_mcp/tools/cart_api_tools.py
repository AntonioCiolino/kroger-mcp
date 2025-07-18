"""
Kroger Cart API tools - Direct API implementation following OpenAPI specification
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastmcp import Context
from .shared import get_authenticated_client
import requests


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
    """Register Kroger Cart API tools with the FastMCP server"""

    @mcp.tool()
    async def get_user_carts(ctx: Context = None) -> Dict[str, Any]:
        """
        Get a list of all carts that belong to an authenticated customer.

        Implements: GET /v1/carts

        Returns:
            Dictionary containing the user's carts list
        """
        try:
            if ctx:
                await ctx.info("Fetching user's carts from Kroger API")

            client = get_authenticated_client()

            # Make direct API request
            response = await _make_kroger_api_request(
                method="GET",
                endpoint="/v1/carts",
            )

            if ctx:
                await ctx.info("Successfully retrieved user's carts")

            return {
                "success": True,
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
            else:
                return {
                    "success": False,
                    "error": f"Failed to get user carts: {error_message}",
                }

    @mcp.tool()
    async def create_cart(
        items: Optional[List[Dict[str, Any]]] = None, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Create a new cart for an authenticated customer.

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
                await ctx.info("Creating new cart")

            client = get_authenticated_client()

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
                        formatted_item["specialInstructions"] = item[
                            "specialInstructions"
                        ]
                    formatted_items.append(formatted_item)
                request_body["items"] = formatted_items

            # Make direct API request
            response = await _make_kroger_api_request(
                method="POST",
                endpoint="/v1/carts",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(request_body) if request_body else None,
            )

            if ctx:
                await ctx.info("Successfully created cart")

            return {
                "success": True,
                "data": response,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to create cart: {str(e)}")

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
                    "error": "Invalid request. Please check the cart data and try again.",
                    "details": error_message,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to create cart: {error_message}",
                }

    @mcp.tool()
    async def get_cart_by_id(cart_id: str, ctx: Context = None) -> Dict[str, Any]:
        """
        Get a specific cart by ID for an authenticated customer.

        Implements: GET /v1/carts/{id}

        Args:
            cart_id: The ID of the cart to retrieve

        Returns:
            Dictionary containing the cart information
        """
        try:
            if ctx:
                await ctx.info(f"Fetching cart with ID: {cart_id}")

            client = get_authenticated_client()

            # Make direct API request
            response = await _make_kroger_api_request(
                method="GET",
                endpoint=f"/v1/carts/{cart_id}",
            )

            if ctx:
                await ctx.info("Successfully retrieved cart")

            return {
                "success": True,
                "data": response,
                "cart_id": cart_id,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to get cart: {str(e)}")

            error_message = str(e)
            if "401" in error_message or "Unauthorized" in error_message:
                return {
                    "success": False,
                    "error": "Authentication failed. Please run force_reauthenticate and try again.",
                    "details": error_message,
                }
            elif "404" in error_message or "Not Found" in error_message:
                return {
                    "success": False,
                    "error": f"Cart with ID {cart_id} not found.",
                    "details": error_message,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to get cart: {error_message}",
                    "cart_id": cart_id,
                }

    @mcp.tool()
    async def update_cart(
        cart_id: str, items: List[Dict[str, Any]], ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Update an authenticated customer's cart by ID.
        This operation only updates items that are already in the cart.

        Implements: PUT /v1/carts/{id}

        Args:
            cart_id: The ID of the cart to update
            items: List of items to update. Each item should have:
                   - upc: The product UPC (required)
                   - quantity: New quantity (required)
                   - modality: PICKUP or DELIVERY (default: PICKUP)
                   - allowSubstitutes: Allow substitutes (default: true)
                   - description: Item description (optional)

        Returns:
            Dictionary containing the updated cart information
        """
        try:
            if ctx:
                await ctx.info(f"Updating cart with ID: {cart_id}")

            client = get_authenticated_client()

            # Prepare request body
            formatted_items = []
            for item in items:
                formatted_item = {
                    "upc": item["upc"],
                    "quantity": item["quantity"],
                    "modality": item.get("modality", "PICKUP"),
                    "allowSubstitutes": item.get("allowSubstitutes", True),
                }
                if "description" in item:
                    formatted_item["description"] = item["description"]
                formatted_items.append(formatted_item)

            request_body = {"items": formatted_items}

            # Make direct API request
            response = await _make_kroger_api_request(
                method="PUT",
                endpoint=f"/v1/carts/{cart_id}",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(request_body),
            )

            if ctx:
                await ctx.info("Successfully updated cart")

            return {
                "success": True,
                "data": response,
                "cart_id": cart_id,
                "items_updated": len(items),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to update cart: {str(e)}")

            error_message = str(e)
            if "401" in error_message or "Unauthorized" in error_message:
                return {
                    "success": False,
                    "error": "Authentication failed. Please run force_reauthenticate and try again.",
                    "details": error_message,
                }
            elif "404" in error_message or "Not Found" in error_message:
                return {
                    "success": False,
                    "error": f"Cart with ID {cart_id} not found.",
                    "details": error_message,
                }
            elif "400" in error_message or "Bad Request" in error_message:
                return {
                    "success": False,
                    "error": "Invalid request. Please check the cart data and try again.",
                    "details": error_message,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to update cart: {error_message}",
                    "cart_id": cart_id,
                }

    @mcp.tool()
    async def add_item_to_cart(
        cart_id: str,
        upc: str,
        quantity: int = 1,
        modality: str = "PICKUP",
        allow_substitutes: bool = True,
        special_instructions: Optional[str] = None,
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        Add an item to an authenticated customer's cart.

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
                await ctx.info(f"Adding item {upc} to cart {cart_id}")

            client = get_authenticated_client()

            # Prepare request body
            request_body = {
                "upc": upc,
                "quantity": quantity,
                "modality": modality,
                "allowSubstitutes": allow_substitutes,
            }
            if special_instructions:
                request_body["specialInstructions"] = special_instructions

            # Make direct API request
            response = await _make_kroger_api_request(
                method="POST",
                endpoint=f"/v1/carts/{cart_id}/items",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(request_body),
            )

            if ctx:
                await ctx.info("Successfully added item to cart")

            return {
                "success": True,
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
            if "401" in error_message or "Unauthorized" in error_message:
                return {
                    "success": False,
                    "error": "Authentication failed. Please run force_reauthenticate and try again.",
                    "details": error_message,
                }
            elif "404" in error_message or "Not Found" in error_message:
                return {
                    "success": False,
                    "error": f"Cart with ID {cart_id} not found.",
                    "details": error_message,
                }
            elif "400" in error_message or "Bad Request" in error_message:
                return {
                    "success": False,
                    "error": "Invalid request. Please check the item data and try again.",
                    "details": error_message,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add item to cart: {error_message}",
                    "cart_id": cart_id,
                    "upc": upc,
                }

    @mcp.tool()
    async def update_cart_item_quantity(
        cart_id: str, upc: str, quantity: int, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Update the quantity of an item in an authenticated customer's cart.

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
                await ctx.info(
                    f"Updating quantity of item {upc} in cart {cart_id} to {quantity}"
                )

            # Validate UPC length
            if len(upc) != 13:
                return {
                    "success": False,
                    "error": f"UPC must be exactly 13 characters long. Provided UPC '{upc}' has {len(upc)} characters.",
                }

            client = get_authenticated_client()

            # Prepare request body
            request_body = {"quantity": quantity}

            # Make direct API request
            response = await _make_kroger_api_request(
                method="PUT",
                endpoint=f"/v1/carts/{cart_id}/items/{upc}",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(request_body),
            )

            if ctx:
                await ctx.info("Successfully updated item quantity")

            return {
                "success": True,
                "message": f"Successfully updated quantity of item {upc} to {quantity}",
                "cart_id": cart_id,
                "upc": upc,
                "quantity": quantity,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to update item quantity: {str(e)}")

            error_message = str(e)
            if "401" in error_message or "Unauthorized" in error_message:
                return {
                    "success": False,
                    "error": "Authentication failed. Please run force_reauthenticate and try again.",
                    "details": error_message,
                }
            elif "404" in error_message or "Not Found" in error_message:
                return {
                    "success": False,
                    "error": f"Cart with ID {cart_id} or item with UPC {upc} not found.",
                    "details": error_message,
                }
            elif "400" in error_message or "Bad Request" in error_message:
                return {
                    "success": False,
                    "error": "Invalid request. Please check the cart ID, UPC, and quantity.",
                    "details": error_message,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to update item quantity: {error_message}",
                    "cart_id": cart_id,
                    "upc": upc,
                }

    @mcp.tool()
    async def delete_cart_item(
        cart_id: str, upc: str, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Delete an item from an authenticated customer's cart.

        Implements: DELETE /v1/carts/{id}/items/{upc}

        Args:
            cart_id: The ID of the cart
            upc: The UPC of the item to delete (must be exactly 13 characters)

        Returns:
            Dictionary confirming the item deletion
        """
        try:
            if ctx:
                await ctx.info(f"Deleting item {upc} from cart {cart_id}")

            # Validate UPC length
            if len(upc) != 13:
                return {
                    "success": False,
                    "error": f"UPC must be exactly 13 characters long. Provided UPC '{upc}' has {len(upc)} characters.",
                }

            client = get_authenticated_client()

            # Make direct API request
            response = await _make_kroger_api_request(
                method="DELETE",
                endpoint=f"/v1/carts/{cart_id}/items/{upc}",
            )

            if ctx:
                await ctx.info("Successfully deleted item from cart")

            return {
                "success": True,
                "message": f"Successfully deleted item {upc} from cart",
                "cart_id": cart_id,
                "upc": upc,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to delete item from cart: {str(e)}")

            error_message = str(e)
            if "401" in error_message or "Unauthorized" in error_message:
                return {
                    "success": False,
                    "error": "Authentication failed. Please run force_reauthenticate and try again.",
                    "details": error_message,
                }
            elif "404" in error_message or "Not Found" in error_message:
                return {
                    "success": False,
                    "error": f"Cart with ID {cart_id} or item with UPC {upc} not found.",
                    "details": error_message,
                }
            elif "400" in error_message or "Bad Request" in error_message:
                return {
                    "success": False,
                    "error": "Invalid request. Please check the cart ID and UPC.",
                    "details": error_message,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to delete item from cart: {error_message}",
                    "cart_id": cart_id,
                    "upc": upc,
                }
