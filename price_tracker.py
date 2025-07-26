"""
Simple price tracking system for Kroger products
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class PriceTracker:
    def __init__(self, data_file="price_history.json", blacklist_file="price_blacklist.json"):
        self.data_file = data_file
        self.blacklist_file = blacklist_file
        self.price_data = self._load_data()
        self.blacklist = self._load_blacklist()
        
        # Configuration settings
        self.max_entries_per_product = 15  # Keep last 15 price entries
        self.max_age_days = 90  # Keep data for 90 days
        self.default_alert_threshold = 2.0  # 2% price drop threshold

    def _load_data(self) -> Dict:
        """Load price data from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}

    def _save_data(self):
        """Save price data to JSON file"""
        # Clean up old data before saving
        self._cleanup_old_data()
        with open(self.data_file, "w") as f:
            json.dump(self.price_data, f, indent=2)
    
    def _load_blacklist(self) -> Dict:
        """Load blacklist data from JSON file"""
        if os.path.exists(self.blacklist_file):
            try:
                with open(self.blacklist_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {"hidden_products": [], "removed_products": []}
    
    def _save_blacklist(self):
        """Save blacklist data to JSON file"""
        with open(self.blacklist_file, "w") as f:
            json.dump(self.blacklist, f, indent=2)
    
    def _cleanup_old_data(self, max_age_days: int = 90):
        """Remove price entries older than max_age_days"""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        for product_id, data in list(self.price_data.items()):
            if "price_history" in data:
                # Filter out old entries
                data["price_history"] = [
                    entry for entry in data["price_history"]
                    if datetime.fromisoformat(entry["timestamp"]) > cutoff_date
                ]
                
                # Enforce max entries per product cap
                if len(data["price_history"]) > self.max_entries_per_product:
                    data["price_history"] = data["price_history"][-self.max_entries_per_product:]
                
                # If no recent entries, remove the entire product
                if not data["price_history"]:
                    del self.price_data[product_id]

    def track_price(
        self,
        product_id: str,
        regular_price: float,
        sale_price: Optional[float] = None,
        location_id: str = None,
        product_name: str = None,
    ) -> Dict:
        """
        Track a price for a product
        Returns: Dict with price change information
        """
        now = datetime.now().isoformat()
        current_price = sale_price if sale_price else regular_price

        if product_id not in self.price_data:
            self.price_data[product_id] = {
                "product_name": product_name,
                "location_id": location_id,
                "price_history": [],
                "lowest_price": current_price,
                "highest_price": current_price,
                "first_seen": now,
                "last_updated": now,
            }

        product_data = self.price_data[product_id]

        # Add new price entry
        price_entry = {
            "regular_price": regular_price,
            "sale_price": sale_price,
            "current_price": current_price,
            "timestamp": now,
            "location_id": location_id,
        }

        product_data["price_history"].append(price_entry)
        
        # Enforce max entries per product cap
        if len(product_data["price_history"]) > self.max_entries_per_product:
            product_data["price_history"] = product_data["price_history"][-self.max_entries_per_product:]
        
        product_data["last_updated"] = now

        # Update product name if provided
        if product_name:
            product_data["product_name"] = product_name

        # Calculate price changes
        price_change_info = self._analyze_price_change(product_id, current_price)

        # Update min/max prices
        if current_price < product_data["lowest_price"]:
            product_data["lowest_price"] = current_price
            price_change_info["is_lowest_ever"] = True

        if current_price > product_data["highest_price"]:
            product_data["highest_price"] = current_price

        # Keep only last 30 price entries to prevent file from growing too large
        if len(product_data["price_history"]) > 30:
            product_data["price_history"] = product_data["price_history"][-30:]

        self._save_data()
        return price_change_info

    def _analyze_price_change(self, product_id: str, current_price: float) -> Dict:
        """Analyze price changes and return insights"""
        product_data = self.price_data[product_id]
        history = product_data["price_history"]

        result = {
            "price_changed": False,
            "price_dropped": False,
            "price_increased": False,
            "is_on_sale": False,
            "is_lowest_ever": False,
            "price_drop_amount": 0,
            "price_drop_percentage": 0,
            "days_since_last_change": 0,
        }

        if len(history) < 2:
            return result

        # Compare with previous price
        previous_entry = history[-2]
        previous_price = previous_entry["current_price"]

        if current_price != previous_price:
            result["price_changed"] = True

            if current_price < previous_price:
                result["price_dropped"] = True
                result["price_drop_amount"] = previous_price - current_price
                result["price_drop_percentage"] = (
                    result["price_drop_amount"] / previous_price
                ) * 100
            else:
                result["price_increased"] = True

        # Check if currently on sale
        latest_entry = history[-1]
        if (
            latest_entry.get("sale_price")
            and latest_entry["sale_price"] < latest_entry["regular_price"]
        ):
            result["is_on_sale"] = True

        # Calculate days since last price change
        for i in range(len(history) - 2, -1, -1):
            if history[i]["current_price"] != current_price:
                last_change = datetime.fromisoformat(history[i]["timestamp"])
                current_time = datetime.fromisoformat(history[-1]["timestamp"])
                result["days_since_last_change"] = (current_time - last_change).days
                break

        return result

    def get_price_history(self, product_id: str, days: int = 30) -> List[Dict]:
        """Get price history for a product"""
        if product_id not in self.price_data:
            return []

        cutoff_date = datetime.now() - timedelta(days=days)
        history = self.price_data[product_id]["price_history"]

        return [
            entry
            for entry in history
            if datetime.fromisoformat(entry["timestamp"]) > cutoff_date
        ]

    def get_price_alerts(self, threshold_percentage: float = 10.0) -> List[Dict]:
        """Get products with significant price drops (excluding blacklisted items)"""
        alerts = []
        hidden_products = self.blacklist.get("hidden_products", [])

        for product_id, data in self.price_data.items():
            # Skip hidden products
            if product_id in hidden_products:
                continue
                
            if len(data["price_history"]) < 2:
                continue

            latest = data["price_history"][-1]
            previous = data["price_history"][-2]

            if latest["current_price"] < previous["current_price"]:
                drop_percentage = (
                    (previous["current_price"] - latest["current_price"])
                    / previous["current_price"]
                ) * 100

                if drop_percentage >= threshold_percentage:
                    alerts.append(
                        {
                            "product_id": product_id,
                            "product_name": data.get("product_name", "Unknown Product"),
                            "previous_price": previous["current_price"],
                            "current_price": latest["current_price"],
                            "drop_amount": previous["current_price"]
                            - latest["current_price"],
                            "drop_percentage": drop_percentage,
                            "timestamp": latest["timestamp"],
                        }
                    )

        return sorted(alerts, key=lambda x: x["drop_percentage"], reverse=True)

        return sorted(alerts, key=lambda x: x["drop_percentage"], reverse=True)
    
    def hide_product(self, product_id: str) -> bool:
        """Hide a product from price alerts (blacklist)"""
        hidden_products = self.blacklist.get("hidden_products", [])
        if product_id not in hidden_products:
            hidden_products.append(product_id)
            self.blacklist["hidden_products"] = hidden_products
            self._save_blacklist()
            return True
        return False
    
    def unhide_product(self, product_id: str) -> bool:
        """Unhide a product (remove from blacklist)"""
        hidden_products = self.blacklist.get("hidden_products", [])
        if product_id in hidden_products:
            hidden_products.remove(product_id)
            self.blacklist["hidden_products"] = hidden_products
            self._save_blacklist()
            return True
        return False
    
    def remove_product(self, product_id: str) -> bool:
        """Permanently remove a product from price tracking"""
        if product_id in self.price_data:
            # Add to removed list for reference
            removed_products = self.blacklist.get("removed_products", [])
            if product_id not in removed_products:
                removed_products.append({
                    "product_id": product_id,
                    "product_name": self.price_data[product_id].get("product_name", "Unknown"),
                    "removed_at": datetime.now().isoformat()
                })
                self.blacklist["removed_products"] = removed_products
            
            # Remove from price data
            del self.price_data[product_id]
            
            # Also remove from hidden list if present
            hidden_products = self.blacklist.get("hidden_products", [])
            if product_id in hidden_products:
                hidden_products.remove(product_id)
                self.blacklist["hidden_products"] = hidden_products
            
            self._save_data()
            self._save_blacklist()
            return True
        return False
    
    def get_hidden_products(self) -> List[Dict]:
        """Get list of hidden products with their details"""
        hidden_products = []
        hidden_ids = self.blacklist.get("hidden_products", [])
        
        for product_id in hidden_ids:
            if product_id in self.price_data:
                data = self.price_data[product_id]
                hidden_products.append({
                    "product_id": product_id,
                    "product_name": data.get("product_name", "Unknown Product"),
                    "last_price": data["price_history"][-1]["current_price"] if data["price_history"] else 0,
                    "last_updated": data.get("last_updated", "Unknown")
                })
        
        return hidden_products
    
    def get_removed_products(self) -> List[Dict]:
        """Get list of permanently removed products"""
        return self.blacklist.get("removed_products", [])

    def get_tracked_products(self) -> List[Dict]:
        """Get all tracked products with their latest prices"""
        products = []

        for product_id, data in self.price_data.items():
            if data["price_history"]:
                latest = data["price_history"][-1]
                products.append(
                    {
                        "product_id": product_id,
                        "product_name": data.get("product_name", "Unknown Product"),
                        "current_price": latest["current_price"],
                        "lowest_price": data["lowest_price"],
                        "highest_price": data["highest_price"],
                        "is_on_sale": latest.get("sale_price") is not None,
                        "last_updated": data["last_updated"],
                        "price_entries": len(data["price_history"]),
                    }
                )

        return sorted(products, key=lambda x: x["last_updated"], reverse=True)


# Global price tracker instance
price_tracker = PriceTracker()
