# OMEGA Deployment Guide: Going Global

To make your OMEGA Elite C2 accessible from the internet (so agents/victims can connect), follow these tactical steps using **ngrok**.

## 1. Get ngrok
1. Go to [ngrok.com](https://ngrok.com/) and create a free account.
2. Download the `ngrok.exe` for Windows.
3. Unzip it to a folder on your computer.

## 2. Authenticate
Open a terminal in the folder where you unzipped ngrok and run your auth token:
```powershell
.\ngrok.exe config add-authtoken YOUR_PERSONAL_TOKEN_HERE
```

## 3. Start the Tactical Tunnel
Start the tunnel on port 8000:
```powershell
.\ngrok.exe http 8000
```

## 4. Deploy Global Agents
Once ngrok starts, it will give you a "Forwarding" address like `https://a1b2-c3d4-e5f6.ngrok-free.app`.

1. **Access your Dashboard**: Use the ngrok address instead of `localhost` in your browser.
2. **Infiltrate**: When you click the "Infiltrate" button while browsing via the ngrok URL, the agent payload will automatically point to that global address.
3. **Connectivity**: Any agent running that payload will now connect to your C2 from anywhere in the world.

> [!TIP]
> Keep the ngrok terminal open. If you close it, your "online" status will terminate.
