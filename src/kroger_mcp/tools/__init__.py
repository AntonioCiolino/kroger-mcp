"""
Tools package for Kroger MCP server

This package contains all the tool modules organized by functionality:
- location_tools: Store location search and management
- product_tools: Product search and details
- cart_tools: Shopping cart management (view, remove, clear, local tracking)
- cart_consumer_tools: Standard cart add operations (add_to_cart, bulk_add_to_cart)
- cart_partner_tools: Partner API tools (disabled by default, requires special access)
- info_tools: Chain and department information
- profile_tools: User profile and authentication
- auth_tools: OAuth authentication tools
- purchase_history_tools: Purchase history and receipts
- utility_tools: Utility functions
- shared: Common utilities and client management

Cart API Architecture:
- Standard tools (cart_consumer_tools): Work with cart.basic:write scope
  - add_to_cart: Add single item
  - bulk_add_to_cart: Add multiple items
  
- Partner tools (cart_partner_tools): Require special partner-level access
  - Disabled by default
  - Set KROGER_ENABLE_PARTNER_API=true to enable
  - Will show CART-2216 error if you don't have partner access
"""
