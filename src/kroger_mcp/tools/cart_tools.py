"""
Cart tracking and management functionality
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List

from fastmcp import Context
from .shared import get_authenticated_client
import requests


# Cart storage file
CART_FILE = "kroger_cart.json"
ORDER_HISTORY_FILE = "kroger_order_history.json"


def _load_cart_data() -> Dict[str, Any]:
    """Load cart data from file"""
    try:
        if os.path.exists(CART_FILE):
            with open(CART_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"current_cart": [], "last_updated": None, "preferred_location_id": None}


def _save_cart_data(cart_data: Dict[str, Any]) -> None:
    """Save cart data to file"""
    try:
        with open(CART_FILE, "w") as f:
            json.dump(cart_data, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save cart data: {e}")


def _load_order_history() -> List[Dict[str, Any]]:
    """Load order history from file"""
    try:
        if os.path.exists(ORDER_HISTORY_FILE):
            with open(ORDER_HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_order_history(history: List[Dict[str, Any]]) -> None:
    """Save order history to file"""
    try:
        with open(ORDER_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save order history: {e}")


def _add_item_to_local_cart(
    product_id: str,
    quantity: int,
    modality: str,
    product_details: Dict[str, Any] = None,
) -> None:
    """Add an item to the local cart tracking"""
    cart_data = _load_cart_data()
    current_cart = cart_data.get("current_cart", [])

    # Check if item already exists in cart
    existing_item = None
    for item in current_cart:
        if item.get("product_id") == product_id and item.get("modality") == modality:
            existing_item = item
            break

    if existing_item:
        # Update existing item quantity
        existing_item["quantity"] = existing_item.get("quantity", 0) + quantity
        existing_item["last_updated"] = datetime.now().isoformat()
    else:
        # Add new item
        new_item = {
            "product_id": product_id,
            "quantity": quantity,
            "modality": modality,
            "added_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
        }

        # Add product details if provided
        if product_details:
            new_item.update(product_details)

        current_cart.append(new_item)

    cart_data["current_cart"] = current_cart
    cart_data["last_updated"] = datetime.now().isoformat()
    _save_cart_data(cart_data)


async def _make_kroger_api_request(
    method: str, 
    endpoint: str, 
    headers: Dict[str, str] = None, 
    data: str = None
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
            raise Exception(f"API request failed with status {response.status_code}: {response.text}")
        
        # Return JSON response if there's content
        if response.content:
            return response.json()
        else:
            return {"success": True}
            
    except Exception as e:
        raise Exception(f"Kroger API request failed: {str(e)}")


async def _fetch_kroger_cart() -> Dict[str, Any]:
    """Fetch the actual cart from Kroger API"""
    try:
        return await _make_kroger_api_request("GET", "/v1/carts")
    except Exception as e:
        print(f"Error fetching Kroger cart: {e}")
        return {"error": str(e)}


async def clear_cart() -> Dict[str, Any]:
    """
    Clear all items from the actual Kroger cart using the Partner API.
    Standalone function for web UI usage.
    """
    try:
        client = get_authenticated_client()

        # Get the current cart to see what items need to be removed
        carts_response = await _make_kroger_api_request(
            method="GET",
            endpoint="/v1/carts",
        )

        if (
            not carts_response
            or "data" not in carts_response
            or not carts_response["data"]
        ):
            return {
                "success": True,
                "message": "No cart found to clear",
                "kroger_items_cleared": 0,
                "kroger_items_total": 0,
            }

        # Get the first (active) cart
        kroger_cart = carts_response["data"][0]
        cart_id = kroger_cart["id"]

        # Count items in Kroger cart before clearing
        kroger_items_count = len(kroger_cart.get("items", []))
        kroger_items_cleared = 0

        # Remove each item from the Kroger cart using Partner API
        if "items" in kroger_cart and kroger_cart["items"]:
            for item in kroger_cart["items"]:
                upc = item.get("upc")
                if upc:
                    try:
                        # Use Partner API to remove item from Kroger cart
                        await _make_kroger_api_request(
                            method="DELETE",
                            endpoint=f"/v1/carts/{cart_id}/items/{upc}",
                        )
                        kroger_items_cleared += 1
                    except Exception as item_error:
                        print(f"Warning: Error removing item {upc}: {str(item_error)}")

        return {
            "success": True,
            "message": f"Successfully cleared {kroger_items_cleared} items from Kroger cart",
            "kroger_items_cleared": kroger_items_cleared,
            "kroger_items_total": kroger_items_count,
            "cart_id": cart_id,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
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
                "error": f"Failed to clear cart: {error_message}",
            }


def register_tools(mcp):
    """Register cart-related tools with the FastMCP server"""

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "Whether the item was successfully added"
            },
            "message": {
                "type": "string",
                "description": "Confirmation or error message"
            },
            "product_id": {
                "type": "string",
                "description": "The product ID/UPC that was added"
            },
            "quantity": {
                "type": "integer",
                "description": "Quantity added"
            },
            "modality": {
                "type": "string",
                "description": "Fulfillment method (PICKUP or DELIVERY)"
            },
            "cart_id": {
                "type": ["string", "null"],
                "description": "The Kroger cart ID"
            },
            "timestamp": {
                "type": "string",
                "description": "ISO timestamp of when item was added"
            },
            "error": {
                "type": "string",
                "description": "Error message (when success=false)"
            },
            "details": {
                "type": "string",
                "description": "Additional error details"
            }
        },
        "required": ["success"]
    })
    async def add_to_cart(
        upc: str,
        quantity: int = 1,
        modality: str = "PICKUP",
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        Add a single item to the user's Kroger cart using the Partner API.

        This is the primary tool for adding items to cart. Use the UPC from search_products_compact.

        If the user doesn't specifically indicate a preference for pickup or delivery,
        you should ask them which modality they prefer before calling this tool.

        Args:
            upc: The product UPC code to add to cart (from search_products_compact results)
            quantity: Quantity to add (default: 1)
            modality: Fulfillment method - PICKUP or DELIVERY

        Returns:
            Dictionary confirming the item was added to cart
        """
        try:
            if ctx:
                await ctx.info(
                    f"Adding {quantity}x {upc} to cart with {modality} modality"
                )

            client = get_authenticated_client()

            # First, get or create a cart
            carts_response = await _make_kroger_api_request(
                method="GET",
                endpoint="/v1/carts",
            )

            cart_id = None
            if carts_response and "data" in carts_response and carts_response["data"]:
                # Use existing cart
                cart_id = carts_response["data"][0]["id"]
                if ctx:
                    await ctx.info(f"Using existing cart: {cart_id}")
            else:
                # Create new cart
                if ctx:
                    await ctx.info("No cart found, creating new cart")
                
                create_response = await _make_kroger_api_request(
                    method="POST",
                    endpoint="/v1/carts",
                    headers={
                        "Content-Type": "application/json",
                    },
                    data=json.dumps({}),
                )
                
                if create_response and "data" in create_response:
                    cart_id = create_response["data"]["id"]
                    if ctx:
                        await ctx.info(f"Created new cart: {cart_id}")
                else:
                    raise Exception("Failed to create cart")

            # Add item to cart using Partner API
            item_data = {
                "upc": upc,
                "quantity": quantity,
                "modality": modality,
                "allowSubstitutes": True,
            }

            if ctx:
                await ctx.info(f"Adding item to cart {cart_id}: {item_data}")

            response = await _make_kroger_api_request(
                method="POST",
                endpoint=f"/v1/carts/{cart_id}/items",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(item_data),
            )

            if ctx:
                await ctx.info("Successfully added item to Kroger cart via Partner API")

            return {
                "success": True,
                "message": f"Successfully added {quantity}x {upc} to cart",
                "product_id": upc,
                "quantity": quantity,
                "modality": modality,
                "cart_id": cart_id,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to add item to cart: {str(e)}")

            # Provide helpful error message for authentication issues
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
                    "product_id": upc,
                    "quantity": quantity,
                    "modality": modality,
                }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "Whether the item was successfully added"
            },
            "message": {
                "type": "string",
                "description": "Confirmation or error message"
            },
            "product_id": {
                "type": "string",
                "description": "The product ID/UPC that was added"
            },
            "quantity": {
                "type": "integer",
                "description": "Quantity added"
            },
            "modality": {
                "type": "string",
                "description": "Fulfillment method (PICKUP or DELIVERY)"
            },
            "cart_id": {
                "type": "string",
                "description": "The Kroger cart ID"
            },
            "timestamp": {
                "type": "string",
                "description": "ISO timestamp of when item was added"
            },
            "error": {
                "type": "string",
                "description": "Error message (when success=false)"
            },
            "details": {
                "type": "string",
                "description": "Additional error details"
            }
        },
        "required": ["success"]
    })
    async def add_items_to_cart(
        product_id: str,
        quantity: int = 1,
        modality: str = "PICKUP",
        ctx: Context = None,
    ) -> Dict[str, Any]:
        """
        Add a single item to the user's Kroger cart using the Partner API.

        If the user doesn't specifically indicate a preference for pickup or delivery,
        you should ask them which modality they prefer before calling this tool.

        Args:
            product_id: The product ID or UPC to add to cart
            quantity: Quantity to add (default: 1)
            modality: Fulfillment method - PICKUP or DELIVERY

        Returns:
            Dictionary confirming the item was added to cart
        """
        try:
            if ctx:
                await ctx.info(
                    f"Adding {quantity}x {product_id} to cart with {modality} modality"
                )

            client = get_authenticated_client()

            # First, get or create a cart
            carts_response = await _make_kroger_api_request(
                method="GET",
                endpoint="/v1/carts",
            )

            cart_id = None
            if carts_response and "data" in carts_response and carts_response["data"]:
                # Use existing cart
                cart_id = carts_response["data"][0]["id"]
                if ctx:
                    await ctx.info(f"Using existing cart: {cart_id}")
            else:
                # Create new cart
                if ctx:
                    await ctx.info("No cart found, creating new cart")
                
                create_response = await _make_kroger_api_request(
                    method="POST",
                    endpoint="/v1/carts",
                    headers={
                        "Content-Type": "application/json",
                    },
                    data=json.dumps({}),
                )
                
                if create_response and "data" in create_response:
                    cart_id = create_response["data"]["id"]
                    if ctx:
                        await ctx.info(f"Created new cart: {cart_id}")
                else:
                    raise Exception("Failed to create cart")

            # Add item to cart using Partner API
            item_data = {
                "upc": product_id,
                "quantity": quantity,
                "modality": modality,
                "allowSubstitutes": True,
            }

            if ctx:
                await ctx.info(f"Adding item to cart {cart_id}: {item_data}")

            response = await _make_kroger_api_request(
                method="POST",
                endpoint=f"/v1/carts/{cart_id}/items",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(item_data),
            )

            if ctx:
                await ctx.info("Successfully added item to Kroger cart via Partner API")

            return {
                "success": True,
                "message": f"Successfully added {quantity}x {product_id} to cart",
                "product_id": product_id,
                "quantity": quantity,
                "modality": modality,
                "cart_id": cart_id,
                "timestamp": datetime.now().isoformat(),
                "api_response": response,
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to add item to cart: {str(e)}")

            # Provide helpful error message for authentication issues
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
                    "error": f"Invalid request. Please check the product ID and try again.",
                    "details": error_message,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add item to cart: {error_message}",
                    "product_id": product_id,
                    "quantity": quantity,
                    "modality": modality,
                }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "Whether the bulk add operation was successful (true if all items added)"
            },
            "message": {
                "type": "string",
                "description": "Summary message of the operation"
            },
            "items_added": {
                "type": "integer",
                "description": "Number of items successfully added to cart"
            },
            "items_failed": {
                "type": "integer",
                "description": "Number of items that failed to add"
            },
            "successful_items": {
                "type": "array",
                "description": "List of successfully added items",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "quantity": {"type": "integer"},
                        "modality": {"type": "string"}
                    }
                }
            },
            "failed_items": {
                "type": "array",
                "description": "List of items that failed to add",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "error": {"type": "string"}
                    }
                }
            },
            "cart_id": {
                "type": "string",
                "description": "The Kroger cart ID"
            },
            "timestamp": {
                "type": "string",
                "description": "ISO timestamp of the operation"
            },
            "error": {
                "type": "string",
                "description": "Error message (when success=false)"
            },
            "items_attempted": {
                "type": "integer",
                "description": "Total number of items attempted (when operation fails)"
            }
        },
        "required": ["success"]
    })
    async def bulk_add_to_cart_partner(
        items: List[Dict[str, Any]], ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Add multiple items to the user's Kroger cart using the Partner API.
        
        NOTE: This uses the Partner API (POST /v1/carts/{cart_id}/items) which requires
        special partner-level access. For standard usage, use bulk_add_to_cart instead
        which uses the Consumer API (PUT /v1/cart/add).

        If the user doesn't specifically indicate a preference for pickup or delivery,
        you should ask them which modality they prefer before calling this tool.

        Args:
            items: List of items to add. Each item should have:
                   - product_id: The product ID or UPC
                   - quantity: Quantity to add (default: 1)
                   - modality: PICKUP or DELIVERY (default: PICKUP)

        Returns:
            Dictionary with results for each item
        """
        try:
            if ctx:
                await ctx.info(f"Adding {len(items)} items to cart in bulk")

            client = get_authenticated_client()

            # First, get or create a cart
            carts_response = await _make_kroger_api_request(
                method="GET",
                endpoint="/v1/carts",
            )

            cart_id = None
            if carts_response and "data" in carts_response and carts_response["data"]:
                # Use existing cart
                cart_id = carts_response["data"][0]["id"]
                if ctx:
                    await ctx.info(f"Using existing cart: {cart_id}")
            else:
                # Create new cart
                if ctx:
                    await ctx.info("No cart found, creating new cart")
                
                create_response = await _make_kroger_api_request(
                    method="POST",
                    endpoint="/v1/carts",
                    headers={
                        "Content-Type": "application/json",
                    },
                    data=json.dumps({}),
                )
                
                if create_response and "data" in create_response:
                    cart_id = create_response["data"]["id"]
                    if ctx:
                        await ctx.info(f"Created new cart: {cart_id}")
                else:
                    raise Exception("Failed to create cart")

            # Add items one by one using Partner API
            successful_items = []
            failed_items = []

            for item in items:
                try:
                    item_data = {
                        "upc": item["product_id"],
                        "quantity": item.get("quantity", 1),
                        "modality": item.get("modality", "PICKUP"),
                        "allowSubstitutes": True,
                    }

                    if ctx:
                        await ctx.info(f"Adding item to cart: {item_data}")

                    response = await _make_kroger_api_request(
                        method="POST",
                        endpoint=f"/v1/carts/{cart_id}/items",
                        headers={
                            "Content-Type": "application/json",
                        },
                        data=json.dumps(item_data),
                    )

                    successful_items.append({
                        "product_id": item["product_id"],
                        "quantity": item.get("quantity", 1),
                        "modality": item.get("modality", "PICKUP"),
                        "response": response
                    })

                except Exception as item_error:
                    if ctx:
                        await ctx.warning(f"Failed to add item {item['product_id']}: {str(item_error)}")
                    
                    failed_items.append({
                        "product_id": item["product_id"],
                        "error": str(item_error)
                    })

            if ctx:
                await ctx.info(f"Bulk add complete: {len(successful_items)} successful, {len(failed_items)} failed")

            return {
                "success": len(failed_items) == 0,
                "message": f"Added {len(successful_items)} of {len(items)} items to cart",
                "items_added": len(successful_items),
                "items_failed": len(failed_items),
                "successful_items": successful_items,
                "failed_items": failed_items,
                "cart_id": cart_id,
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

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "current_cart": {
                "type": "array",
                "description": "Array of cart items",
                "items": {"type": "object"}
            },
            "cart_id": {"type": "string", "description": "The Kroger cart ID"},
            "summary": {
                "type": "object",
                "properties": {
                    "total_items": {"type": "integer"},
                    "total_quantity": {"type": "integer"},
                    "pickup_items": {"type": "integer"},
                    "delivery_items": {"type": "integer"},
                    "cart_exists": {"type": "boolean"}
                }
            },
            "raw_response": {"type": "object", "description": "Raw API response"},
            "message": {"type": "string", "description": "Message when no cart found or error"},
            "error": {"type": "string", "description": "Error details"},
            "details": {"type": "string", "description": "Additional error details"}
        },
        "required": ["success"]
    })
    async def view_current_cart(ctx: Context = None) -> Dict[str, Any]:
        """
        View the current cart contents from the Kroger API.

        This tool fetches the actual cart from Kroger's servers, not local tracking.

        Returns:
            Dictionary containing current cart items and summary
        """
        try:
            if ctx:
                await ctx.info("Fetching current cart from Kroger API")

            client = get_authenticated_client()

            # Get carts from Kroger API
            response = await _make_kroger_api_request(
                method="GET",
                endpoint="/v1/carts",
            )

            if ctx:
                await ctx.info("Successfully retrieved cart from Kroger API")

            # Process the response
            if not response or "data" not in response or not response["data"]:
                return {
                    "success": True,
                    "current_cart": [],
                    "summary": {
                        "total_items": 0,
                        "total_quantity": 0,
                        "pickup_items": 0,
                        "delivery_items": 0,
                        "cart_exists": False,
                    },
                    "message": "No cart found"
                }

            # Get the first (active) cart
            kroger_cart = response["data"][0]
            cart_items = kroger_cart.get("items", [])

            # Calculate summary
            total_quantity = sum(item.get("quantity", 0) for item in cart_items)
            pickup_items = [
                item for item in cart_items if item.get("modality") == "PICKUP"
            ]
            delivery_items = [
                item for item in cart_items if item.get("modality") == "DELIVERY"
            ]

            return {
                "success": True,
                "current_cart": cart_items,
                "cart_id": kroger_cart.get("id"),
                "summary": {
                    "total_items": len(cart_items),
                    "total_quantity": total_quantity,
                    "pickup_items": len(pickup_items),
                    "delivery_items": len(delivery_items),
                    "cart_exists": True,
                },
                "raw_response": kroger_cart
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to view cart: {str(e)}")

            error_message = str(e)
            if "401" in error_message or "Unauthorized" in error_message:
                return {
                    "success": False,
                    "error": "Authentication failed. Please run force_reauthenticate and try again.",
                    "details": error_message,
                }
            else:
                return {"success": False, "error": f"Failed to view cart: {error_message}"}

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "message": {"type": "string", "description": "Confirmation or error message"},
            "items_removed": {"type": "integer", "description": "Number of items removed"},
            "product_id": {"type": "string", "description": "The product ID that was removed"},
            "modality": {"type": ["string", "null"], "description": "The modality that was removed"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def remove_from_local_cart_tracking(
        product_id: str, modality: str = None, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Remove an item from the local cart tracking only.

        IMPORTANT: This tool CANNOT remove items from the actual Kroger cart in the app/website.
        It only updates our local tracking to stay in sync. The user must remove the item from
        their actual cart through the Kroger app or website themselves.

        Use this tool only when:
        1. The user has already removed an item from their Kroger cart through the app/website
        2. You need to update the local tracking to reflect that change

        Args:
            product_id: The product ID to remove
            modality: Specific modality to remove (if None, removes all instances)

        Returns:
            Dictionary confirming the removal from local tracking
        """
        try:
            cart_data = _load_cart_data()
            current_cart = cart_data.get("current_cart", [])
            original_count = len(current_cart)

            if modality:
                # Remove specific modality
                cart_data["current_cart"] = [
                    item
                    for item in current_cart
                    if not (
                        item.get("product_id") == product_id
                        and item.get("modality") == modality
                    )
                ]
            else:
                # Remove all instances
                cart_data["current_cart"] = [
                    item
                    for item in current_cart
                    if item.get("product_id") != product_id
                ]

            items_removed = original_count - len(cart_data["current_cart"])

            if items_removed > 0:
                cart_data["last_updated"] = datetime.now().isoformat()
                _save_cart_data(cart_data)

            if ctx:
                await ctx.info(
                    f"Removed {items_removed} items from local cart tracking"
                )

            return {
                "success": True,
                "message": f"Removed {items_removed} items from local cart tracking",
                "items_removed": items_removed,
                "product_id": product_id,
                "modality": modality,
            }
        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to remove from local cart tracking: {str(e)}")
            return {"success": False, "error": f"Failed to remove from cart: {str(e)}"}

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "message": {"type": "string", "description": "Confirmation or error message"},
            "kroger_items_removed": {"type": "integer", "description": "Number of items removed from Kroger cart"},
            "product_id": {"type": "string", "description": "The product ID that was removed"},
            "modality": {"type": ["string", "null"], "description": "The modality that was removed"},
            "cart_id": {"type": "string", "description": "The Kroger cart ID"},
            "summary": {"type": "object", "description": "Summary of removal operation"},
            "error": {"type": "string", "description": "Error message"},
            "details": {"type": "string", "description": "Additional error details"}
        },
        "required": ["success"]
    })
    async def remove_from_cart(
        product_id: str, modality: str = None, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Remove an item from the actual Kroger cart using the Partner API.

        This function uses the Partner API to remove items from your actual Kroger cart.
        This is the recommended way to remove items since it uses the official API.

        Requires authentication with cart.basic:write scope.

        Args:
            product_id: The product ID/UPC to remove
            modality: Specific modality to remove (if None, removes all instances)

        Returns:
            Dictionary confirming the removal from Kroger cart
        """
        try:
            if ctx:
                await ctx.info(f"🗑️ Removing item {product_id} from Kroger cart...")

            client = get_authenticated_client()

            if ctx:
                await ctx.info("✅ Client authenticated successfully")
                await ctx.info("📋 Fetching current cart from Kroger API...")

            # Get the current cart to find the item
            carts_response = await _make_kroger_api_request(
                method="GET",
                endpoint="/v1/carts",
            )

            if ctx:
                await ctx.info("📋 Cart API response received successfully")

            if (
                not carts_response
                or "data" not in carts_response
                or not carts_response["data"]
            ):
                if ctx:
                    await ctx.info("✅ No Kroger cart found")
                return {
                    "success": True,
                    "message": "No cart found - item already removed or doesn't exist",
                    "kroger_items_removed": 0,
                }

            # Get the first (active) cart
            kroger_cart = carts_response["data"][0]
            cart_id = kroger_cart["id"]

            kroger_items_removed = 0

            if ctx:
                await ctx.info(
                    f"📋 Found Kroger cart, searching for item {product_id}"
                )

            # Find and remove the item from the Kroger cart using Partner API
            if "items" in kroger_cart and kroger_cart["items"]:
                for item in kroger_cart["items"]:
                    upc = item.get("upc")
                    if upc == product_id:
                        try:
                            # Use Partner API to remove item from Kroger cart
                            await _make_kroger_api_request(
                                method="DELETE",
                                endpoint=f"/v1/carts/{cart_id}/items/{upc}",
                            )

                            kroger_items_removed += 1
                            if ctx:
                                await ctx.info(
                                    f"✅ Removed item {upc} from Kroger cart"
                                )

                        except Exception as item_error:
                            if ctx:
                                await ctx.warning(
                                    f"⚠️ Error removing item {upc}: {str(item_error)}"
                                )

            if ctx:
                await ctx.info(f"🧹 Removal complete!")
                await ctx.info(
                    f"📊 Summary: {kroger_items_removed} items removed from Kroger cart"
                )

            # Create detailed message
            if kroger_items_removed > 0:
                kroger_status = f"✅ Removed {kroger_items_removed} item(s) from Kroger cart"
            else:
                kroger_status = f"ℹ️ Item not found in Kroger cart"

            return {
                "success": True,
                "message": kroger_status,
                "kroger_items_removed": kroger_items_removed,
                "product_id": product_id,
                "modality": modality,
                "cart_id": cart_id,
                "summary": {
                    "kroger_cart": f"{kroger_items_removed} items removed",
                },
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to remove from cart: {str(e)}")

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
                    "error": f"Failed to remove from cart: {error_message}",
                    "product_id": product_id,
                }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "message": {"type": "string", "description": "Confirmation or error message"},
            "items_cleared": {"type": "integer", "description": "Number of items cleared from local tracking"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def clear_local_cart_tracking(ctx: Context = None) -> Dict[str, Any]:
        """
        Clear all items from the local cart tracking only.

        IMPORTANT: This tool CANNOT remove items from the actual Kroger cart in the app/website.
        It only clears our local tracking. The user must remove items from their actual cart
        through the Kroger app or website themselves.

        Use this tool only when:
        1. The user has already cleared their Kroger cart through the app/website
        2. You need to update the local tracking to reflect that change
        3. Or when the local tracking is out of sync with the actual cart

        Returns:
            Dictionary confirming the local cart tracking was cleared
        """
        try:
            cart_data = _load_cart_data()
            items_count = len(cart_data.get("current_cart", []))

            cart_data["current_cart"] = []
            cart_data["last_updated"] = datetime.now().isoformat()
            _save_cart_data(cart_data)

            if ctx:
                await ctx.info(f"Cleared {items_count} items from local cart tracking")

            return {
                "success": True,
                "message": f"Cleared {items_count} items from local cart tracking",
                "items_cleared": items_count,
            }
        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to clear local cart tracking: {str(e)}")
            return {"success": False, "error": f"Failed to clear cart: {str(e)}"}

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "message": {"type": "string", "description": "Confirmation or error message"},
            "kroger_items_cleared": {"type": "integer", "description": "Number of items cleared from Kroger cart"},
            "kroger_items_total": {"type": "integer", "description": "Total number of items in cart before clearing"},
            "cart_id": {"type": "string", "description": "The Kroger cart ID"},
            "summary": {"type": "object", "description": "Summary of clearing operation"},
            "timestamp": {"type": "string", "description": "ISO timestamp of operation"},
            "error": {"type": "string", "description": "Error message"},
            "details": {"type": "string", "description": "Additional error details"}
        },
        "required": ["success"]
    })
    async def clear_cart(ctx: Context = None) -> Dict[str, Any]:
        """
        Clear all items from the actual Kroger cart using the Partner API.

        This function uses the Partner API to remove all items from your actual Kroger cart.
        This is the recommended way to clear your cart since it uses the official API.

        Requires authentication with cart.basic:write scope.

        Returns:
            Dictionary confirming the cart was cleared
        """
        try:
            if ctx:
                await ctx.info("🧹 Starting cart clearing process...")

            client = get_authenticated_client()

            if ctx:
                await ctx.info("✅ Client authenticated successfully")
                await ctx.info("📋 Fetching current cart from Kroger API...")

            # Get the current cart to see what items need to be removed
            carts_response = await _make_kroger_api_request(
                method="GET",
                endpoint="/v1/carts",
            )

            if ctx:
                await ctx.info("📋 Cart API response received successfully")

            if (
                not carts_response
                or "data" not in carts_response
                or not carts_response["data"]
            ):
                if ctx:
                    await ctx.info("✅ No Kroger cart found")

                return {
                    "success": True,
                    "message": "No cart found to clear",
                    "kroger_items_cleared": 0,
                    "kroger_items_total": 0,
                }

            # Get the first (active) cart
            kroger_cart = carts_response["data"][0]
            cart_id = kroger_cart["id"]

            # Count items in Kroger cart before clearing
            kroger_items_count = len(kroger_cart.get("items", []))
            kroger_items_cleared = 0

            if ctx:
                await ctx.info(
                    f"📋 Found Kroger cart with {kroger_items_count} item(s)"
                )

            # Remove each item from the Kroger cart using Partner API
            if "items" in kroger_cart and kroger_cart["items"]:
                if ctx:
                    await ctx.info(
                        f"🗑️ Clearing {kroger_items_count} items from Kroger cart..."
                    )

                for item in kroger_cart["items"]:
                    upc = item.get("upc")
                    if upc:
                        try:
                            # Use Partner API to remove item from Kroger cart
                            await _make_kroger_api_request(
                                method="DELETE",
                                endpoint=f"/v1/carts/{cart_id}/items/{upc}",
                            )

                            kroger_items_cleared += 1
                            if ctx:
                                await ctx.info(
                                    f"✅ Removed item {upc} from Kroger cart"
                                )

                        except Exception as item_error:
                            if ctx:
                                await ctx.warning(
                                    f"⚠️ Error removing item {upc}: {str(item_error)}"
                                )

            if ctx:
                await ctx.info(f"✅ Cart clearing complete!")
                await ctx.info(
                    f"📊 Summary: {kroger_items_cleared}/{kroger_items_count} items cleared from Kroger cart"
                )

            # Create detailed message
            if kroger_items_cleared == kroger_items_count:
                kroger_status = f"✅ Successfully cleared all {kroger_items_cleared} items from Kroger cart"
            else:
                kroger_status = f"⚠️ Cleared {kroger_items_cleared} of {kroger_items_count} items from Kroger cart"

            return {
                "success": True,
                "message": kroger_status,
                "kroger_items_cleared": kroger_items_cleared,
                "kroger_items_total": kroger_items_count,
                "cart_id": cart_id,
                "summary": {
                    "kroger_cart": f"{kroger_items_cleared}/{kroger_items_count} items cleared",
                },
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Failed to clear cart: {str(e)}")

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
                    "error": f"Failed to clear cart: {error_message}",
                }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "message": {"type": "string", "description": "Confirmation or error message"},
            "order_id": {"type": "integer", "description": "Simple order ID based on history length"},
            "items_placed": {"type": "integer", "description": "Number of items in the order"},
            "total_quantity": {"type": "integer", "description": "Total quantity of items"},
            "placed_at": {"type": "string", "description": "ISO timestamp when order was placed"},
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def mark_order_placed(
        order_notes: str = None, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        Mark the current cart as an order that has been placed and move it to order history.
        Use this after you've completed checkout on the Kroger website/app.

        Args:
            order_notes: Optional notes about the order

        Returns:
            Dictionary confirming the order was recorded
        """
        try:
            cart_data = _load_cart_data()
            current_cart = cart_data.get("current_cart", [])

            if not current_cart:
                return {
                    "success": False,
                    "error": "No items in current cart to mark as placed",
                }

            # Create order record
            order_record = {
                "items": current_cart.copy(),
                "placed_at": datetime.now().isoformat(),
                "item_count": len(current_cart),
                "total_quantity": sum(item.get("quantity", 0) for item in current_cart),
                "notes": order_notes,
            }

            # Load and update order history
            order_history = _load_order_history()
            order_history.append(order_record)
            _save_order_history(order_history)

            # Clear current cart
            cart_data["current_cart"] = []
            cart_data["last_updated"] = datetime.now().isoformat()
            _save_cart_data(cart_data)

            return {
                "success": True,
                "message": f"Marked order with {order_record['item_count']} items as placed",
                "order_id": len(
                    order_history
                ),  # Simple order ID based on history length
                "items_placed": order_record["item_count"],
                "total_quantity": order_record["total_quantity"],
                "placed_at": order_record["placed_at"],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to mark order as placed: {str(e)}",
            }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "message": {"type": "string", "description": "Confirmation or error message"},
            "cart_data": {"type": "object", "description": "The actual Kroger cart data"},
            "timestamp": {"type": "string", "description": "ISO timestamp of operation"},
            "version": {"type": "string", "description": "API version used"},
            "error": {"type": "string", "description": "Error message"},
            "details": {"type": "string", "description": "Additional error details"}
        },
        "required": ["success"]
    })
    async def fetch_actual_kroger_cart(ctx: Context = None) -> Dict[str, Any]:
        """
        Fetch the actual cart from the Kroger API using the Partner API.

        This function directly accesses the Kroger cart API to get the current cart state.
        This is the same as view_current_cart but returns the raw API response.

        Returns:
            Dictionary containing the actual Kroger cart data or an error message
        """
        try:
            if ctx:
                await ctx.info("Fetching actual Kroger cart via Partner API - UPDATED VERSION")

            client = get_authenticated_client()

            # Fetch the cart from Kroger API using Partner API
            cart_response = await _make_kroger_api_request(
                method="GET", 
                endpoint="/v1/carts"
            )

            if ctx:
                await ctx.info("Successfully fetched Kroger cart")

            return {
                "success": True,
                "message": "Successfully fetched Kroger cart - UPDATED VERSION",
                "cart_data": cart_response,
                "timestamp": datetime.now().isoformat(),
                "version": "UPDATED_PARTNER_API",
            }

        except Exception as e:
            if ctx:
                await ctx.error(f"Error fetching Kroger cart: {str(e)}")

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
                    "error": f"Error fetching Kroger cart: {error_message}"
                }

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the test was successful"},
            "message": {"type": "string", "description": "Test result message"},
            "cart_response": {"type": "object", "description": "Cart API response"},
            "has_carts": {"type": "boolean", "description": "Whether carts were found"},
            "error": {"type": "string", "description": "Error message"},
            "suggestion": {"type": "string", "description": "Suggestion for fixing the issue"}
        },
        "required": ["success"]
    })
    async def test_cart_api_access(ctx: Context = None) -> Dict[str, Any]:
        """
        Test if we can access the Kroger cart API.

        This is a diagnostic tool to help troubleshoot cart clearing issues.

        Returns:
            Dictionary with diagnostic information
        """
        try:
            from .shared import get_authenticated_client

            if ctx:
                await ctx.info("🔧 Testing cart API access...")

            client = get_authenticated_client()

            if ctx:
                await ctx.info("✅ Client authenticated successfully")

            # Test cart access
            try:
                carts_response = client.cart.get_carts()
                if ctx:
                    await ctx.info(
                        f"✅ Cart API accessible. Response type: {type(carts_response)}"
                    )
                    if carts_response and "data" in carts_response:
                        cart_count = len(carts_response["data"])
                        await ctx.info(f"📊 Found {cart_count} cart(s)")
                        if cart_count > 0:
                            first_cart = carts_response["data"][0]
                            item_count = len(first_cart.get("items", []))
                            await ctx.info(f"📦 First cart has {item_count} item(s)")

                return {
                    "success": True,
                    "message": "Cart API access test successful",
                    "cart_response": carts_response,
                    "has_carts": bool(
                        carts_response
                        and "data" in carts_response
                        and carts_response["data"]
                    ),
                }
            except Exception as cart_error:
                if ctx:
                    await ctx.error(f"❌ Cart API access failed: {str(cart_error)}")
                return {
                    "success": False,
                    "error": f"Cart API access failed: {str(cart_error)}",
                    "suggestion": "Check authentication and cart.basic:write scope",
                }

        except Exception as e:
            if ctx:
                await ctx.error(f"❌ Test failed: {str(e)}")
            return {"success": False, "error": f"Test failed: {str(e)}"}

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether the operation was successful"},
            "orders": {
                "type": "array",
                "description": "Array of order records",
                "items": {"type": "object"}
            },
            "showing": {"type": "integer", "description": "Number of orders shown"},
            "summary": {
                "type": "object",
                "properties": {
                    "total_orders": {"type": "integer"},
                    "total_items_all_time": {"type": "integer"},
                    "total_quantity_all_time": {"type": "integer"}
                }
            },
            "error": {"type": "string", "description": "Error details"}
        },
        "required": ["success"]
    })
    async def view_order_history(
        limit: int = 10, ctx: Context = None
    ) -> Dict[str, Any]:
        """
        View the history of placed orders.

        Note: This tool can only see orders that were explicitly marked as placed via this MCP server.
        The Kroger API does not provide permission to query the actual order history from Kroger's systems.

        Args:
            limit: Number of recent orders to show (1-50)

        Returns:
            Dictionary containing order history
        """
        try:
            # Ensure limit is within bounds
            limit = max(1, min(50, limit))

            order_history = _load_order_history()

            # Sort by placed_at date (most recent first) and limit
            sorted_orders = sorted(
                order_history, key=lambda x: x.get("placed_at", ""), reverse=True
            )
            limited_orders = sorted_orders[:limit]

            # Calculate summary stats
            total_orders = len(order_history)
            total_items_all_time = sum(
                order.get("item_count", 0) for order in order_history
            )
            total_quantity_all_time = sum(
                order.get("total_quantity", 0) for order in order_history
            )

            return {
                "success": True,
                "orders": limited_orders,
                "showing": len(limited_orders),
                "summary": {
                    "total_orders": total_orders,
                    "total_items_all_time": total_items_all_time,
                    "total_quantity_all_time": total_quantity_all_time,
                },
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to view order history: {str(e)}",
            }
