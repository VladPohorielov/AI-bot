# api/oauth_callback.py
"""
Vercel serverless function for handling Google OAuth callbacks
"""

from flask import Flask, request

app = Flask(__name__)

@app.route('/')
def oauth_callback():
    """Handle OAuth callback from Google"""
    
    # Get parameters from request
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    # Handle OAuth errors
    if error:
        return f"""
        <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h2>❌ Помилка авторизації</h2>
                <p>Сталася помилка: {error}</p>
                <p>Спробуйте ще раз або зверніться до підтримки.</p>
                <a href="https://t.me/briefly_calendar_bot">← Повернутись до бота</a>
            </body>
        </html>
        """, 400
    
    # Validate required parameters
    if not code:
        return """
        <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h2>❌ Невірний запит</h2>
                <p>Відсутні необхідні параметри авторизації.</p>
                <a href="https://t.me/briefly_calendar_bot">← Повернутись до бота</a>
            </body>
        </html>
        """, 400
    
    # Success page
    success_page = f"""
    <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h2>✅ Авторизація успішна!</h2>
            <p>Google Calendar авторизацію отримано.</p>
            <p><strong>Код авторизації:</strong> <code id="auth-code">{code[:20]}...</code></p>
            {f"<p><strong>State:</strong> <code>{state}</code></p>" if state else ""}
            
            <div style="background: #f0f8ff; padding: 20px; margin: 20px 0; border-radius: 10px;">
                <h3>📋 Наступні кроки:</h3>
                <ol style="text-align: left; display: inline-block;">
                    <li>Поверніться до Telegram бота</li>
                    <li>Надішліть цей код боту: <strong>{code}</strong></li>
                    <li>Або скористайтесь командою /connect_calendar</li>
                </ol>
            </div>
            
            <p>
                <a href="https://t.me/briefly_calendar_bot" style="
                    background: #007bff; 
                    color: white; 
                    padding: 10px 20px; 
                    text-decoration: none; 
                    border-radius: 5px;
                    display: inline-block;
                    margin-top: 20px;
                ">🤖 Повернутись до бота</a>
            </p>
            
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
            
            <script>
                // Auto close window after 5 seconds
                setTimeout(() => {{
                    window.close();
                }}, 5000);
                
                // Copy code to clipboard
                function copyCode() {{
                    navigator.clipboard.writeText('{code}').then(() => {{
                        alert('Код скопійовано у буфер обміну!');
                    }}).catch(() => {{
                        // Fallback for older browsers
                        const textArea = document.createElement('textarea');
                        textArea.value = '{code}';
                        document.body.appendChild(textArea);
                        textArea.select();
                        document.execCommand('copy');
                        document.body.removeChild(textArea);
                        alert('Код скопійовано у буфер обміну!');
                    }});
                }}
            </script>
        </body>
    </html>
    """
    
    return success_page

# For local development
if __name__ == '__main__':
    app.run(debug=True, port=8080) 