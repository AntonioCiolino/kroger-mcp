#!/usr/bin/env python3
"""
Web UI for Kroger MCP Server

A simple Flask web interface to interact with the Kroger MCP server tools.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
from datetime import datetime
import asyncio
import sys
from urllib.parse import parse_qs
from kroger_api import KrogerAPI
from kroger_api.utils import generate_pkce_parameters
from price_tracker import price_tracker

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from kroger_mcp.tools.shared import (
    get_client_credentials_client,
    get_authenticated_client,
)
from kroger_mcp.tools import (
    location_tools,
    product_tools,
    cart_tools,
    info_tools,
    profile_tools,
    auth_tools,
)

app = Flask(__name__)
app.secret_key = "your-secret-key-change-this"

# Global variables for PKCE authentication flow
_pkce_params = None
_auth_state = None

# Store for UI state
ui_state = {
    "preferred_location": None,
    "last_search_results": [],
    "cart_items": [],
    "auth_status": False,
}


@app.route("/")
def index():
    """Main dashboard"""
    return render_template("index.html", state=ui_state)


@app.route("/api/locations/search", methods=["POST"])
def search_locations():
    """Search for store locations"""
    data = request.get_json()
    zip_code = data.get("zip_code", "90274")

    try:
        # Call the Kroger API directly using the correct method
        client = get_client_credentials_client()
        locations = client.location.search_locations(zip_code=zip_code, limit=20)

        # Format the response similar to the MCP tool
        if locations and "data" in locations:
            formatted_locations = []
            for loc in locations["data"]:
                address = loc.get("address", {})
                formatted_locations.append(
                    {
                        "locationId": loc.get("locationId"),
                        "name": loc.get("name"),
                        "address": f"{address.get('addressLine1', '')}, {address.get('city', '')}, {address.get('state', '')} {address.get('zipCode', '')}",
                        "phone": loc.get("phone"),
                        "chain": loc.get("chain"),
                        "hours": (
                            "Hours available"
                            if loc.get("hours")
                            else "Hours not available"
                        ),
                    }
                )

            result = {
                "success": True,
                "locations": formatted_locations,
                "count": len(formatted_locations),
            }
        else:
            result = {"success": False, "message": "No locations found"}

        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/locations/set-preferred", methods=["POST"])
def set_preferred_location():
    """Set preferred store location"""
    data = request.get_json()
    location_id = data.get("location_id")

    try:
        from kroger_mcp.tools.shared import (
            set_preferred_location_id,
            get_client_credentials_client,
        )

        set_preferred_location_id(location_id)
        ui_state["preferred_location"] = location_id

        # Try to get location name for display
        location_name = None
        try:
            client = get_client_credentials_client()
            location_details = client.location.get_location(location_id)
            if location_details and "data" in location_details:
                location_name = location_details["data"].get("name")
        except:
            pass

        result = {
            "success": True,
            "message": f"Preferred location set to {location_id}",
            "location_id": location_id,
            "location_name": location_name,
        }
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/locations/get-preferred", methods=["GET"])
def get_preferred_location():
    """Get current preferred location"""
    try:
        from kroger_mcp.tools.shared import (
            get_preferred_location_id,
            get_client_credentials_client,
        )

        location_id = get_preferred_location_id()

        if not location_id:
            return jsonify({"success": False, "message": "No preferred location set"})

        # Try to get location name for display
        location_name = None
        try:
            client = get_client_credentials_client()
            location_details = client.location.get_location(location_id)
            if location_details and "data" in location_details:
                location_name = location_details["data"].get("name")
        except:
            pass

        result = {
            "success": True,
            "location_id": location_id,
            "location_name": location_name or f"Location {location_id}",
        }
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/preferences/display-name", methods=["POST"])
def set_display_name():
    """Set user's preferred display name"""
    try:
        data = request.get_json()
        display_name = data.get('display_name', '').strip()
        
        if not display_name:
            return jsonify({"success": False, "error": "Display name cannot be empty"})
        
        if len(display_name) > 50:
            return jsonify({"success": False, "error": "Display name must be 50 characters or less"})
        
        # Load existing preferences
        try:
            with open('kroger_preferences.json', 'r') as f:
                prefs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            prefs = {}
        
        # Update display name
        prefs['display_name'] = display_name
        
        # Save preferences
        with open('kroger_preferences.json', 'w') as f:
            json.dump(prefs, f, indent=2)
        
        return jsonify({
            "success": True, 
            "message": f"Display name set to '{display_name}'",
            "display_name": display_name
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/preferences/display-name", methods=["GET"])
def get_display_name():
    """Get user's current display name"""
    try:
        try:
            with open('kroger_preferences.json', 'r') as f:
                prefs = json.load(f)
                display_name = prefs.get('display_name')
        except (FileNotFoundError, json.JSONDecodeError):
            display_name = None
        
        return jsonify({
            "success": True,
            "display_name": display_name,
            "has_custom_name": display_name is not None
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/debug/profile", methods=["GET"])
def debug_profile():
    """Debug endpoint to see what profile data is available"""
    try:
        client = get_authenticated_client()
        
        # Get token info
        token_info = client.client.token_info if hasattr(client, 'client') and hasattr(client.client, 'token_info') else None
        scopes = []
        
        # Try to get scopes from JWT token first (more reliable)
        if token_info:
            try:
                access_token = token_info.get("access_token", "")
                if access_token:
                    # Decode JWT payload
                    import base64
                    parts = access_token.split('.')
                    if len(parts) >= 2:
                        payload = parts[1]
                        payload += '=' * (4 - len(payload) % 4)  # Add padding
                        decoded = base64.b64decode(payload)
                        jwt_data = json.loads(decoded)
                        scopes = jwt_data.get("scope", "").split(" ")
                    else:
                        scopes = token_info.get('scope', '').split(' ')
                else:
                    scopes = token_info.get('scope', '').split(' ')
            except Exception as e:
                print(f"Error decoding JWT for debug: {e}")
                scopes = token_info.get('scope', '').split(' ') if token_info else []
        
        result = {
            "success": True,
            "has_token": token_info is not None,
            "scopes": scopes,
            "has_profile_scope": "profile.name" in scopes,
            "profile_data": None,
            "error": None
        }
        
        if "profile.name" in scopes:
            try:
                profile = client.identity.get_profile()
                result["profile_data"] = profile
                result["profile_keys"] = list(profile.get("data", {}).keys()) if profile and "data" in profile else []
            except Exception as profile_error:
                result["error"] = str(profile_error)
                result["profile_data"] = None
        else:
            result["error"] = "profile.name scope not available - need to re-authenticate"
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "authenticated": False
        })


@app.route("/api/products/details", methods=["GET"])
def get_product_details():
    """Get detailed information about a specific product"""
    product_id = request.args.get("product_id")

    if not product_id:
        return jsonify({"success": False, "error": "Product ID is required"})

    try:
        # Call the Kroger API directly using the correct method
        client = get_client_credentials_client()

        # Get preferred location for product details
        from kroger_mcp.tools.shared import get_preferred_location_id

        location_id = get_preferred_location_id()

        if not location_id:
            return jsonify(
                {
                    "success": False,
                    "error": "No preferred location set. Please search for locations and set a preferred store first.",
                }
            )

        product_details = client.product.get_product(
            product_id=product_id, location_id=location_id
        )

        # Format the response with full product details
        if product_details and "data" in product_details:
            product = product_details["data"]

            formatted_product = {
                "product_id": product.get("productId"),
                "upc": product.get("upc"),
                "description": product.get("description"),
                "brand": product.get("brand"),
                "categories": product.get("categories", []),
                "country_origin": product.get("countryOrigin"),
                "temperature": product.get("temperature", {}),
            }

            # Add item information (size, price, etc.)
            if "items" in product and product["items"]:
                item = product["items"][0]
                formatted_product["item_details"] = {
                    "size": item.get("size"),
                    "sold_by": item.get("soldBy"),
                    "inventory": item.get("inventory", {}),
                    "fulfillment": item.get("fulfillment", {}),
                }

                # Add pricing information
                if "price" in item:
                    price = item["price"]
                    formatted_product["pricing"] = {
                        "regular_price": price.get("regular"),
                        "sale_price": price.get("promo"),
                        "regular_per_unit": price.get("regularPerUnitEstimate"),
                        "on_sale": price.get("promo") is not None
                        and price.get("promo") < price.get("regular", float("inf")),
                    }

            # Add aisle information
            if "aisleLocations" in product:
                formatted_product["aisle_locations"] = [
                    {
                        "description": aisle.get("description"),
                        "number": aisle.get("number"),
                        "side": aisle.get("side"),
                        "shelf_number": aisle.get("shelfNumber"),
                    }
                    for aisle in product["aisleLocations"]
                ]

            # Add image information
            if "images" in product and product["images"]:
                formatted_product["images"] = [
                    {
                        "perspective": img.get("perspective"),
                        "url": img["sizes"][0].get("url") if img.get("sizes") else None,
                        "size": (
                            img["sizes"][0].get("size") if img.get("sizes") else None
                        ),
                    }
                    for img in product["images"]
                    if img.get("sizes")
                ]

            return jsonify({"success": True, "data": formatted_product})
        else:
            return jsonify({"success": False, "error": "Product not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/products/search", methods=["POST"])
def search_products():
    """Search for products"""
    data = request.get_json()
    term = data.get("term", "")
    limit = data.get("limit", 10)

    try:
        # Call the Kroger API directly using the correct method
        client = get_client_credentials_client()

        # Get preferred location for product search
        from kroger_mcp.tools.shared import get_preferred_location_id

        location_id = get_preferred_location_id()

        if not location_id:
            return jsonify(
                {
                    "success": False,
                    "error": "No preferred location set. Please search for locations and set a preferred store first.",
                }
            )

        products = client.product.search_products(
            term=term, location_id=location_id, limit=limit
        )

        # Format the response with full product details like the MCP tool
        if products and "data" in products:
            formatted_products = []
            for product in products["data"]:
                formatted_product = {
                    "productId": product.get("productId"),
                    "upc": product.get("upc"),
                    "description": product.get("description"),
                    "brand": product.get("brand"),
                    "categories": product.get("categories", []),
                    "country_origin": product.get("countryOrigin"),
                    "temperature": product.get("temperature", {}),
                }

                # Add item information (size, price, etc.)
                if "items" in product and product["items"]:
                    item = product["items"][0]
                    formatted_product["item"] = {
                        "size": item.get("size"),
                        "sold_by": item.get("soldBy"),
                        "inventory": item.get("inventory", {}),
                        "fulfillment": item.get("fulfillment", {}),
                    }

                    # Add pricing information
                    if "price" in item:
                        price = item["price"]
                        regular_price = price.get("regular")
                        sale_price = price.get("promo")
                        
                        formatted_product["pricing"] = {
                            "regular_price": regular_price,
                            "sale_price": sale_price,
                            "regular_per_unit": price.get("regularPerUnitEstimate"),
                            "on_sale": sale_price is not None and sale_price < regular_price,
                        }
                        
                        # Track price for this product
                        if regular_price:
                            try:
                                price_change_info = price_tracker.track_price(
                                    product_id=product.get("productId"),
                                    regular_price=regular_price,
                                    sale_price=sale_price,
                                    location_id=location_id,
                                    product_name=product.get("description")
                                )
                                formatted_product["price_tracking"] = price_change_info
                            except Exception as e:
                                print(f"Warning: Price tracking failed for {product.get('productId')}: {e}")

                # Add aisle information
                if "aisleLocations" in product:
                    formatted_product["aisle_locations"] = [
                        {
                            "description": aisle.get("description"),
                            "number": aisle.get("number"),
                            "side": aisle.get("side"),
                            "shelf_number": aisle.get("shelfNumber"),
                        }
                        for aisle in product["aisleLocations"]
                    ]

                # Add image information
                if "images" in product and product["images"]:
                    formatted_product["images"] = [
                        {
                            "perspective": img.get("perspective"),
                            "url": (
                                img["sizes"][0].get("url") if img.get("sizes") else None
                            ),
                            "size": (
                                img["sizes"][0].get("size")
                                if img.get("sizes")
                                else None
                            ),
                        }
                        for img in product["images"]
                        if img.get("sizes")
                    ]

                formatted_products.append(formatted_product)

            result = {
                "success": True,
                "products": formatted_products,
                "count": len(formatted_products),
                "search_term": term,
            }
            ui_state["last_search_results"] = formatted_products
        else:
            result = {"success": False, "message": "No products found"}

        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/add", methods=["POST"])
def add_to_cart():
    """Add item to cart"""
    data = request.get_json()
    product_id = data.get("product_id")
    quantity = data.get("quantity", 1)

    try:
        # Try to get authenticated client for cart operations
        client = get_authenticated_client()

        # Get preferred location for cart operations
        from kroger_mcp.tools.shared import get_preferred_location_id

        location_id = get_preferred_location_id()

        if not location_id:
            return jsonify(
                {
                    "success": False,
                    "error": "No preferred location set. Please set a preferred location first.",
                }
            )

        # Get modality from request, default to PICKUP
        modality = data.get("modality", "PICKUP")

        # Add item to cart via Kroger API (correct method)
        cart_item = {"upc": product_id, "quantity": quantity, "modality": modality}

        # The add_to_cart method takes a list of items and returns None on success
        client.cart.add_to_cart([cart_item])
        cart_result = {"success": True, "message": "Item added to Kroger cart"}

        # Also update local cart tracking
        cart_file = "kroger_cart.json"
        if os.path.exists(cart_file):
            try:
                with open(cart_file, "r") as f:
                    cart_data = json.load(f)
                    # Handle both formats: the MCP format (with "current_cart") and the legacy format (flat array)
                    if isinstance(cart_data, dict) and "current_cart" in cart_data:
                        cart_items = cart_data.get("current_cart", [])
                    else:
                        cart_items = cart_data if isinstance(cart_data, list) else []
            except json.JSONDecodeError:
                cart_data = {
                    "current_cart": [],
                    "last_updated": None,
                    "preferred_location_id": None,
                }
                cart_items = []
        else:
            cart_data = {
                "current_cart": [],
                "last_updated": None,
                "preferred_location_id": None,
            }
            cart_items = []
        
        # Add to local tracking
        new_item = {
            "product_id": product_id,
            "quantity": quantity,
            "modality": modality,
            "added_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "location_id": location_id,
        }

        # Check if item already exists in cart with the same product_id AND modality
        existing_item = None
        for item in cart_items:
            if item.get("product_id") == product_id and item.get("modality") == modality:
                existing_item = item
                break

        if existing_item:
            # Update existing item quantity (same product, same modality)
            existing_item["quantity"] = existing_item.get("quantity", 0) + quantity
            existing_item["last_updated"] = datetime.now().isoformat()
        else:
            # Add new item (either new product or same product with different modality)
            cart_items.append(new_item)

        # Save in MCP format
        cart_data["current_cart"] = cart_items
        cart_data["last_updated"] = datetime.now().isoformat()
        cart_data["preferred_location_id"] = location_id

        with open(cart_file, "w") as f:
            json.dump(cart_data, f, indent=2)

        result = {
            "success": True,
            "message": f"Added {quantity} item(s) to cart",
            "product_id": product_id,
            "quantity": quantity,
            "kroger_response": cart_result,
        }
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/update-quantity", methods=["POST"])
def update_cart_quantity():
    """Update quantity of an item in the cart"""
    try:
        data = request.get_json()
        product_id = data.get("product_id")
        new_quantity = data.get("quantity", 1)

        # Read current cart
        cart_file = "kroger_cart.json"
        if os.path.exists(cart_file):
            with open(cart_file, "r") as f:
                cart_data = json.load(f)
                # Handle both formats: the MCP format (with "current_cart") and the legacy format (flat array)
                if isinstance(cart_data, dict) and "current_cart" in cart_data:
                    cart_items = cart_data.get("current_cart", [])
                else:
                    cart_items = cart_data if isinstance(cart_data, list) else []
        else:
            cart_items = []

        # Update the item quantity
        updated = False
        for item in cart_items:
            # Match by product_id only, ignore modality
            if item.get("product_id") == product_id:
                item["quantity"] = new_quantity
                item["last_updated"] = datetime.now().isoformat()
                updated = True
                break

        if updated:
            # Also update the Kroger cart
            try:
                client = get_authenticated_client()
                from kroger_mcp.tools.shared import get_preferred_location_id
                
                # Get the access token
                token_info = client.client.token_info
                access_token = token_info.get("access_token")
                
                if access_token:
                    import requests
                    
                    # First, get the current carts to find the cart ID
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json"
                    }
                    
                    carts_response = requests.get("https://api.kroger.com/v1/carts", headers=headers)
                    
                    if carts_response.status_code == 200:
                        carts_data = carts_response.json()
                        if "data" in carts_data and carts_data["data"]:
                            cart_id = carts_data["data"][0]["id"]  # Use first cart
                            
                            # Update the item quantity in Kroger cart
                            update_url = f"https://api.kroger.com/v1/carts/{cart_id}/items/{product_id}"
                            update_data = {"quantity": new_quantity}
                            
                            update_response = requests.put(
                                update_url, 
                                headers={**headers, "Content-Type": "application/json"},
                                json=update_data
                            )
                            
                            if update_response.status_code not in [200, 204]:
                                print(f"Warning: Failed to update Kroger cart: {update_response.status_code}")
                        
            except Exception as e:
                print(f"Warning: Could not sync to Kroger cart: {e}")
                # Continue anyway - local update succeeded
            
            # Save updated cart in MCP format
            if isinstance(cart_data, dict) and "current_cart" in cart_data:
                cart_data["current_cart"] = cart_items
                cart_data["last_updated"] = datetime.now().isoformat()
                with open(cart_file, "w") as f:
                    json.dump(cart_data, f, indent=2)
            else:
                # Legacy format or new cart
                with open(cart_file, "w") as f:
                    json.dump(
                        {
                            "current_cart": cart_items,
                            "last_updated": datetime.now().isoformat(),
                            "preferred_location_id": None,
                        },
                        f,
                        indent=2,
                    )

            return jsonify(
                {"success": True, "message": f"Updated quantity to {new_quantity}"}
            )
        else:
            return jsonify({"success": False, "error": "Item not found in cart"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/update-modality", methods=["POST"])
def update_cart_modality():
    """Update modality of an item in the cart"""
    try:
        data = request.get_json()
        product_id = data.get("product_id")
        new_modality = data.get("modality", "PICKUP")

        # Read current cart
        cart_file = "kroger_cart.json"
        if os.path.exists(cart_file):
            with open(cart_file, "r") as f:
                cart_data = json.load(f)
                # Handle both formats: the MCP format (with "current_cart") and the legacy format (flat array)
                if isinstance(cart_data, dict) and "current_cart" in cart_data:
                    cart_items = cart_data.get("current_cart", [])
                else:
                    cart_items = cart_data if isinstance(cart_data, list) else []
        else:
            cart_items = []

        # Update the item modality
        updated = False
        for item in cart_items:
            if item.get("product_id") == product_id:
                item["modality"] = new_modality
                item["last_updated"] = datetime.now().isoformat()
                updated = True
                break

        if updated:
            # Also update the Kroger cart modality
            try:
                client = get_authenticated_client()
                from kroger_mcp.tools.shared import get_preferred_location_id
                
                # Get the access token
                token_info = client.client.token_info
                access_token = token_info.get("access_token")
                
                if access_token:
                    import requests
                    
                    # Get current carts to find the cart ID and item details
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json"
                    }
                    
                    carts_response = requests.get("https://api.kroger.com/v1/carts", headers=headers)
                    
                    if carts_response.status_code == 200:
                        carts_data = carts_response.json()
                        if "data" in carts_data and carts_data["data"]:
                            cart_id = carts_data["data"][0]["id"]  # Use first cart
                            kroger_cart = carts_data["data"][0]
                            
                            # Find the item in the Kroger cart to get its current quantity
                            item_quantity = 1
                            if "items" in kroger_cart:
                                for item in kroger_cart["items"]:
                                    if item.get("upc") == product_id:
                                        item_quantity = item.get("quantity", 1)
                                        break
                            
                            # Update the item with new modality (need to include quantity)
                            update_url = f"https://api.kroger.com/v1/carts/{cart_id}/items/{product_id}"
                            update_data = {
                                "quantity": item_quantity,
                                "modality": new_modality
                            }
                            
                            update_response = requests.put(
                                update_url, 
                                headers={**headers, "Content-Type": "application/json"},
                                json=update_data
                            )
                            
                            if update_response.status_code not in [200, 204]:
                                print(f"Warning: Failed to update Kroger cart modality: {update_response.status_code}")
                        
            except Exception as e:
                print(f"Warning: Could not sync modality to Kroger cart: {e}")
                # Continue anyway - local update succeeded
            
            # Save updated cart in MCP format
            if isinstance(cart_data, dict) and "current_cart" in cart_data:
                cart_data["current_cart"] = cart_items
                cart_data["last_updated"] = datetime.now().isoformat()
                with open(cart_file, "w") as f:
                    json.dump(cart_data, f, indent=2)
            else:
                # Legacy format or new cart
                with open(cart_file, "w") as f:
                    json.dump(
                        {
                            "current_cart": cart_items,
                            "last_updated": datetime.now().isoformat(),
                            "preferred_location_id": None,
                        },
                        f,
                        indent=2,
                    )

            return jsonify(
                {"success": True, "message": f"Updated modality to {new_modality}"}
            )
        else:
            return jsonify({"success": False, "error": "Item not found in cart"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/remove", methods=["POST"])
def remove_from_cart():
    """Remove an item from the cart - using Kroger API as source of truth"""
    try:
        data = request.get_json()
        product_id = data.get("product_id")

        # Remove from Kroger cart first
        try:
            client = get_authenticated_client()
            from kroger_mcp.tools.shared import get_preferred_location_id
            
            # Get the access token
            token_info = client.client.token_info
            access_token = token_info.get("access_token")
            
            if access_token:
                import requests
                
                # Get current carts to find the cart ID
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }
                
                carts_response = requests.get("https://api.kroger.com/v1/carts", headers=headers)
                
                if carts_response.status_code == 200:
                    carts_data = carts_response.json()
                    if "data" in carts_data and carts_data["data"]:
                        cart_id = carts_data["data"][0]["id"]  # Use first cart
                        
                        # Remove the item from Kroger cart
                        remove_url = f"https://api.kroger.com/v1/carts/{cart_id}/items/{product_id}"
                        
                        remove_response = requests.delete(remove_url, headers=headers)
                        
                        if remove_response.status_code in [200, 204, 404]:  # 404 is OK - item already gone
                            # Now sync the updated cart back to local storage
                            # Fetch the updated cart from Kroger
                            updated_carts_response = requests.get("https://api.kroger.com/v1/carts", headers=headers)
                            
                            if updated_carts_response.status_code == 200:
                                updated_carts_data = updated_carts_response.json()
                                
                                # Convert to local format and save
                                local_cart_items = []
                                if "data" in updated_carts_data and updated_carts_data["data"]:
                                    kroger_cart = updated_carts_data["data"][0]
                                    if "items" in kroger_cart:
                                        for item in kroger_cart["items"]:
                                            local_item = {
                                                "product_id": item.get("upc"),
                                                "quantity": item.get("quantity", 1),
                                                "modality": item.get("modality", "PICKUP"),
                                                "added_at": datetime.now().isoformat(),
                                                "last_updated": datetime.now().isoformat(),
                                                "location_id": get_preferred_location_id(),
                                            }
                                            local_cart_items.append(local_item)
                                
                                # Save updated cart to local file
                                cart_file = "kroger_cart.json"
                                cart_data = {
                                    "current_cart": local_cart_items,
                                    "last_updated": datetime.now().isoformat(),
                                    "preferred_location_id": get_preferred_location_id(),
                                }
                                with open(cart_file, "w") as f:
                                    json.dump(cart_data, f, indent=2)
                            
                            return jsonify({"success": True, "message": "Item removed from cart"})
                        else:
                            raise Exception(f"Failed to remove from Kroger cart: {remove_response.status_code}")
                else:
                    raise Exception(f"Failed to get carts: {carts_response.status_code}")
            else:
                raise Exception("No access token available")
                
        except Exception as api_error:
            return jsonify({
                "success": False, 
                "error": f"Failed to remove from Kroger cart: {str(api_error)}"
            })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/view", methods=["GET"])
def view_cart():
    """View current cart with enhanced product details - always fetch from Kroger API"""
    try:
        # Always fetch fresh data from Kroger API
        all_cart_items = []
        
        try:
            client = get_authenticated_client()
            from kroger_mcp.tools.shared import get_preferred_location_id
            
            # Get the access token
            token_info = client.client.token_info
            access_token = token_info.get("access_token")
            
            if access_token:
                import requests
                
                # Fetch current cart from Kroger API
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }
                
                carts_response = requests.get("https://api.kroger.com/v1/carts", headers=headers)
                
                if carts_response.status_code == 200:
                    carts_data = carts_response.json()
                    if "data" in carts_data and carts_data["data"]:
                        kroger_cart = carts_data["data"][0]  # Use first cart
                        
                        # Convert Kroger cart items to our format
                        if "items" in kroger_cart:
                            for item in kroger_cart["items"]:
                                cart_item = {
                                    "product_id": item.get("upc"),
                                    "quantity": item.get("quantity", 1),
                                    "modality": item.get("modality", "PICKUP"),
                                    "added_at": datetime.now().isoformat(),
                                    "last_updated": datetime.now().isoformat(),
                                    "location_id": get_preferred_location_id(),
                                }
                                all_cart_items.append(cart_item)
                        
                        # Also update local cache for consistency
                        cart_file = "kroger_cart.json"
                        cart_data = {
                            "current_cart": all_cart_items,
                            "last_updated": datetime.now().isoformat(),
                            "preferred_location_id": get_preferred_location_id(),
                        }
                        with open(cart_file, "w") as f:
                            json.dump(cart_data, f, indent=2)
                            
        except Exception as api_error:
            print(f"Warning: Could not fetch from Kroger API: {api_error}")
            # Fall back to local cache if API fails
            cart_file = "kroger_cart.json"
            if os.path.exists(cart_file):
                try:
                    with open(cart_file, "r") as f:
                        cart_data = json.load(f)
                        if isinstance(cart_data, dict) and "current_cart" in cart_data:
                            all_cart_items = cart_data.get("current_cart", [])
                        else:
                            all_cart_items = cart_data if isinstance(cart_data, list) else []
                except json.JSONDecodeError:
                    all_cart_items = []

        # Use all cart items without filtering by modality
        cart_items = all_cart_items

        # Enhance cart items with product details and images
        enhanced_cart_items = []
        client = get_client_credentials_client()

        from kroger_mcp.tools.shared import get_preferred_location_id

        location_id = get_preferred_location_id()

        for item in cart_items:
            enhanced_item = item.copy()
            product_id = item.get("product_id")

            if product_id and location_id:
                try:
                    # Get product details from Kroger API
                    product_details = client.product.get_product(
                        product_id=product_id, location_id=location_id
                    )

                    if product_details and "data" in product_details:
                        product = product_details["data"]

                        # Add product information
                        enhanced_item.update(
                            {
                                "description": product.get("description"),
                                "brand": product.get("brand"),
                                "upc": product.get("upc"),
                            }
                        )

                        # Add pricing information
                        if "items" in product and product["items"]:
                            item_data = product["items"][0]
                            if "price" in item_data:
                                price = item_data["price"]
                                regular_price = price.get("regular")
                                sale_price = price.get("promo")
                                
                                enhanced_item["pricing"] = {
                                    "regular_price": regular_price,
                                    "sale_price": sale_price,
                                    "on_sale": sale_price is not None
                                    and sale_price < regular_price,
                                }
                                
                                # Track price for this product
                                if regular_price:
                                    try:
                                        price_info = price_tracker.track_price(
                                            product_id=product_id,
                                            regular_price=regular_price,
                                            sale_price=sale_price,
                                            location_id=location_id,
                                            product_name=product.get("description")
                                        )
                                        enhanced_item["price_tracking"] = price_info
                                    except Exception as e:
                                        print(f"Price tracking error: {e}")

                            # Add size information
                            enhanced_item["size"] = item_data.get("size")

                        # Add image information
                        if "images" in product and product["images"]:
                            images = []
                            for img in product["images"]:
                                if img.get("sizes"):
                                    # Get the best available image size
                                    best_size = None
                                    for size in [
                                        "large",
                                        "medium",
                                        "small",
                                        "thumbnail",
                                    ]:
                                        for img_size in img["sizes"]:
                                            if img_size.get("size") == size:
                                                best_size = img_size
                                                break
                                        if best_size:
                                            break

                                    if best_size:
                                        images.append(
                                            {
                                                "perspective": img.get(
                                                    "perspective", "front"
                                                ),
                                                "url": best_size.get("url"),
                                                "size": best_size.get("size"),
                                            }
                                        )

                            enhanced_item["images"] = images

                except Exception as e:
                    # If we can't get product details, just note the error
                    enhanced_item["product_details_error"] = str(e)

            enhanced_cart_items.append(enhanced_item)

        result = {
            "success": True,
            "cart_items": enhanced_cart_items,
            "count": len(enhanced_cart_items),
            "message": "Enhanced cart view with product details and images",
        }
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/sync", methods=["POST"])
def sync_cart():
    """Fetch cart from Kroger API and sync with local cart"""
    try:
        data = request.get_json() or {}
        
        # Check if we should clear the cart
        if data.get("clear", False):
            cart_file = "kroger_cart.json"
            if os.path.exists(cart_file):
                with open(cart_file, "r") as f:
                    cart_data = json.load(f)

                # Clear the cart items but keep the structure
                if isinstance(cart_data, dict) and "current_cart" in cart_data:
                    cart_data["current_cart"] = []
                    cart_data["last_updated"] = datetime.now().isoformat()
                else:
                    cart_data = {
                        "current_cart": [],
                        "last_updated": datetime.now().isoformat(),
                        "preferred_location_id": None,
                    }

                with open(cart_file, "w") as f:
                    json.dump(cart_data, f, indent=2)

            return jsonify({"success": True, "message": "Cart cleared successfully"})

        # Check if we should fetch from Kroger API
        if data.get("fetch", False):
            try:
                # Get authenticated client for user cart access
                client = get_authenticated_client()
                
                # Import the function we need
                from kroger_mcp.tools.shared import get_preferred_location_id
                
                # Make direct API call to get user carts
                import requests
                
                # Get the access token from the client
                token_info = client.client.token_info
                access_token = token_info.get("access_token")
                
                if not access_token:
                    raise Exception("No access token available")
                
                # Make direct API call to Kroger
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                }
                
                response = requests.get("https://api.kroger.com/v1/carts", headers=headers)
                
                if response.status_code == 200:
                    carts_response = response.json()
                    carts_result = {"success": True, "data": carts_response}
                else:
                    raise Exception(f"API call failed with status {response.status_code}: {response.text}")
                
                if carts_result.get("success") and carts_result.get("data"):
                    carts_data = carts_result["data"]
                    
                    if "data" in carts_data and carts_data["data"]:
                        # Use the first cart (most recent)
                        kroger_cart = carts_data["data"][0]
                        
                        # Convert Kroger cart items to our local format
                        local_cart_items = []
                        if "items" in kroger_cart:
                            for item in kroger_cart["items"]:
                                local_item = {
                                    "product_id": item.get("upc"),
                                    "quantity": item.get("quantity", 1),
                                    "modality": item.get("modality", "PICKUP"),
                                    "added_at": datetime.now().isoformat(),
                                    "last_updated": datetime.now().isoformat(),
                                    "location_id": get_preferred_location_id(),
                                }
                                local_cart_items.append(local_item)
                        
                        # Save to local cart file
                        cart_file = "kroger_cart.json"
                        cart_data = {
                            "current_cart": local_cart_items,
                            "last_updated": datetime.now().isoformat(),
                            "preferred_location_id": get_preferred_location_id(),
                        }
                        with open(cart_file, "w") as f:
                            json.dump(cart_data, f, indent=2)
                        
                        return jsonify({
                            "success": True,
                            "message": f"Successfully fetched and synced {len(local_cart_items)} items from Kroger cart",
                            "items_count": len(local_cart_items)
                        })
                    else:
                        # No carts found, create empty local cart
                        cart_file = "kroger_cart.json"
                        cart_data = {
                            "current_cart": [],
                            "last_updated": datetime.now().isoformat(),
                            "preferred_location_id": get_preferred_location_id(),
                        }
                        with open(cart_file, "w") as f:
                            json.dump(cart_data, f, indent=2)
                        
                        return jsonify({
                            "success": True,
                            "message": "No items found in Kroger cart. Local cart cleared.",
                            "items_count": 0
                        })
                else:
                    raise Exception(f"Failed to get carts: {carts_result.get('error', 'Unknown error')}")
                    
            except Exception as api_error:
                # If Kroger API fails, return error
                return jsonify({
                    "success": False,
                    "error": f"Failed to fetch from Kroger API: {str(api_error)}",
                    "note": "Make sure you're authenticated with cart.basic:rw scope"
                })
        
        # Default behavior - create empty cart
        cart_file = "kroger_cart.json"
        cart_data = {
            "current_cart": [],
            "last_updated": datetime.now().isoformat(),
            "preferred_location_id": get_preferred_location_id()
        }
        
        with open(cart_file, "w") as f:
            json.dump(cart_data, f, indent=2)
        
        return jsonify({
            "success": True,
            "message": "Cart initialized (local storage).",
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/clear", methods=["POST"])
def clear_cart():
    """Clear all items from the cart - using MCP clear_cart tool with Partner API access"""
    try:
        # Use the MCP clear_cart tool which handles both Kroger API and local tracking
        import asyncio
        
        # Import the MCP clear_cart function
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        from kroger_mcp.tools.cart_tools import clear_cart as mcp_clear_cart
        
        # Run the async MCP function
        result = asyncio.run(mcp_clear_cart())
        
        if result.get("success"):
            return jsonify({
                "success": True, 
                "message": result.get("message", "Cart cleared successfully"),
                "items_cleared": result.get("items_cleared", 0)
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Failed to clear cart")
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/update-all-modality", methods=["POST"])
def update_all_cart_modality():
    """Update modality for all items in the cart"""
    try:
        data = request.get_json()
        new_modality = data.get("modality", "PICKUP")

        # Read current cart
        cart_file = "kroger_cart.json"
        if os.path.exists(cart_file):
            with open(cart_file, "r") as f:
                cart_data = json.load(f)
                # Handle both formats: the MCP format (with "current_cart") and the legacy format (flat array)
                if isinstance(cart_data, dict) and "current_cart" in cart_data:
                    cart_items = cart_data.get("current_cart", [])
                else:
                    cart_items = cart_data if isinstance(cart_data, list) else []
        else:
            cart_items = []

        # Update all items' modality
        updated_count = 0
        for item in cart_items:
            item["modality"] = new_modality
            item["last_updated"] = datetime.now().isoformat()
            updated_count += 1

        if updated_count > 0:
            # Save updated cart in MCP format
            if isinstance(cart_data, dict) and "current_cart" in cart_data:
                cart_data["current_cart"] = cart_items
                cart_data["last_updated"] = datetime.now().isoformat()
                with open(cart_file, "w") as f:
                    json.dump(cart_data, f, indent=2)
            else:
                # Legacy format or new cart
                with open(cart_file, "w") as f:
                    json.dump(
                        {
                            "current_cart": cart_items,
                            "last_updated": datetime.now().isoformat(),
                            "preferred_location_id": None,
                        },
                        f,
                        indent=2,
                    )

            return jsonify(
                {"success": True, "message": f"Updated {updated_count} items to {new_modality}"}
            )
        else:
            return jsonify({"success": True, "message": "No items in cart to update"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# Removed import_cart_items endpoint - manual entry functionality removed


@app.route("/auth/callback")
def auth_callback():
    """Handle OAuth callback from Kroger"""
    try:
        from urllib.parse import parse_qs
        from kroger_api import KrogerAPI

        global _pkce_params, _auth_state

        # Get the authorization code and state from the callback
        auth_code = request.args.get("code")
        received_state = request.args.get("state")
        error = request.args.get("error")

        if error:
            return render_template(
                "auth_result.html",
                success=False,
                message=f"Authorization failed: {error}",
            )

        if not auth_code:
            return render_template(
                "auth_result.html",
                success=False,
                message="No authorization code received",
            )

        if not _pkce_params or not _auth_state:
            return render_template(
                "auth_result.html",
                success=False,
                message="Authentication session expired. Please try again.",
            )

        # Verify state parameter
        if received_state != _auth_state:
            return render_template(
                "auth_result.html",
                success=False,
                message="Security check failed. Please try again.",
            )

        # Exchange the authorization code for tokens
        kroger = KrogerAPI()
        token_info = kroger.authorization.get_token_with_authorization_code(
            auth_code, code_verifier=_pkce_params["code_verifier"]
        )

        # Clear PKCE parameters after successful exchange
        _pkce_params = None
        _auth_state = None

        # Update UI state
        ui_state["auth_status"] = True
        
        # Print token information for debugging
        print("Authentication successful!")
        print("Token info:", token_info)
        print("Received scopes:", token_info.get("scope", "No scopes received"))
        
        # Check if we received the cart scope by decoding the actual JWT token
        import base64
        try:
            access_token = token_info.get("access_token", "")
            if access_token:
                # Decode JWT payload
                parts = access_token.split('.')
                if len(parts) >= 2:
                    payload = parts[1]
                    payload += '=' * (4 - len(payload) % 4)  # Add padding
                    decoded = base64.b64decode(payload)
                    jwt_data = json.loads(decoded)
                    actual_scopes = jwt_data.get("scope", "").split(" ")
                    has_cart_scope = "cart.basic:rw" in actual_scopes
                    print(f"JWT scopes: {actual_scopes}")
                else:
                    received_scopes = token_info.get("scope", "").split(" ")
                    has_cart_scope = "cart.basic:rw" in received_scopes
            else:
                received_scopes = token_info.get("scope", "").split(" ")
                has_cart_scope = "cart.basic:rw" in received_scopes
        except Exception as e:
            print(f"Error decoding JWT: {e}")
            received_scopes = token_info.get("scope", "").split(" ")
            has_cart_scope = "cart.basic:rw" in received_scopes
        
        message = "Authentication successful! You can now close this tab and return to the main app."
        if not has_cart_scope:
            message += " WARNING: The cart.basic:rw scope was not granted, which may limit cart functionality."
            print("WARNING: cart.basic:rw scope not received!")

        return render_template(
            "auth_result.html",
            success=True,
            message=message,
            token_info={
                "expires_in": token_info.get("expires_in"),
                "scope": token_info.get("scope"),
                "has_refresh_token": "refresh_token" in token_info,
                "has_cart_scope": has_cart_scope
            },
        )

    except Exception as e:
        return render_template(
            "auth_result.html",
            success=False,
            message=f"Authentication failed: {str(e)}",
        )


@app.route("/api/auth/start", methods=["POST"])
def start_auth():
    """Start authentication process"""
    try:
        from kroger_api.utils import generate_pkce_parameters
        from kroger_api import KrogerAPI

        # Clear any existing authentication tokens to ensure fresh authentication
        token_file = ".kroger_token_user.json"
        if os.path.exists(token_file):
            try:
                os.remove(token_file)
                print("Cleared existing authentication token for fresh authentication")
            except Exception as e:
                print(f"Warning: Could not remove old token file: {e}")

        # Generate PKCE parameters and store them globally
        global _pkce_params, _auth_state
        _pkce_params = generate_pkce_parameters()
        _auth_state = _pkce_params.get("state", _pkce_params.get("code_verifier")[:16])

        # Get client_id from environment
        client_id = os.environ.get("KROGER_CLIENT_ID")
        # Use the redirect URI from environment or fallback to default
        # Make sure this matches what's registered in the Kroger Developer Portal
        redirect_uri = os.environ.get(
            "KROGER_REDIRECT_URI", "http://localhost:8000/auth/callback"
        )

        if not client_id:
            return jsonify(
                {
                    "success": False,
                    "error": "Missing KROGER_CLIENT_ID environment variable",
                }
            )

        # Initialize the Kroger API client
        kroger = KrogerAPI()

        # Try different scope combinations to see what's available
        # Let's test what scopes are actually available for your application
        
        # Option 1: Try with no scopes to see basic access
        # scopes = ""
        
        # Option 2: Try with just product scope
        # scopes = "product.compact"
        
        # Option 3: Try with cart scope only
        # scopes = "cart.basic:write"
        
        # Option 4: Try with both (original)
        # scopes = "product.compact cart.basic:rw"
        
        # Option 5: Include profile scope to get user information
        # Using profile.name to get firstName and lastName
        # Adding profile.loyalty to get loyalty card information for purchase history
        scopes = "product.compact cart.basic:rw profile.name profile.loyalty"
        
        print(f"Requesting scopes: {scopes}")
        print(f"Client ID: {client_id}")
        print(f"Redirect URI: {redirect_uri}")

        # Get the authorization URL with PKCE
        auth_url = kroger.authorization.get_authorization_url(
            scope=scopes,
            state=_auth_state,
            code_challenge=_pkce_params["code_challenge"],
            code_challenge_method=_pkce_params["code_challenge_method"],
        )
        
        print(f"Generated auth URL: {auth_url}")

        result = {
            "authorization_url": auth_url,
            "message": "Click the button below to authenticate with Kroger. A new tab will open.",
            "debug_info": {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "requested_scopes": scopes,
                "auth_url_preview": auth_url[:100] + "..." if len(auth_url) > 100 else auth_url
            }
        }
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/auth/check", methods=["GET"])
def check_auth_completion():
    """Check if authentication was completed"""
    return jsonify(
        {
            "success": True,
            "authenticated": ui_state["auth_status"],
            "message": (
                "Authentication completed!"
                if ui_state["auth_status"]
                else "Not authenticated"
            ),
        }
    )


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    """Check authentication status"""
    try:
        # Try to get authenticated client to test if auth is working
        client = get_authenticated_client()
        is_valid = client.test_current_token()

        ui_state["auth_status"] = is_valid

        # Use the exact same working logic from debug endpoint
        token_info = client.client.token_info if hasattr(client, 'client') and hasattr(client.client, 'token_info') else None
        scopes = []
        
        if token_info:
            try:
                access_token = token_info.get("access_token", "")
                if access_token:
                    import base64
                    parts = access_token.split('.')
                    if len(parts) >= 2:
                        payload = parts[1]
                        payload += '=' * (4 - len(payload) % 4)
                        decoded = base64.b64decode(payload)
                        jwt_data = json.loads(decoded)
                        scopes = jwt_data.get("scope", "").split(" ")
                        # Filter out empty strings
                        scopes = [s for s in scopes if s.strip()]
                    else:
                        scopes = token_info.get('scope', '').split(' ')
                        scopes = [s for s in scopes if s.strip()]
                else:
                    scopes = token_info.get('scope', '').split(' ')
                    scopes = [s for s in scopes if s.strip()]
            except Exception as e:
                print(f"Error decoding JWT: {e}")
                scopes = token_info.get('scope', '').split(' ') if token_info else []
                scopes = [s for s in scopes if s.strip()]

        # Try to get user name from preferences first, then profile API
        user_name = None
        try:
            # Check for user-defined display name in preferences
            try:
                import json
                with open('kroger_preferences.json', 'r') as f:
                    prefs = json.load(f)
                    user_name = prefs.get('display_name')
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                pass
            
            # Since scope parsing is problematic, try to get profile directly
            print(f"Available scopes: {scopes}")
            
            # If no custom display name, try to get from profile API directly
            if not user_name:
                try:
                    print("Attempting to fetch profile data directly...")
                    profile = client.identity.get_profile()
                    print(f"Raw profile response: {profile}")
                    
                    if profile and "data" in profile:
                        profile_data = profile["data"]
                        print(f"Profile data keys: {list(profile_data.keys())}")
                        
                        # Try to extract actual user name from profile
                        first_name = profile_data.get("firstName")
                        last_name = profile_data.get("lastName") 
                        
                        print(f"Name fields - first: {first_name}, last: {last_name}")
                        
                        if first_name and last_name:
                            user_name = f"{first_name} {last_name}"
                        elif first_name:
                            user_name = first_name
                        else:
                            # Fallback to profile ID if no name fields available
                            profile_id = profile_data.get("id", "")
                            user_name = f"Kroger User {profile_id[:8]}" if profile_id else "Shopper"
                            
                        print(f"Final extracted user name: {user_name}")
                    else:
                        print("No profile data in response")
                        user_name = "Shopper"
                except Exception as profile_error:
                    print(f"Error getting profile info: {profile_error}")
                    user_name = "Shopper"
            
            if not user_name:
                user_name = "Shopper"
        except Exception as e:
            print(f"Could not extract user info: {e}")
            user_name = "Shopper"

        result = {
            "success": True,
            "authenticated": is_valid,
            "token_valid": is_valid,
            "message": f"Authentication token is {'valid' if is_valid else 'invalid'}",
            "scopes": scopes,
            "has_cart_scope": "cart.basic:write" in scopes,
            "user_name": user_name
        }
        return jsonify({"success": True, "data": result})
    except Exception as e:
        ui_state["auth_status"] = False
        result = {
            "success": False,
            "authenticated": False,
            "token_valid": False,
            "error": str(e),
        }
        return jsonify(
            {"success": True, "data": result}
        )  # Still return success=True for the outer wrapper


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    """Force logout/deauthentication by removing the token"""
    try:
        from kroger_mcp.tools.shared import invalidate_authenticated_client
        
        # Invalidate the client to force re-authentication
        invalidate_authenticated_client()
        
        # Remove token files
        token_files = [".kroger_token_user.json", ".kroger_token_client_product.compact.json"]
        for token_file in token_files:
            if os.path.exists(token_file):
                os.remove(token_file)
                print(f"Removed token file: {token_file}")
        
        # Clear the cart since we're no longer authenticated
        cart_file = "kroger_cart.json"
        if os.path.exists(cart_file):
            try:
                # Clear the cart data
                empty_cart = {
                    "current_cart": [],
                    "last_updated": datetime.now().isoformat(),
                    "preferred_location_id": None,
                }
                with open(cart_file, "w") as f:
                    json.dump(empty_cart, f, indent=2)
                print("Cleared cart data on logout")
            except Exception as cart_error:
                print(f"Warning: Could not clear cart: {cart_error}")
        
        # Clear global state
        global _pkce_params, _auth_state
        _pkce_params = None
        _auth_state = None
        
        # Update UI state
        ui_state["auth_status"] = False
        ui_state["cart_items"] = []
        
        return jsonify({
            "success": True,
            "message": "Successfully logged out. Cart has been cleared.",
            "cart_cleared": True
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to logout: {str(e)}"
        })


@app.route("/callback")
def legacy_callback():
    """Handle OAuth callback from Kroger at the old URL"""
    # Get the authorization code and state from the callback
    auth_code = request.args.get("code")
    received_state = request.args.get("state")
    error = request.args.get("error")

    # Log the callback for debugging
    print(
        f"Legacy callback received: code={auth_code}, state={received_state}, error={error}"
    )

    # Redirect to the new callback URL
    return redirect(
        url_for(
            "auth_callback",
            code=auth_code,
            state=received_state,
            error=error,
        )
    )


@app.route("/api/price-tracking/alerts", methods=["GET"])
def get_price_alerts():
    """Get products with significant price drops"""
    try:
        threshold = float(request.args.get('threshold', 10.0))
        alerts = price_tracker.get_price_alerts(threshold_percentage=threshold)
        
        return jsonify({
            "success": True,
            "data": {
                "alerts": alerts,
                "count": len(alerts),
                "threshold_percentage": threshold
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)


@app.route("/api/price-tracking/history/<product_id>", methods=["GET"])
def get_price_history(product_id):
    """Get price history for a specific product"""
    try:
        days = int(request.args.get('days', 30))
        history = price_tracker.get_price_history(product_id, days=days)
        
        return jsonify({
            "success": True,
            "data": {
                "product_id": product_id,
                "history": history,
                "days": days,
                "count": len(history)
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/price-tracking/tracked-products", methods=["GET"])
def get_tracked_products():
    """Get all tracked products with their latest prices"""
    try:
        products = price_tracker.get_tracked_products()
        
        return jsonify({
            "success": True,
            "data": {
                "products": products,
                "count": len(products)
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# Removed duplicate price tracking endpoints - they are already defined above


