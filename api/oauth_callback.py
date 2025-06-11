def handler(request):
    try:
        # Якщо request це dict — беремо query
        if isinstance(request, dict):
            params = request.get("query", {})
        else:
            # Інакше — пробуємо взяти як атрибут (якщо Vercel передав special object)
            params = getattr(request, "query", {})

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
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Error in handler: {str(e)}"
        }