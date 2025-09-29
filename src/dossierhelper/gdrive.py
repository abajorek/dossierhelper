"""Google Drive integration for dossierhelper."""

from __future__ import annotations

import io
import pickle
from pathlib import Path
from typing import Iterator, Optional, Callable, List, Dict
from dataclasses import dataclass

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from rich.console import Console

console = Console()

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


@dataclass
class GDriveFile:
    """Represents a file from Google Drive."""
    
    id: str
    name: str
    mime_type: str
    size: int
    modified_time: str
    web_view_link: str
    drive_name: str  # Which Google Drive this belongs to
    
    @property
    def is_supported_document(self) -> bool:
        """Check if this is a supported document type."""
        supported_types = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/msword',
            'text/plain',
            'application/vnd.google-apps.document',  # Google Docs
            'application/vnd.google-apps.presentation',  # Google Slides
            'application/vnd.google-apps.spreadsheet',  # Google Sheets
        ]
        return self.mime_type in supported_types


class GoogleDriveManager:
    """Manages connections to multiple Google Drive accounts."""
    
    def __init__(self, credentials_dir: Path):
        """
        Initialize the Google Drive Manager.
        
        Args:
            credentials_dir: Directory to store credentials files
        """
        self.credentials_dir = Path(credentials_dir)
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        self.services: Dict[str, any] = {}
        
    def authenticate_drive(self, drive_name: str, client_secrets_file: Optional[Path] = None) -> bool:
        """
        Authenticate a Google Drive account.
        
        Args:
            drive_name: Friendly name for this drive (e.g., "personal", "work")
            client_secrets_file: Path to OAuth client secrets JSON file
            
        Returns:
            True if authentication successful
        """
        token_path = self.credentials_dir / f"token_{drive_name}.pickle"
        creds = None
        
        # Load existing credentials
        if token_path.exists():
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    console.log(f"[green]Refreshed credentials for '{drive_name}'")
                except Exception as e:
                    console.log(f"[yellow]Could not refresh credentials for '{drive_name}': {e}")
                    creds = None
            
            if not creds:
                if not client_secrets_file or not client_secrets_file.exists():
                    console.log(f"[red]No client secrets file found for '{drive_name}'. Cannot authenticate.")
                    console.log(f"[yellow]Please provide OAuth credentials file or run authentication first.")
                    return False
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(client_secrets_file), SCOPES
                    )
                    
                    # Try local server first (automatic browser flow)
                    try:
                        console.log(f"[cyan]Opening browser for authentication...")
                        creds = flow.run_local_server(
                            port=8080,  # Use specific port instead of 0
                            open_browser=True,
                            bind_addr='127.0.0.1'  # Explicitly use 127.0.0.1
                        )
                        console.log(f"[green]Successfully authenticated '{drive_name}'")
                    except OSError as e:
                        # If local server fails, try manual flow
                        console.log(f"[yellow]Local server auth failed: {e}")
                        console.log(f"[cyan]Falling back to manual authorization...")
                        console.log(f"[yellow]Please follow the instructions below:")
                        creds = flow.run_console()
                        console.log(f"[green]Successfully authenticated '{drive_name}'")
                        
                except Exception as e:
                    console.log(f"[red]Authentication failed for '{drive_name}': {e}")
                    console.log(f"[yellow]Troubleshooting:")
                    console.log(f"[yellow]  1. Check internet connection: ping google.com")
                    console.log(f"[yellow]  2. Verify /etc/hosts has: 127.0.0.1 localhost")
                    console.log(f"[yellow]  3. Check firewall settings")
                    console.log(f"[yellow]  4. Try manual auth by running: python3 -m dossierhelper.gdrive_auth")
                    return False
            
            # Save credentials
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        # Build the service
        try:
            service = build('drive', 'v3', credentials=creds)
            self.services[drive_name] = service
            console.log(f"[green]Google Drive service ready for '{drive_name}'")
            return True
        except Exception as e:
            console.log(f"[red]Failed to build Drive service for '{drive_name}': {e}")
            return False
    
    def list_files(
        self,
        drive_name: str,
        folder_id: Optional[str] = None,
        recursive: bool = True,
        page_size: int = 100,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Iterator[GDriveFile]:
        """
        List files from a Google Drive.
        
        Args:
            drive_name: Name of the authenticated drive
            folder_id: Optional folder ID to search within
            recursive: Whether to search recursively through subdirectories
            page_size: Number of files to fetch per API call
            progress_callback: Optional callback(count, file_name) for progress updates
            
        Yields:
            GDriveFile objects
        """
        if drive_name not in self.services:
            console.log(f"[red]Drive '{drive_name}' not authenticated")
            return
        
        service = self.services[drive_name]
        
        try:
            # Build query
            query_parts = ["trashed = false"]
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")
            
            query = " and ".join(query_parts)
            
            page_token = None
            file_count = 0
            
            while True:
                results = service.files().list(
                    q=query,
                    pageSize=page_size,
                    fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)",
                    pageToken=page_token
                ).execute()
                
                items = results.get('files', [])
                
                for item in items:
                    gdrive_file = GDriveFile(
                        id=item['id'],
                        name=item['name'],
                        mime_type=item['mimeType'],
                        size=int(item.get('size', 0)),
                        modified_time=item['modifiedTime'],
                        web_view_link=item.get('webViewLink', ''),
                        drive_name=drive_name
                    )
                    
                    file_count += 1
                    
                    if progress_callback:
                        progress_callback(file_count, gdrive_file.name)
                    
                    # If it's a folder and recursive is True, search inside it
                    if recursive and item['mimeType'] == 'application/vnd.google-apps.folder':
                        yield from self.list_files(
                            drive_name=drive_name,
                            folder_id=item['id'],
                            recursive=True,
                            page_size=page_size,
                            progress_callback=progress_callback
                        )
                    elif gdrive_file.is_supported_document:
                        yield gdrive_file
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
                    
        except Exception as e:
            console.log(f"[red]Error listing files from '{drive_name}': {e}")
    
    def download_file_content(
        self,
        drive_name: str,
        file: GDriveFile,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[bytes]:
        """
        Download file content from Google Drive.
        
        Args:
            drive_name: Name of the authenticated drive
            file: GDriveFile object
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
            
        Returns:
            File content as bytes, or None if download failed
        """
        if drive_name not in self.services:
            console.log(f"[red]Drive '{drive_name}' not authenticated")
            return None
        
        service = self.services[drive_name]
        
        try:
            # Handle Google Docs exports
            if file.mime_type == 'application/vnd.google-apps.document':
                request = service.files().export_media(
                    fileId=file.id,
                    mimeType='application/pdf'
                )
            elif file.mime_type == 'application/vnd.google-apps.presentation':
                request = service.files().export_media(
                    fileId=file.id,
                    mimeType='application/pdf'
                )
            elif file.mime_type == 'application/vnd.google-apps.spreadsheet':
                request = service.files().export_media(
                    fileId=file.id,
                    mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            else:
                request = service.files().get_media(fileId=file.id)
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status and progress_callback:
                    progress_callback(
                        int(status.resumable_progress),
                        int(status.total_size) if status.total_size else file.size
                    )
            
            return fh.getvalue()
            
        except Exception as e:
            console.log(f"[red]Error downloading '{file.name}' from '{drive_name}': {e}")
            return None
    
    def search_files(
        self,
        drive_name: str,
        query: str,
        max_results: int = 100
    ) -> List[GDriveFile]:
        """
        Search for files using Google Drive's search query.
        
        Args:
            drive_name: Name of the authenticated drive
            query: Search query (e.g., "name contains 'syllabus'")
            max_results: Maximum number of results to return
            
        Returns:
            List of matching GDriveFile objects
        """
        if drive_name not in self.services:
            console.log(f"[red]Drive '{drive_name}' not authenticated")
            return []
        
        service = self.services[drive_name]
        results = []
        
        try:
            response = service.files().list(
                q=f"{query} and trashed = false",
                pageSize=max_results,
                fields="files(id, name, mimeType, size, modifiedTime, webViewLink)"
            ).execute()
            
            items = response.get('files', [])
            
            for item in items:
                gdrive_file = GDriveFile(
                    id=item['id'],
                    name=item['name'],
                    mime_type=item['mimeType'],
                    size=int(item.get('size', 0)),
                    modified_time=item['modifiedTime'],
                    web_view_link=item.get('webViewLink', ''),
                    drive_name=drive_name
                )
                
                if gdrive_file.is_supported_document:
                    results.append(gdrive_file)
            
        except Exception as e:
            console.log(f"[red]Error searching files in '{drive_name}': {e}")
        
        return results
