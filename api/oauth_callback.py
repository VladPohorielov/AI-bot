# api/oauth_callback.py
"""
Vercel serverless function for handling Google OAuth callbacks
"""

def handler(request):
    params = request.get("query", {})
    code = params.get("code")
    state = params.get("state")
    error = params.get("error")

    body = "<html><body style='font-family:Arial;'>"

    if error:
        body += f"<h2>OAuth Error: {error}</h2>"
    elif not code:
        body += "<h2>No code provided</h2>"
    else:
        body += f"<h2>OAuth success!</h2>"
        body += f"<p>Code: <b>{code}</b></p>"
        body += f"<p>State: <b>{state}</b></p>"

    body += "</body></html>"

    return {
        "statusCode": 200,
        "headers": { "Content-Type": "text/html" },
        "body": body
    }

# This is a Vercel serverless function 