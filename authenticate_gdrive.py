#!/usr/bin/env python3
"""
Manual Google Drive Authentication Helper
Use this if automatic browser authentication fails.
"""

import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def manual_authenticate(drive_name: str, client_secrets_file: str):
    """Manually authenticate a Google Drive account."""
    
    print(f"\n🔐 Manual Google Drive Authentication for: {drive_name}")
    print("=" * 60)
    
    # Verify credentials file exists
    secrets_path = Path(client_secrets_file).expanduser()
    if not secrets_path.exists():
        print(f"❌ Error: Credentials file not found at: {secrets_path}")
        print("\nPlease:")
        print("1. Download OAuth credentials from Google Cloud Console")
        print("2. Save to the path specified above")
        return False
    
    try:
        # Create the flow
        flow = InstalledAppFlow.from_client_secrets_file(
            str(secrets_path), 
            SCOPES
        )
        
        print("\n📋 Manual Authorization Steps:")
        print("1. A URL will be displayed below")
        print("2. Copy and paste it into your browser")
        print("3. Sign in to your Google account")
        print("4. Click 'Allow' to grant permissions")
        print("5. Copy the authorization code from the browser")
        print("6. Paste it back here\n")
        
        # Run console-based authentication
        creds = flow.run_console()
        
        # Save the credentials
        token_dir = Path.home() / ".dossierhelper" / "gdrive_credentials"
        token_dir.mkdir(parents=True, exist_ok=True)
        token_path = token_dir / f"token_{drive_name}.pickle"
        
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
        
        print(f"\n✅ Success! Authentication token saved to:")
        print(f"   {token_path}")
        print(f"\n🎉 You can now use '{drive_name}' Google Drive in Dossier Helper!")
        return True
        
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        print("\nTroubleshooting:")
        print("• Make sure you have internet connectivity")
        print("• Verify the credentials file is valid JSON")
        print("• Check that Google Drive API is enabled in Cloud Console")
        return False


def main():
    """Interactive authentication."""
    print("\n🚀 Dossier Helper - Google Drive Manual Authentication")
    print("=" * 60)
    
    # Get drive name
    drive_name = input("\nEnter drive name (e.g., 'personal', 'work'): ").strip()
    if not drive_name:
        print("❌ Drive name cannot be empty")
        return
    
    # Get credentials file path
    default_path = f"~/.dossierhelper/{drive_name}_credentials.json"
    print(f"\nDefault credentials path: {default_path}")
    custom_path = input("Press Enter to use default, or enter custom path: ").strip()
    
    credentials_file = custom_path if custom_path else default_path
    
    # Perform authentication
    success = manual_authenticate(drive_name, credentials_file)
    
    if success:
        print("\n✨ Next steps:")
        print("1. Edit example_config.yaml")
        print(f"2. Set google_drives['{drive_name}'].enabled = true")
        print("3. Run: python3 run_dossierhelper.py")
    else:
        print("\n💡 Need help?")
        print("• See docs/GOOGLE_DRIVE_SETUP.md for detailed instructions")
        print("• Check that port 8080 is not blocked by firewall")


if __name__ == "__main__":
    main()
