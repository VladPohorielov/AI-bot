# api/oauth_callback.py
"""
Vercel serverless function for handling Google OAuth callbacks
"""

def handler(request):
    try:
        query = request.get("query", {})
        code = query.get("code")
        state = query.get("state")
        error = query.get("error")

        html = "<html><body style='font-family:Arial;'>"

        if error:
            html += f"<h2>OAuth Error: {error}</h2>"
        elif not code:
            html += "<h2>No code provided</h2>"
        else:
            html += f"<h2>OAuth success!</h2>"
            html += f"<p>Code: <b>{code}</b></p>"
            html += f"<p>State: <b>{state}</b></p>"

        html += "</body></html>"

        return {
            "statusCode": 200,
            "headers": { "Content-Type": "text/html" },
            "body": html
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Internal Server Error: {str(e)}"
        }

# This is a Vercel serverless function 