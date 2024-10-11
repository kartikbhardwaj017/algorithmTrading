from flask import Flask, request, render_template_string, jsonify
from kiteconnect import KiteConnect, KiteTicker

import json

# Replace with your API Key and Secret
api_key = ""
api_secret = ""


app = Flask(__name__)


kite = KiteConnect(api_key=api_key)

# Route to generate the login URL and display it in an HTML page
@app.route('/generate-auth-url', methods=['GET'])
def generate_auth_url():
    login_url = kite.login_url()
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login with Kite</title>
    </head>
    <body style="display: flex; justify-content: center; align-items: center; height: 100vh;">
        <a href="{login_url}" target="_blank" style="font-size: 20px;">Click here to login with Kite</a>
    </body>
    </html>
    '''
    return render_template_string(html_content)

# Route to handle request token, generate access token, and save session data to JSON file
@app.route('/get-access-token', methods=['GET'])
def get_access_token():
    request_token = request.args.get('request_token')

    if not request_token:
        return jsonify({"error": "Request token is missing"}), 400

    try:
        # Generate session using the request token
        data = kite.generate_session(request_token, api_secret)
        kite.set_access_token(data["access_token"])

        session_data = {
            "access_token": data["access_token"],
            "public_token": data.get("public_token", ""),  # Add any other relevant data here
            "user_id": data.get("user_id", "")
        }
    

        # Save session data to JSON file
        with open("zerodhaSession.json", "w") as json_file:
            json.dump(session_data, json_file, indent=4)

        return jsonify({"message": "Access token generated and saved successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
