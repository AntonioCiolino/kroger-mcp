"""
Tests for Kroger Cart Consumer API tools.

These tests verify the Consumer API cart tools work correctly with the cart.basic:write scope.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestAddToCartConsumer:
    """Tests for add_to_cart_consumer tool"""

    @pytest.mark.asyncio
    async def test_add_single_item_success(self):
        """Test adding a single item to cart via Consumer API"""
        from src.kroger_mcp.tools import cart_consumer_tools
        
        # Mock the API request function
        with patch.object(
            cart_consumer_tools, 
            '_make_kroger_consumer_api_request',
            new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"success": True, "status_code": 204}
            
            # Create a mock MCP server to register tools
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_consumer_tools.register_tools(mock_mcp)
            
            # Call the tool
            result = await tools['add_to_cart_consumer'](
                upc="0078142152306",
                quantity=2,
                modality="PICKUP"
            )
            
            assert result["success"] is True
            assert result["upc"] == "0078142152306"
            assert result["quantity"] == 2
            assert result["modality"] == "PICKUP"
            assert result["api_type"] == "consumer"
            assert result["endpoint"] == "PUT /v1/cart/add"
            
            # Verify the API was called correctly
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[1]["method"] == "PUT"
            assert call_args[1]["endpoint"] == "/v1/cart/add"
            
            # Verify request body
            request_body = json.loads(call_args[1]["data"])
            assert request_body["items"][0]["upc"] == "0078142152306"
            assert request_body["items"][0]["quantity"] == 2
            assert request_body["items"][0]["modality"] == "PICKUP"

    @pytest.mark.asyncio
    async def test_add_item_auth_failure(self):
        """Test handling of authentication failure"""
        from src.kroger_mcp.tools import cart_consumer_tools
        
        with patch.object(
            cart_consumer_tools,
            '_make_kroger_consumer_api_request',
            new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("401 Unauthorized")
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_consumer_tools.register_tools(mock_mcp)
            
            result = await tools['add_to_cart_consumer'](
                upc="0078142152306",
                quantity=1,
                modality="PICKUP"
            )
            
            assert result["success"] is False
            assert "Authentication failed" in result["error"]

    @pytest.mark.asyncio
    async def test_add_item_bad_request(self):
        """Test handling of bad request (invalid UPC)"""
        from src.kroger_mcp.tools import cart_consumer_tools
        
        with patch.object(
            cart_consumer_tools,
            '_make_kroger_consumer_api_request',
            new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("400 Bad Request: Invalid UPC")
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_consumer_tools.register_tools(mock_mcp)
            
            result = await tools['add_to_cart_consumer'](
                upc="invalid",
                quantity=1,
                modality="PICKUP"
            )
            
            assert result["success"] is False
            assert "Invalid request" in result["error"]


class TestBulkAddToCartConsumer:
    """Tests for bulk_add_to_cart_consumer tool"""

    @pytest.mark.asyncio
    async def test_bulk_add_success(self):
        """Test adding multiple items to cart via Consumer API"""
        from src.kroger_mcp.tools import cart_consumer_tools
        
        with patch.object(
            cart_consumer_tools,
            '_make_kroger_consumer_api_request',
            new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"success": True, "status_code": 204}
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_consumer_tools.register_tools(mock_mcp)
            
            items = [
                {"upc": "0078142152306", "quantity": 2, "modality": "PICKUP"},
                {"upc": "0001111040101", "quantity": 1, "modality": "PICKUP"},
            ]
            
            result = await tools['bulk_add_to_cart_consumer'](items=items)
            
            assert result["success"] is True
            assert result["items_added"] == 2
            assert result["api_type"] == "consumer"
            assert result["endpoint"] == "PUT /v1/cart/add"
            
            # Verify the API was called with all items
            call_args = mock_request.call_args
            request_body = json.loads(call_args[1]["data"])
            assert len(request_body["items"]) == 2

    @pytest.mark.asyncio
    async def test_bulk_add_with_product_id_field(self):
        """Test bulk add accepts product_id as alias for upc"""
        from src.kroger_mcp.tools import cart_consumer_tools
        
        with patch.object(
            cart_consumer_tools,
            '_make_kroger_consumer_api_request',
            new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"success": True, "status_code": 204}
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_consumer_tools.register_tools(mock_mcp)
            
            # Use product_id instead of upc
            items = [
                {"product_id": "0078142152306", "quantity": 1},
            ]
            
            result = await tools['bulk_add_to_cart_consumer'](items=items)
            
            assert result["success"] is True
            
            # Verify the UPC was extracted from product_id
            call_args = mock_request.call_args
            request_body = json.loads(call_args[1]["data"])
            assert request_body["items"][0]["upc"] == "0078142152306"

    @pytest.mark.asyncio
    async def test_bulk_add_default_values(self):
        """Test bulk add uses correct defaults for quantity and modality"""
        from src.kroger_mcp.tools import cart_consumer_tools
        
        with patch.object(
            cart_consumer_tools,
            '_make_kroger_consumer_api_request',
            new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"success": True, "status_code": 204}
            
            mock_mcp = MagicMock()
            tools = {}
            
            def capture_tool():
                def decorator(func):
                    tools[func.__name__] = func
                    return func
                return decorator
            
            mock_mcp.tool = capture_tool
            cart_consumer_tools.register_tools(mock_mcp)
            
            # Minimal item - only UPC
            items = [{"upc": "0078142152306"}]
            
            result = await tools['bulk_add_to_cart_consumer'](items=items)
            
            assert result["success"] is True
            
            # Verify defaults were applied
            call_args = mock_request.call_args
            request_body = json.loads(call_args[1]["data"])
            assert request_body["items"][0]["quantity"] == 1
            assert request_body["items"][0]["modality"] == "PICKUP"


class TestConsumerApiRequest:
    """Tests for the _make_kroger_consumer_api_request helper"""

    @pytest.mark.asyncio
    async def test_handles_204_no_content(self):
        """Test that 204 No Content response is handled correctly"""
        from src.kroger_mcp.tools import cart_consumer_tools
        
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        
        mock_client = MagicMock()
        mock_client.client.token_info = {"access_token": "test_token"}
        
        with patch.object(cart_consumer_tools, 'get_authenticated_client', return_value=mock_client):
            with patch.object(cart_consumer_tools.requests, 'put', return_value=mock_response):
                result = await cart_consumer_tools._make_kroger_consumer_api_request(
                    method="PUT",
                    endpoint="/v1/cart/add",
                    data='{"items": []}'
                )
                
                assert result["success"] is True
                assert result["status_code"] == 204

    @pytest.mark.asyncio
    async def test_raises_on_error_status(self):
        """Test that error status codes raise exceptions"""
        from src.kroger_mcp.tools import cart_consumer_tools
        
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = '{"error": "CART-2216: required scope not found"}'
        
        mock_client = MagicMock()
        mock_client.client.token_info = {"access_token": "test_token"}
        
        with patch.object(cart_consumer_tools, 'get_authenticated_client', return_value=mock_client):
            with patch.object(cart_consumer_tools.requests, 'put', return_value=mock_response):
                with pytest.raises(Exception) as exc_info:
                    await cart_consumer_tools._make_kroger_consumer_api_request(
                        method="PUT",
                        endpoint="/v1/cart/add",
                        data='{"items": []}'
                    )
                
                assert "403" in str(exc_info.value)
