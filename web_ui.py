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
    """Remove an item from the cart"""
    try:
        data = request.get_json()
        product_id = data.get("product_id")

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

        # Remove the item matching product_id only, ignore modality
        original_count = len(cart_items)
        cart_items = [
            item for item in cart_items if item.get("product_id") != product_id
        ]

        if len(cart_items) < original_count:
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

            return jsonify({"success": True, "message": "Item removed from cart"})
        else:
            return jsonify({"success": False, "error": "Item not found in cart"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/view", methods=["GET"])
def view_cart():
    """View current cart with enhanced product details"""
    try:
        # Read local cart tracking since Kroger API doesn't provide cart viewing
        cart_file = "kroger_cart.json"
        if os.path.exists(cart_file):
            try:
                with open(cart_file, "r") as f:
                    cart_data = json.load(f)
                    # Handle both formats: the MCP format (with "current_cart") and the legacy format (flat array)
                    if isinstance(cart_data, dict) and "current_cart" in cart_data:
                        all_cart_items = cart_data.get("current_cart", [])
                    else:
                        all_cart_items = (
                            cart_data if isinstance(cart_data, list) else []
                        )
            except json.JSONDecodeError:
                # If the file exists but is not valid JSON, create a new empty cart in MCP format
                all_cart_items = []
                with open(cart_file, "w") as f:
                    json.dump(
                        {
                            "current_cart": [],
                            "last_updated": None,
                            "preferred_location_id": None,
                        },
                        f,
                        indent=2,
                    )
        else:
            # If the file doesn't exist, create a new empty cart in MCP format
            all_cart_items = []
            with open(cart_file, "w") as f:
                json.dump(
                    {
                        "current_cart": [],
                        "last_updated": None,
                        "preferred_location_id": None,
                    },
                    f,
                    indent=2,
                )

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
                                enhanced_item["pricing"] = {
                                    "regular_price": price.get("regular"),
                                    "sale_price": price.get("promo"),
                                    "on_sale": price.get("promo") is not None
                                    and price.get("promo")
                                    < price.get("regular", float("inf")),
                                }

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
    """Sync local cart with Kroger cart"""
    try:
        # Check if we should clear the cart instead of adding sample items
        data = request.get_json() or {}
        if data.get("clear", False):
            # Clear the cart
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

        # Since direct cart fetching from Kroger API isn't available with current authentication,
        # we'll maintain local cart storage which is actually a good approach for this use case
        cart_file = "kroger_cart.json"
        
        # Ensure we have an empty cart file
        cart_data = {
            "current_cart": [],
            "last_updated": datetime.now().isoformat(),
            "preferred_location_id": None
        }
        
        with open(cart_file, "w") as f:
            json.dump(cart_data, f, indent=2)
        
        return jsonify({
            "success": True,
            "message": "Cart synced (using local storage). Add items to cart to track them locally.",
            "note": "This app uses local cart tracking since Kroger API cart access requires partner-level authentication."
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cart/clear", methods=["POST"])
def clear_cart():
    """Clear all items from the cart"""
    try:
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


@app.route("/api/cart/import", methods=["POST"])
def import_cart_items():
    """Import multiple items to the cart"""
    try:
        data = request.get_json()
        items = data.get("items", [])

        if not items:
            return jsonify({"success": False, "error": "No items provided"})

        # Get preferred location
        from kroger_mcp.tools.shared import get_preferred_location_id

        location_id = get_preferred_location_id()

        if not location_id:
            return jsonify(
                {
                    "success": False,
                    "error": "No preferred location set. Please set a preferred location first.",
                }
            )

        # Read current cart
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

        # Process each item
        client = get_authenticated_client()
        kroger_items = []
        added_count = 0

        for item_data in items:
            product_id = item_data.get("product_id")
            quantity = item_data.get("quantity", 1)

            if not product_id:
                continue

            # Add to Kroger cart
            kroger_items.append({"upc": product_id, "quantity": quantity})

            # Add to local tracking
            existing_item = None
            for item in cart_items:
                if item.get("product_id") == product_id:
                    existing_item = item
                    break

            if existing_item:
                # Update existing item quantity
                existing_item["quantity"] = existing_item.get("quantity", 0) + quantity
                existing_item["last_updated"] = datetime.now().isoformat()
            else:
                # Add new item
                cart_items.append(
                    {
                        "product_id": product_id,
                        "quantity": quantity,
                        "added_at": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                        "location_id": location_id,
                    }
                )

            added_count += 1

        # Add items to Kroger cart
        if kroger_items:
            try:
                client.cart.add_to_cart(kroger_items)
            except Exception as e:
                print(f"Warning: Could not add items to Kroger cart: {e}")

        # Save updated cart
        cart_data["current_cart"] = cart_items
        cart_data["last_updated"] = datetime.now().isoformat()
        cart_data["preferred_location_id"] = location_id

        with open(cart_file, "w") as f:
            json.dump(cart_data, f, indent=2)

        return jsonify(
            {
                "success": True,
                "message": f"Successfully imported {added_count} items",
                "items_added": added_count,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


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
        
        # Check if we received the cart scope
        received_scopes = token_info.get("scope", "").split(" ")
        has_cart_scope = "cart.basic:write" in received_scopes
        
        message = "Authentication successful! You can now close this tab and return to the main app."
        if not has_cart_scope:
            message += " WARNING: The cart.basic:write scope was not granted, which may limit cart functionality."
            print("WARNING: cart.basic:write scope not received!")

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
        scopes = "product.compact cart.basic:write"
        
        # Option 5: Try with profile scope to test user authentication
        # scopes = "profile.compact"
        
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

        # Get token information including scopes
        token_info = None
        scopes = []
        if hasattr(client, 'client') and hasattr(client.client, 'token_info'):
            token_info = client.client.token_info
            scopes = token_info.get('scope', '').split(' ') if token_info else []

        result = {
            "success": True,
            "authenticated": is_valid,
            "token_valid": is_valid,
            "message": f"Authentication token is {'valid' if is_valid else 'invalid'}",
            "scopes": scopes,
            "has_cart_scope": "cart.basic:write" in scopes
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
        
        # Remove the token file if it exists
        token_file = ".kroger_token_user.json"
        if os.path.exists(token_file):
            os.remove(token_file)
            print(f"Removed token file: {token_file}")
        
        # Update UI state
        ui_state["auth_status"] = False
        
        return jsonify({
            "success": True,
            "message": "Successfully logged out. You will need to re-authenticate."
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
