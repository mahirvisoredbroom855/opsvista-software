# Google Drive Integration Service
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from typing import List, Dict, Optional, BinaryIO
import io
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class GoogleDriveService:
    """Service for interacting with Google Drive API"""
    
    def __init__(self, credentials_path: str = None):
        self.credentials_path = credentials_path or os.getenv('GOOGLE_CREDENTIALS_PATH', './google_credentials.json')
        self.scopes = ['https://www.googleapis.com/auth/drive.readonly']
        self.service = None
        self._connect()
    
    def _connect(self):
        """Authenticate and create Drive service"""
        try:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(f"Google credentials not found: {self.credentials_path}")
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.scopes
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("✅ Connected to Google Drive API")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Google Drive: {str(e)}")
            raise
    
    def test_connection(self) -> Dict[str, any]:
        """Test Google Drive connection"""
        try:
            # Try to list files (limit 1 to test connection)
            results = self.service.files().list(pageSize=1).execute()
            
            return {
                'connected': True,
                'test_time': datetime.now().isoformat(),
                'message': 'Google Drive connection successful'
            }
            
        except Exception as e:
            return {
                'connected': False,
                'test_time': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def find_finance_folder(self, folder_name: str = "Md. Mizanur Rahman (PTIL)") -> Optional[str]:
        """Find the finance folder in Google Drive"""
        try:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, parents)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                folder_id = folders[0]['id']
                logger.info(f"✅ Found finance folder: {folder_name} (ID: {folder_id})")
                return folder_id
            else:
                logger.warning(f"❌ Finance folder '{folder_name}' not found")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error finding finance folder: {str(e)}")
            return None
    
    def list_excel_files(self, folder_id: str = None) -> List[Dict[str, any]]:
        """List all Excel files in the finance folder"""
        try:
            # Build query for Excel files
            mime_types = [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
                "application/vnd.ms-excel"  # .xls
            ]
            
            query_parts = []
            
            # Filter by folder if specified
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")
            
            # Filter by Excel MIME types
            mime_query = " or ".join([f"mimeType='{mt}'" for mt in mime_types])
            query_parts.append(f"({mime_query})")
            
            # Exclude trashed files
            query_parts.append("trashed=false")
            
            query = " and ".join(query_parts)
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, modifiedTime, size, parents, mimeType)",
                orderBy="modifiedTime desc"
            ).execute()
            
            files = results.get('files', [])
            
            logger.info(f"✅ Found {len(files)} Excel files")
            
            # Process file information
            processed_files = []
            for file in files:
                processed_files.append({
                    'id': file['id'],
                    'name': file['name'],
                    'modified_time': file['modifiedTime'],
                    'size': int(file.get('size', 0)),
                    'mime_type': file['mimeType'],
                    'is_excel': True
                })
            
            return processed_files
            
        except Exception as e:
            logger.error(f"❌ Error listing Excel files: {str(e)}")
            return []
    
    def download_file(self, file_id: str) -> bytes:
        """Download file content as bytes"""
        try:
            request = self.service.files().get_media(fileId=file_id)
            
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(f"Download progress: {int(status.progress() * 100)}%")
            
            file_content = file_io.getvalue()
            logger.info(f"✅ Downloaded file: {len(file_content)} bytes")
            
            return file_content
            
        except Exception as e:
            logger.error(f"❌ Error downloading file {file_id}: {str(e)}")
            return b''
    
    def get_file_info(self, file_id: str) -> Optional[Dict[str, any]]:
        """Get detailed file information"""
        try:
            file_info = self.service.files().get(
                fileId=file_id,
                fields="id, name, modifiedTime, size, mimeType, parents"
            ).execute()
            
            return {
                'id': file_info['id'],
                'name': file_info['name'],
                'modified_time': file_info['modifiedTime'],
                'size': int(file_info.get('size', 0)),
                'mime_type': file_info['mimeType']
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting file info {file_id}: {str(e)}")
            return None
    
    def find_files_modified_since(self, since_time: datetime, folder_id: str = None) -> List[Dict[str, any]]:
        """Find Excel files modified since specified time"""
        try:
            # Format time for Google Drive API
            time_filter = since_time.strftime('%Y-%m-%dT%H:%M:%S')
            
            query_parts = [
                f"modifiedTime > '{time_filter}'",
                "trashed=false"
            ]
            
            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")
            
            # Excel file types
            mime_types = [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel"
            ]
            mime_query = " or ".join([f"mimeType='{mt}'" for mt in mime_types])
            query_parts.append(f"({mime_query})")
            
            query = " and ".join(query_parts)
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, modifiedTime, size)",
                orderBy="modifiedTime desc"
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"✅ Found {len(files)} files modified since {since_time}")
            
            return files
            
        except Exception as e:
            logger.error(f"❌ Error finding modified files: {str(e)}")
            return []
    
    def get_quota_info(self) -> Dict[str, any]:
        """Get Google Drive quota information"""
        try:
            about = self.service.about().get(fields="storageQuota").execute()
            quota = about.get('storageQuota', {})
            
            return {
                'limit': int(quota.get('limit', 0)),
                'usage': int(quota.get('usage', 0)),
                'usage_in_drive': int(quota.get('usageInDrive', 0)),
                'usage_in_drive_trash': int(quota.get('usageInDriveTrash', 0))
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting quota info: {str(e)}")
            return {}

    def list_target_finance_files(self, folder_id: str = None) -> List[Dict[str, any]]:
        """List only the 3 specific target finance files"""
        
        # Define the exact files we want to process
        TARGET_FILES = [
            "1.Cash Book_2025.xlsx",
            "Cash Party Due Bill_2024-2025.xlsx", 
            "PTIL Expenditure LC & Other 2019-2020-2021-22-23-24.xlsx"
        ]
        
        try:
            # Get all Excel files first
            all_files = self.list_excel_files(folder_id)
            
            # Filter to only target files
            target_files = []
            
            for file in all_files:
                file_name = file['name']
                
                # Check if this file matches any of our target files
                for target in TARGET_FILES:
                    if self._is_target_file_match(file_name, target):
                        target_files.append(file)
                        logger.info(f"✅ Target file found: {file_name}")
                        break
                else:
                    # This runs if no break occurred (file not in targets)
                    logger.info(f"🔍 Skipping non-target file: {file_name}")
            
            logger.info(f"📊 Filtered to {len(target_files)} target files out of {len(all_files)} total files")
            return target_files
            
        except Exception as e:
            logger.error(f"❌ Error listing target files: {str(e)}")
            return []
    
    def _is_target_file_match(self, file_name: str, target_name: str) -> bool:
        """Check if a file name matches our target file"""
        
        # Exact match
        if file_name == target_name:
            return True
        
        # Check if target name is contained in file name (handles slight variations)
        if target_name in file_name:
            return True
        
        # Check key identifying parts
        if "Cash Book" in target_name and "Cash Book" in file_name and "2025" in file_name:
            return True
        elif "Party Due Bill" in target_name and "Party Due Bill" in file_name:
            return True
        elif "PTIL Expenditure" in target_name and "PTIL Expenditure" in file_name:
            return True
        
        return False
    
    def find_modified_target_files_since(self, since_time: datetime, folder_id: str = None) -> List[Dict[str, any]]:
        """Find target files modified since specified time"""
        try:
            # Get all target files
            target_files = self.list_target_finance_files(folder_id)
            
            # Filter by modification time
            modified_files = []
            for file in target_files:
                file_modified = datetime.fromisoformat(file['modified_time'].replace('Z', '+00:00'))
                
                if file_modified > since_time:
                    modified_files.append(file)
                    logger.info(f"📅 Modified target file: {file['name']} (modified: {file_modified})")
            
            logger.info(f"🔄 Found {len(modified_files)} modified target files since {since_time}")
            return modified_files
            
        except Exception as e:
            logger.error(f"❌ Error finding modified target files: {str(e)}")
            return []

    def list_target_finance_files_recursive(self, folder_id: str = None) -> List[Dict[str, any]]:
        """Recursively search for target finance files in all subfolders"""
        
        # Define the exact files we want to process
        TARGET_FILES = [
            "1.Cash Book_2025.xlsx",
            "Cash Party Due Bill_2024-2025.xlsx", 
            "PTIL Expenditure LC & Other 2019-2020-2021-22-23-24.xlsx"
        ]
        
        try:
            logger.info(f"🔍 Starting recursive search for target files...")
            
            all_target_files = []
            folders_to_search = [folder_id] if folder_id else []
            
            # Get all folders to search (including subfolders)
            if folder_id:
                folders_to_search.extend(self._get_all_subfolders(folder_id))
            else:
                # If no folder specified, search entire Drive
                folders_to_search = [None]
            
            logger.info(f"📁 Will search in {len(folders_to_search)} folders")
            
            # Search each folder for our target files
            for search_folder_id in folders_to_search:
                folder_files = self._search_folder_for_targets(search_folder_id, TARGET_FILES)
                all_target_files.extend(folder_files)
            
            # Remove duplicates (same file ID)
            unique_files = []
            seen_ids = set()
            
            for file in all_target_files:
                if file['id'] not in seen_ids:
                    unique_files.append(file)
                    seen_ids.add(file['id'])
                    logger.info(f"✅ Found target file: {file['name']} (in folder: {file.get('parent_folder', 'unknown')})")
            
            logger.info(f"📊 Recursive search complete: {len(unique_files)} target files found")
            return unique_files
            
        except Exception as e:
            logger.error(f"❌ Recursive search failed: {str(e)}")
            return []
    
    def _get_all_subfolders(self, parent_folder_id: str) -> List[str]:
        """Get all subfolders recursively"""
        subfolders = []
        
        try:
            # Query for folders inside the parent folder
            query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, parents)",
                pageSize=100
            ).execute()
            
            folders = results.get('files', [])
            
            for folder in folders:
                folder_id = folder['id']
                subfolders.append(folder_id)
                logger.info(f"📂 Found subfolder: {folder['name']} (ID: {folder_id})")
                
                # Recursively get subfolders of this folder
                nested_subfolders = self._get_all_subfolders(folder_id)
                subfolders.extend(nested_subfolders)
            
            return subfolders
            
        except Exception as e:
            logger.error(f"❌ Error getting subfolders: {str(e)}")
            return []
    
    def _search_folder_for_targets(self, folder_id: str, target_files: List[str]) -> List[Dict[str, any]]:
        """Search specific folder for target files"""
        found_files = []
        
        try:
            # Get Excel files in this folder
            if folder_id:
                excel_files = self.list_excel_files(folder_id)
            else:
                excel_files = self.list_excel_files()
            
            # Filter to target files
            for file in excel_files:
                file_name = file['name']
                
                for target in target_files:
                    if self._is_target_file_match(file_name, target):
                        # Add folder info to the file
                        file['parent_folder'] = folder_id
                        found_files.append(file)
                        break
            
            return found_files
            
        except Exception as e:
            logger.error(f"❌ Error searching folder {folder_id}: {str(e)}")
            return []
    
    def find_target_files_anywhere(self, base_folder_name: str = "Md. Mizanur Rahman (PTIL)") -> List[Dict[str, any]]:
        """Find target files anywhere in the specified base folder and its subfolders"""
        try:
            logger.info(f"🔍 Searching for target files in '{base_folder_name}' and all subfolders...")
            
            # Find the base folder
            base_folder_id = self.find_finance_folder(base_folder_name)
            
            if not base_folder_id:
                logger.error(f"❌ Base folder '{base_folder_name}' not found")
                return []
            
            # Search recursively
            target_files = self.list_target_finance_files_recursive(base_folder_id)
            
            logger.info(f"🎯 Found {len(target_files)} target files across all folders")
            return target_files
            
        except Exception as e:
            logger.error(f"❌ Error in find_target_files_anywhere: {str(e)}")
            return []
