"""
Simple OAuth callback server for handling Google Calendar OAuth redirects
"""
import asyncio
import sys
import os
from pathlib import Path
from aiohttp import web, ClientSession
from urllib.parse import parse_qs, urlparse
import logging

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent))

from config import GOOGLE_REDIRECT_URI
from services.google_oauth import GoogleOAuthService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OAuthCallbackServer:
    def __init__(self, port=8080):
        self.port = port
        self.oauth_service = GoogleOAuthService()
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_get('/oauth/callback', self.handle_oauth_callback)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/', self.home)
    
    async def handle_oauth_callback(self, request):
        """Handle OAuth callback from Google"""
        try:
            # Get parameters from query string
            code = request.query.get('code')
            state = request.query.get('state')
            error = request.query.get('error')
            
            if error:
                logger.error(f"OAuth error: {error}")
                return web.Response(
                    text=f"""
                    <html>
                        <body style="font-family: Arial; text-align: center; padding: 50px;">
                            <h2>❌ Помилка авторизації</h2>
                            <p>Сталася помилка: {error}</p>
                            <p>Спробуйте ще раз або зверніться до підтримки.</p>
                        </body>
                    </html>
                    """,
                    content_type='text/html',
                    status=400
                )
            
            if not code or not state:
                return web.Response(
                    text="""
                    <html>
                        <body style="font-family: Arial; text-align: center; padding: 50px;">
                            <h2>❌ Невірний запит</h2>
                            <p>Відсутні необхідні параметри авторизації.</p>
                        </body>
                    </html>
                    """,
                    content_type='text/html',
                    status=400
                )
            
            # Exchange code for tokens
            tokens = await self.oauth_service.exchange_code_for_tokens(code, state)
            
            if tokens:
                logger.info("OAuth tokens successfully exchanged")
                return web.Response(
                    text="""
                    <html>
                        <body style="font-family: Arial; text-align: center; padding: 50px;">
                            <h2>✅ Успішно підключено!</h2>
                            <p>Google Calendar успішно підключено до вашого Telegram бота.</p>
                            <p>Тепер ви можете закрити це вікно та повернутись до бота.</p>
                            <script>
                                setTimeout(() => {
                                    window.close();
                                }, 3000);
                            </script>
                        </body>
                    </html>
                    """,
                    content_type='text/html'
                )
            else:
                logger.error("Failed to exchange OAuth code for tokens")
                return web.Response(
                    text="""
                    <html>
                        <body style="font-family: Arial; text-align: center; padding: 50px;">
                            <h2>❌ Помилка обміну токенів</h2>
                            <p>Не вдалося завершити авторизацію.</p>
                            <p>Спробуйте ще раз.</p>
                        </body>
                    </html>
                    """,
                    content_type='text/html',
                    status=500
                )
                
        except Exception as e:
            logger.error(f"Error in OAuth callback: {e}")
            return web.Response(
                text="""
                <html>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h2>❌ Внутрішня помилка сервера</h2>
                        <p>Сталася непередбачена помилка.</p>
                    </body>
                </html>
                """,
                content_type='text/html',
                status=500
            )
    
    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({'status': 'ok', 'service': 'oauth-callback-server'})
    
    async def home(self, request):
        """Home page"""
        return web.Response(
            text="""
            <html>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1>🤖 Telegram Calendar Bot</h1>
                    <h2>OAuth Callback Server</h2>
                    <p>Сервер працює та готовий обробляти OAuth redirects.</p>
                    <p>Щоб підключити календар, використайте команду /settings у боті.</p>
                </body>
            </html>
            """,
            content_type='text/html'
        )

async def create_app():
    """Create and configure the web application"""
    server = OAuthCallbackServer()
    return server.app

async def main():
    """Run the OAuth callback server"""
    print("🚀 Запуск OAuth callback сервера...")
    print(f"📡 Сервер доступний на: http://localhost:8080")
    print(f"🔗 Callback URL: http://localhost:8080/oauth/callback")
    print("⏹️  Для зупинки натисніть Ctrl+C")
    
    app = await create_app()
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        print("\n🛑 Зупинка сервера...")
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main()) 