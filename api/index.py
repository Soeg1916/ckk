from flask import Flask, request, jsonify
import os
import sys

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the app from the parent directory
from app import app as flask_app

# This is necessary for Vercel serverless deployment
app = flask_app

# Import webhook functionality
from api.webhook import *

# Add a simple status endpoint for health checks
@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        "status": "online",
        "message": "Bot API is running"
    })

# Add error handlers
@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"Server error: {e}")
    return jsonify({
        "status": "error",
        "message": "An internal server error occurred",
        "error": str(e)
    }), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "status": "error",
        "message": "Resource not found"
    }), 404

# If this file is run directly, start the app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
