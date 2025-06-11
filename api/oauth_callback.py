# api/oauth_callback.py
"""
Vercel serverless function for handling Google OAuth callbacks
"""
import os
import sys
import asyncio
from urllib.parse import parse_qs, urlencode
import json

# Add parent directory to path to import from services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from services.google_oauth import GoogleOAuthService
except ImportError:
    # Fallback for Vercel environment
    GoogleOAuthService = None

def handler(request):
    """
    Vercel serverless function handler for OAuth callback
    """
    # Get query parameters
    query_params = parse_qs(request.query_string.decode()) if hasattr(request, 'query_string') else {}
    
    # Handle different request formats (Vercel WSGI/ASGI)
    if hasattr(request, 'args'):
        # Flask-like request object
        code = request.args.get('code')
        state = request.args.get('state') 
        error = request.args.get('error')
    else:
        # Raw query parameters
        code = query_params.get('code', [None])[0]
        state = query_params.get('state', [None])[0]
        error = query_params.get('error', [None])[0]
    
    # Handle OAuth errors
    if error:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'text/html; charset=utf-8'},
            'body': f"""
            <html>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2>❌ Помилка авторизації</h2>
                    <p>Сталася помилка: {error}</p>
                    <p>Спробуйте ще раз або зверніться до підтримки.</p>
                    <a href="https://t.me/your_bot_username">← Повернутись до бота</a>
                </body>
            </html>
            """
        }
    
    # Validate required parameters
    if not code or not state:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'text/html; charset=utf-8'},
            'body': """
            <html>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h2>❌ Невірний запит</h2>
                    <p>Відсутні необхідні параметри авторизації.</p>
                    <a href="https://t.me/your_bot_username">← Повернутись до бота</a>
                </body>
            </html>
            """
        }
    
    # In production, you would handle the OAuth flow here
    # For now, return success page with instructions
    success_page = f"""
    <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h2>✅ Авторизація успішна!</h2>
            <p>Google Calendar авторизацію отримано.</p>
            <p><strong>Код авторизації:</strong> <code>{code[:20]}...</code></p>
            <p><strong>State:</strong> <code>{state}</code></p>
            
            <div style="background: #f0f8ff; padding: 20px; margin: 20px 0; border-radius: 10px;">
                <h3>📋 Наступні кроки:</h3>
                <ol style="text-align: left; display: inline-block;">
                    <li>Поверніться до Telegram бота</li>
                    <li>Надішліть цей код боту: <strong>{code}</strong></li>
                    <li>Або скористайтесь командою /connect_calendar</li>
                </ol>
            </div>
            
            <p>
                <a href="https://t.me/your_bot_username" style="
                    background: #007bff; 
                    color: white; 
                    padding: 10px 20px; 
                    text-decoration: none; 
                    border-radius: 5px;
                    display: inline-block;
                    margin-top: 20px;
                ">🤖 Повернутись до бота</a>
            </p>
            
            <script>
                // Auto close window after 5 seconds
                setTimeout(() => {{
                    window.close();
                }}, 5000);
                
                // Copy code to clipboard
                function copyCode() {{
                    navigator.clipboard.writeText('{code}');
                    alert('Код скопійовано у буфер обміну!');
                }}
            </script>
            
            <p>
                <button onclick="copyCode()" style="
                    background: #28a745; 
                    color: white; 
                    border: none; 
                    padding: 8px 16px; 
                    border-radius: 3px; 
                    cursor: pointer;
                ">📋 Копіювати код</button>
            </p>
            
            <small>Це вікно автоматично закриється через 5 секунд</small>
        </body>
    </html>
    """
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/html; charset=utf-8'},
        'body': success_page
    }

# For Flask compatibility (local development)
try:
    from flask import Flask, request as flask_request
    
    app = Flask(__name__)
    
    @app.route('/api/oauth_callback', methods=['GET'])
    def oauth_callback():
        return handler(flask_request)
    
    @app.route('/oauth/callback', methods=['GET'])  
    def oauth_callback_alt():
        return handler(flask_request)
        
    if __name__ == '__main__':
        app.run(debug=True, port=8080)
        
except ImportError:
    # Flask not available in Vercel environment
    pass

# Export for Vercel
def app(environ, start_response):
    """WSGI application for Vercel"""
    from werkzeug.wrappers import Request
    request = Request(environ)
    
    response = handler(request)
    
    status = f"{response['statusCode']} OK"
    headers = [(k, v) for k, v in response['headers'].items()]
    
    start_response(status, headers)
    return [response['body'].encode('utf-8')] 