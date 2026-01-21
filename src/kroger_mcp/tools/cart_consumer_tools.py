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

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "Whether the item was successfully added"
            },
            "message": {
                "type": "string",
                "description": "Summary message"
            },
            "upc": {
                "type": "string",
                "description": "Product UPC that was added"
            },
            "quantity": {
                "type": "integer",
                "description": "Quantity added"
            },
            "modality": {
                "type": "string",
                "description": "Fulfillment method (PICKUP or DELIVERY)"
            },
            "timestamp": {
                "type": "string",
                "description": "ISO timestamp of operation"
            },
            "error": {
                "type": "string",
                "description": "Error message (when success=false)"
            },
            "details": {
                "type": "string",
                "description": "Additional error details (when success=false)"
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

    @mcp.tool(output_schema={
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "Whether the bulk add operation was successful"
            },
            "message": {
                "type": "string",
                "description": "Summary message of the operation"
            },
            "items_added": {
                "type": "integer",
                "description": "Number of items successfully added to cart"
            },
            "items": {
                "type": "array",
                "description": "List of items added to cart with UPC, quantity, and modality",
                "items": {
                    "type": "object",
                    "properties": {
                        "upc": {"type": "string", "description": "Product UPC code"},
                        "quantity": {"type": "integer", "description": "Quantity added"},
                        "modality": {"type": "string", "description": "PICKUP or DELIVERY"}
                    }
                }
            },
            "items_skipped": {
                "type": "integer",
                "description": "Number of items that were skipped (not found or missing UPC)"
            },
            "skipped_items": {
                "type": "array",
                "description": "List of item names/identifiers that were skipped",
                "items": {"type": "string"}
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
                "description": "Total number of items attempted (only present on error)"
            }
        },
        "required": ["success"]
    })
    async def bulk_add_to_cart(
        items: Union[List[Dict[str, Any]], Dict[str, Any], str], 
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
                   
                   Can also accept:
                   - A dict with {"items": [...]} (common LLM mistake - will be unwrapped)
                   - A JSON string containing the items list or {"items": [...]}

        Returns:
            Dictionary with results for the bulk add operation
        """
        try:
            # Handle case where items is passed as {"items": [...]} dict (common LLM mistake)
            if isinstance(items, dict):
                if ctx:
                    await ctx.info("Received items as dict, extracting items list...")
                if "items" in items:
                    items = items["items"]
                else:
                    return {
                        "success": False,
                        "error": "Invalid items format. Expected list or dict with 'items' key",
                        "received_keys": list(items.keys())
                    }
            
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
            skipped_items = []
            
            for item in items:
                # Handle case where item is a loop result with nested search data
                # Structure: {"index": 0, "element": "...", "success": true, "result": {"data": {"data": [products]}}}
                if "result" in item and isinstance(item.get("result"), dict):
                    result_data = item["result"].get("data", {})
                    if isinstance(result_data, dict) and "data" in result_data:
                        # Extract first product from search results
                        products = result_data["data"]
                        if products and len(products) > 0:
                            first_product = products[0]
                            upc = first_product.get("upc")
                            if upc:
                                formatted_items.append({
                                    "upc": upc,
                                    "quantity": item.get("quantity", 1),
                                    "modality": item.get("modality", "PICKUP")
                                })
                                if ctx:
                                    await ctx.info(f"Extracted UPC {upc} from search result for '{item.get('element', 'unknown')}'")
                            else:
                                skipped_items.append(item.get("element", "unknown"))
                                if ctx:
                                    await ctx.warning(f"Product found but missing UPC for '{item.get('element', 'unknown')}'")
                        else:
                            skipped_items.append(item.get("element", "unknown"))
                            if ctx:
                                await ctx.warning(f"No products found in search result for '{item.get('element', 'unknown')}'")
                    else:
                        # Standard item format
                        upc = item.get("upc") or item.get("product_id")
                        if upc:
                            formatted_items.append({
                                "upc": upc,
                                "quantity": item.get("quantity", 1),
                                "modality": item.get("modality", "PICKUP")
                            })
                        else:
                            skipped_items.append(str(item))
                else:
                    # Standard item format
                    upc = item.get("upc") or item.get("product_id")
                    if upc:
                        formatted_items.append({
                            "upc": upc,
                            "quantity": item.get("quantity", 1),
                            "modality": item.get("modality", "PICKUP")
                        })
                    else:
                        skipped_items.append(str(item))

            request_body = {"items": formatted_items}
            
            # Check if we have any valid items to add
            if not formatted_items:
                if ctx:
                    await ctx.error(f"No valid items to add. All {len(items)} items were skipped.")
                return {
                    "success": False,
                    "error": f"No valid items to add to cart. All items missing UPCs or not found.",
                    "items_attempted": len(items),
                    "items_skipped": len(skipped_items),
                    "skipped_items": skipped_items
                }
            
            # Validate that all items have UPCs (should be caught above, but double-check)
            invalid_items = [item for item in formatted_items if not item.get("upc")]
            if invalid_items:
                if ctx:
                    await ctx.error(f"Found {len(invalid_items)} items without UPCs")
                return {
                    "success": False,
                    "error": f"Cannot add items without UPCs. {len(invalid_items)} of {len(formatted_items)} items missing UPC.",
                    "items_attempted": len(items),
                    "invalid_items_count": len(invalid_items)
                }

            if ctx:
                if skipped_items:
                    await ctx.warning(f"Skipped {len(skipped_items)} items: {', '.join(skipped_items)}")
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
                await ctx.info(f"Successfully added {len(formatted_items)} items to cart")

            result = {
                "success": True,
                "message": f"Successfully added {len(formatted_items)} items to cart",
                "items_added": len(formatted_items),
                "items": formatted_items,
                "timestamp": datetime.now().isoformat(),
            }
            
            if skipped_items:
                result["items_skipped"] = len(skipped_items)
                result["skipped_items"] = skipped_items
                result["message"] += f" ({len(skipped_items)} items skipped)"
            
            return result

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
