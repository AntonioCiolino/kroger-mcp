"""
Tests for Kroger Cart Partner API tools.

These tests verify the Partner API tools are properly disabled by default
and work correctly when enabled.
"""

import pytest
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestPartnerToolsDisabledByDefault:
    """Tests that Partner API tools are disabled by default"""

    @pytest.mark.asyncio
    async def test_partner_tools_disabled_by_default(self):
        """Test that partner tools show info message when disabled"""
        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            # Need to reload the module to pick up env change
            import importlib
            from src.kroger_mcp.tools import cart_partner_tools
            importlib.reload(cart_partner_tools)
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_partner_tools.register_tools(mock_mcp)
            
            # Should only have the info tool
            assert 'partner_api_info' in tools
            assert 'get_user_carts_partner' not in tools
            assert 'add_item_to_cart_partner' not in tools
            
            # Call the info tool
            result = await tools['partner_api_info']()
            
            assert result["partner_api_enabled"] is False
            assert "disabled" in result["message"].lower()
            assert "KROGER_ENABLE_PARTNER_API" in result["enable_instructions"]

    @pytest.mark.asyncio
    async def test_partner_tools_enabled_with_env_var(self):
        """Test that partner tools are registered when env var is set"""
        with patch.dict(os.environ, {"KROGER_ENABLE_PARTNER_API": "true"}):
            import importlib
            from src.kroger_mcp.tools import cart_partner_tools
            importlib.reload(cart_partner_tools)
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_partner_tools.register_tools(mock_mcp)
            
            # Should have partner tools registered
            assert 'get_user_carts_partner' in tools
            assert 'create_cart_partner' in tools
            assert 'get_cart_by_id_partner' in tools
            assert 'add_item_to_cart_partner' in tools
            assert 'update_cart_item_quantity_partner' in tools
            assert 'delete_cart_item_partner' in tools
            
            # Should NOT have the info tool when enabled
            assert 'partner_api_info' not in tools


class TestPartnerToolsWhenEnabled:
    """Tests for Partner API tools when enabled"""

    @pytest.fixture(autouse=True)
    def enable_partner_api(self):
        """Enable partner API for these tests"""
        with patch.dict(os.environ, {"KROGER_ENABLE_PARTNER_API": "true"}):
            import importlib
            from src.kroger_mcp.tools import cart_partner_tools
            importlib.reload(cart_partner_tools)
            yield

    @pytest.mark.asyncio
    async def test_get_user_carts_partner_success(self):
        """Test getting user carts via Partner API"""
        from src.kroger_mcp.tools import cart_partner_tools
        
        with patch.object(
            cart_partner_tools,
            '_make_kroger_api_request',
            new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "data": [{"id": "cart-123", "items": []}]
            }
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_partner_tools.register_tools(mock_mcp)
            
            result = await tools['get_user_carts_partner']()
            
            assert result["success"] is True
            assert result["api_type"] == "partner"
            assert "data" in result

    @pytest.mark.asyncio
    async def test_add_item_to_cart_partner_success(self):
        """Test adding item via Partner API"""
        from src.kroger_mcp.tools import cart_partner_tools
        
        with patch.object(
            cart_partner_tools,
            '_make_kroger_api_request',
            new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"success": True}
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_partner_tools.register_tools(mock_mcp)
            
            result = await tools['add_item_to_cart_partner'](
                cart_id="cart-123",
                upc="0078142152306",
                quantity=2,
                modality="PICKUP"
            )
            
            assert result["success"] is True
            assert result["api_type"] == "partner"
            assert result["cart_id"] == "cart-123"
            assert result["upc"] == "0078142152306"

    @pytest.mark.asyncio
    async def test_partner_api_cart_2216_error(self):
        """Test that CART-2216 error provides helpful message"""
        from src.kroger_mcp.tools import cart_partner_tools
        
        with patch.object(
            cart_partner_tools,
            '_make_kroger_api_request',
            new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("CART-2216: required scope not found")
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_partner_tools.register_tools(mock_mcp)
            
            result = await tools['get_user_carts_partner']()
            
            assert result["success"] is False
            assert "Partner API access required" in result["error"]
            assert "recommendation" in result

    @pytest.mark.asyncio
    async def test_update_cart_item_quantity_validates_upc_length(self):
        """Test that UPC length validation works"""
        from src.kroger_mcp.tools import cart_partner_tools
        
        mock_mcp = MagicMock()
        tools = {}
        
        def capture_tool():
            def decorator(func):
                tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = capture_tool
        cart_partner_tools.register_tools(mock_mcp)
        
        # UPC too short
        result = await tools['update_cart_item_quantity_partner'](
            cart_id="cart-123",
            upc="123",  # Too short, should be 13 chars
            quantity=2
        )
        
        assert result["success"] is False
        assert "13 characters" in result["error"]

    @pytest.mark.asyncio
    async def test_delete_cart_item_validates_upc_length(self):
        """Test that delete validates UPC length"""
        from src.kroger_mcp.tools import cart_partner_tools
        
        mock_mcp = MagicMock()
        tools = {}
        
        def capture_tool():
            def decorator(func):
                tools[func.__name__] = func
                return func
            return decorator
        
        mock_mcp.tool = capture_tool
        cart_partner_tools.register_tools(mock_mcp)
        
        # UPC too short
        result = await tools['delete_cart_item_partner'](
            cart_id="cart-123",
            upc="short"
        )
        
        assert result["success"] is False
        assert "13 characters" in result["error"]
