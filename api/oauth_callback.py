# api/oauth_callback.py
"""
Vercel serverless function for handling Google OAuth callbacks
"""

def handler(request):
    """Vercel serverless function for handling Google OAuth callbacks"""
    
    # Get query parameters from request
    params = request.get("query", {})
    code = params.get("code")
    state = params.get("state") 
    error = params.get("error")

    # Build HTML response
    body = "<html><body style='font-family:Arial; text-align:center; padding:50px;'>"

    if error:
        body += f"<h2>❌ OAuth Error: {error}</h2>"
        body += "<p>Спробуйте ще раз або зверніться до підтримки.</p>"
        body += "<a href='https://t.me/briefly_calendar_bot'>← Повернутись до бота</a>"
    elif not code:
        body += "<h2>❌ No code provided</h2>"
        body += "<p>Відсутні необхідні параметри авторизації.</p>"
        body += "<a href='https://t.me/briefly_calendar_bot'>← Повернутись до бота</a>"
    else:
        body += "<h2>✅ OAuth success!</h2>"
        body += f"<p><strong>Code:</strong> <code>{code[:20]}...</code></p>"
        if state:
            body += f"<p><strong>State:</strong> <code>{state}</code></p>"
        
        body += """
        <div style='background:#f0f8ff; padding:20px; margin:20px 0; border-radius:10px;'>
            <h3>📋 Наступні кроки:</h3>
            <ol style='text-align:left; display:inline-block;'>
                <li>Поверніться до Telegram бота</li>
                <li>Надішліть цей код боту</li>
                <li>Або скористайтесь командою /connect_calendar</li>
            </ol>
        </div>
        """
        
        body += """
        <a href='https://t.me/briefly_calendar_bot' style='
            background:#007bff; color:white; padding:10px 20px; 
            text-decoration:none; border-radius:5px; display:inline-block; margin:10px;
        '>🤖 Повернутись до бота</a>
        """
        
        body += f"""
        <button onclick='copyCode()' style='
            background:#28a745; color:white; border:none; 
            padding:8px 16px; border-radius:3px; cursor:pointer; margin:10px;
        '>📋 Копіювати код</button>
        
        <script>
            function copyCode() {{
                navigator.clipboard.writeText('{code}').then(() => {{
                    alert('Код скопійовано!');
                }}).catch(() => {{
                    const textArea = document.createElement('textarea');
                    textArea.value = '{code}';
                    document.body.appendChild(textArea);
                    textArea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textArea);
                    alert('Код скопійовано!');
                }});
            }}
            
            // Auto close after 5 seconds
            setTimeout(() => {{ window.close(); }}, 5000);
        </script>
        
        <p><small>Це вікно автоматично закриється через 5 секунд</small></p>
        """

    body += "</body></html>"

    return {
        "statusCode": 200,
        "headers": { "Content-Type": "text/html; charset=utf-8" },
        "body": body
    }

# This is a Vercel serverless function 