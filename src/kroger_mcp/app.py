from flask import Flask, request, jsonify, render_template
from fastmcp import FastMCP
import os

# Import auth_tools specifically for authentication
from .tools import auth_tools

app = Flask(__name__)

# Global variable to store the MCP server instance
mcp_server = None

# Hardcoded redirect URI for this application
KROGER_APP_REDIRECT_URI = "http://localhost:8000/callback"

def get_mcp_server(client_id: str, client_secret: str) -> FastMCP:
    """Initializes and returns an MCP server instance."""
    global mcp_server
    # For simplicity, we re-initialize if client_id/secret change.
    # In a real app, you might manage sessions or a single global server differently.
    if mcp_server is None or \
       mcp_server.kroger_client_id != client_id or \
       mcp_server.kroger_client_secret != client_secret:

        print(f"Initializing FastMCP with new credentials. Client ID: {client_id}")
        # Set environment variables for FastMCP, as it expects them
        os.environ['KROGER_CLIENT_ID'] = client_id
        os.environ['KROGER_CLIENT_SECRET'] = client_secret
        os.environ['KROGER_REDIRECT_URI'] = KROGER_APP_REDIRECT_URI

        mcp_server = FastMCP(
            name="Kroger API Auth Helper",
            instructions="Provides authentication tools for the Kroger API."
        )
        auth_tools.register_tools(mcp_server)

        # Store client_id and client_secret on the server instance for reference
        mcp_server.kroger_client_id = client_id
        mcp_server.kroger_client_secret = client_secret
    return mcp_server

@app.route('/')
def index():
    """Serves the index.html page."""
    return render_template('index.html')

@app.route('/auth_start', methods=['POST'])
def auth_start():
    """
    Starts the authentication process.
    Accepts client_id and client_secret from the form.
    Returns the authorization URL.
    """
    data = request.get_json()
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')

    if not client_id or not client_secret:
        return jsonify({"error": "Client ID and Client Secret are required."}), 400

    try:
        server = get_mcp_server(client_id, client_secret)
        # The start_authentication tool in FastMCP should handle the API call
        # to Kroger and return the authorization URL.
        # It typically takes client_id, client_secret, and redirect_uri as parameters.
        # However, FastMCP tools are usually called by an agent, not directly.
        # We need to ensure the tool can be called programmatically or adapt.

        # For FastMCP, tools are usually invoked via mcp.run_tool("tool_name", {"param": "value"})
        # Assuming start_authentication tool is registered and callable:
        auth_url_response = server.run_tool("start_authentication", {})

        # The response from run_tool might be a string or a dict.
        # Adjust based on actual auth_tools.start_authentication implementation.
        # For now, assuming it returns a dict with 'authorization_url'
        if isinstance(auth_url_response, str): # If it directly returns the URL string
             auth_url = auth_url_response
        elif isinstance(auth_url_response, dict) and "authorization_url" in auth_url_response:
            auth_url = auth_url_response["authorization_url"]
        elif isinstance(auth_url_response, dict) and "url" in auth_url_response: # common pattern
            auth_url = auth_url_response["url"]
        else:
            # Fallback if the structure is different or it's an unexpected message
            # This indicates a mismatch with how `start_authentication` tool returns its result.
            # We might need to inspect the `auth_tools.py` more closely if this path is hit.
            print(f"Unexpected response from start_authentication: {auth_url_response}")
            return jsonify({"error": "Failed to get authorization URL from MCP tool. Check tool's response format."}), 500

        return jsonify({"authorization_url": auth_url})

    except Exception as e:
        print(f"Error in /auth_start: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/auth_complete', methods=['POST'])
def auth_complete():
    """
    Completes the authentication process.
    Accepts the redirect_url from the form.
    Returns the authentication status.
    """
    data = request.get_json()
    redirect_url = data.get('redirect_url')

    if not redirect_url:
        return jsonify({"error": "Redirect URL is required."}), 400

    global mcp_server
    if mcp_server is None:
        return jsonify({"error": "MCP server not initialized. Please start authentication first."}), 400

    try:
        # The complete_authentication tool uses the redirect_url to get tokens.
        # It needs the server instance that was used to start the authentication.
        auth_result = mcp_server.run_tool("complete_authentication", {"redirect_url": redirect_url})

        # Assuming complete_authentication returns a dict with status or token info.
        # Adjust based on actual auth_tools.complete_authentication implementation.
        if isinstance(auth_result, str) and "success" in auth_result.lower():
            return jsonify({"status": "success", "message": auth_result})
        elif isinstance(auth_result, dict):
             return jsonify(auth_result) # Return the whole dict
        else:
            print(f"Unexpected response from complete_authentication: {auth_result}")
            return jsonify({"status": "error", "message": "Authentication failed or unexpected response.", "details": str(auth_result)})

    except Exception as e:
        print(f"Error in /auth_complete: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Note: Flask's dev server is not suitable for production.
    # Use a production WSGI server (e.g., Gunicorn) for deployment.
    app.run(port=8000, debug=True)
