# Google Drive Authentication Troubleshooting

## 🐛 Error: "nodename nor servname provided, or not known"

This DNS resolution error occurs when the OAuth authentication can't bind to localhost. Here are the solutions:

---

## ✅ **Solution 1: Fix /etc/hosts File**

### Check your hosts file:
```bash
cat /etc/hosts
```

### Should contain:
```
127.0.0.1       localhost
::1             localhost
127.0.0.1       broadcasthost
::1             ip6-localhost ip6-loopback
```

### If missing, add them:
```bash
sudo nano /etc/hosts
# Add the lines above
# Save: Ctrl+O, Enter, Ctrl+X
```

---

## ✅ **Solution 2: Use Manual Authentication**

If automatic browser authentication fails, use the manual authentication script:

```bash
cd /Users/andrewbajorek/Documents/GitHub/dossierhelper
source .venv/bin/activate
python3 authenticate_gdrive.py
```

Follow the prompts:
1. Enter drive name (e.g., "personal")
2. Confirm credentials file path
3. Copy URL to browser manually
4. Authorize in browser
5. Copy code back to terminal

---

## ✅ **Solution 3: Check Firewall/Network**

### Test connectivity:
```bash
# Test internet
ping -c 3 google.com

# Test Google OAuth endpoint
curl -I https://accounts.google.com

# Check if port 8080 is available
lsof -i :8080
```

### macOS Firewall:
1. System Settings → Network → Firewall
2. Make sure Python is allowed
3. Or temporarily disable firewall for testing

---

## ✅ **Solution 4: Try Different Port**

The updated code now uses port **8080** instead of a random port. If this is blocked:

Edit `src/dossierhelper/gdrive.py` line ~108:
```python
creds = flow.run_local_server(
    port=8081,  # Try different port: 8081, 8888, 9090
    open_browser=True,
    bind_addr='127.0.0.1'
)
```

---

## ✅ **Solution 5: VPN/Proxy Issues**

If you're using a VPN or corporate proxy:

### Temporarily disable VPN:
```bash
# Test without VPN
# Then re-enable after authentication
```

### Set proxy environment variables:
```bash
export HTTP_PROXY=your_proxy
export HTTPS_PROXY=your_proxy
```

---

## ✅ **Solution 6: DNS Resolution**

### Flush DNS cache:
```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

### Test DNS:
```bash
nslookup accounts.google.com
# Should return IP addresses
```

---

## 📋 **Complete Manual Authentication Process**

### Step 1: Run authentication script
```bash
python3 authenticate_gdrive.py
```

### Step 2: When prompted, you'll see:
```
Visit this URL in your browser:
https://accounts.google.com/o/oauth2/auth?...very-long-url...

Enter the authorization code:
```

### Step 3: Copy the URL
```bash
# Copy the entire URL starting with https://
```

### Step 4: Open in browser
- Paste URL in your browser
- Sign in to Google account
- Click "Allow"
- Browser shows authorization code

### Step 5: Copy code back
```bash
Enter the authorization code: 4/1AY0e-g7_very_long_code_here
```

### Step 6: Success!
```
✅ Success! Authentication token saved
🎉 You can now use 'personal' Google Drive in Dossier Helper!
```

---

## 🧪 **Testing After Fix**

### Test 1: Verify token was saved
```bash
ls ~/.dossierhelper/gdrive_credentials/
# Should show: token_personal.pickle (or your drive name)
```

### Test 2: Run Dossier Helper
```bash
python3 run_dossierhelper.py
# Should now authenticate successfully
```

---

## 🔍 **Diagnostic Commands**

### Check network configuration:
```bash
# Check localhost resolution
ping -c 1 localhost
ping -c 1 127.0.0.1

# Check network interfaces
ifconfig lo0

# Check DNS servers
scutil --dns
```

### Check Python network capabilities:
```bash
python3 -c "import socket; print(socket.gethostbyname('localhost'))"
# Should print: 127.0.0.1
```

### Test OAuth server manually:
```bash
python3 << EOF
from http.server import HTTPServer, BaseHTTPRequestHandler
server = HTTPServer(('127.0.0.1', 8080), BaseHTTPRequestHandler)
print("Server started on port 8080")
server.server_close()
print("Server closed successfully")
EOF
```

---

## 📝 **Common Error Messages**

### "nodename nor servname provided"
- **Cause**: DNS can't resolve localhost
- **Fix**: Update /etc/hosts or use manual auth

### "Address already in use"
- **Cause**: Port 8080 is occupied
- **Fix**: Use different port or kill process: `lsof -ti:8080 | xargs kill`

### "Connection refused"
- **Cause**: Firewall blocking connection
- **Fix**: Allow Python in firewall settings

### "Invalid client secrets"
- **Cause**: Wrong credentials file
- **Fix**: Re-download from Google Cloud Console

---

## 🆘 **Still Not Working?**

### Option 1: Skip Google Drive
```yaml
# example_config.yaml
google_drives:
  - name: "personal"
    enabled: false  # Disable for now
```

### Option 2: Use web-based authentication
Visit this page and copy your credentials:
```
https://developers.google.com/oauthplayground/
```

### Option 3: Contact for help
Check the logs for more details:
```bash
python3 run_dossierhelper.py 2>&1 | tee auth_debug.log
```

---

## ✅ **Prevention**

Once authenticated successfully:

1. **Token is cached** - No need to re-authenticate
2. **Token location**: `~/.dossierhelper/gdrive_credentials/token_*.pickle`
3. **Expires**: Tokens refresh automatically
4. **Backup tokens**: Optional but recommended

```bash
# Backup your tokens
cp -r ~/.dossierhelper/gdrive_credentials ~/Desktop/gdrive_backup
```

---

## 🎓 **Understanding the Error**

The error "nodename nor servname provided, or not known" means:
- **nodename**: Hostname (like "localhost")
- **servname**: Service/port name
- **Translation**: "I can't figure out what 'localhost' means"

This happens when:
1. `/etc/hosts` is missing localhost entry
2. DNS resolver is misconfigured
3. Network stack has issues
4. Firewall is blocking resolution

The OAuth flow needs to:
1. Start a local web server on your computer
2. Bind it to `localhost:8080` (or another port)
3. Receive the authorization code from Google
4. Exchange it for an access token

If "localhost" can't be resolved to "127.0.0.1", the server can't start.

---

## 🎉 **Success Indicators**

You know it's working when you see:
```
[cyan] Opening browser for authentication...
[green] Successfully authenticated 'personal'
[green] ✓ Google Drive 'personal' authenticated successfully
```

No errors = Ready to scan! 🚀
