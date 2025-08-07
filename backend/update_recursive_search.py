import os

def update_google_drive_for_recursive_search():
    """Add recursive search capability to GoogleDriveService"""
    
    # Add the new recursive search method
    recursive_method = '''
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
            return []'''
    
    # Read the current google_drive_service.py
    service_file = "app/features/finance/google_drive_service.py"
    
    if not os.path.exists(service_file):
        print("❌ google_drive_service.py not found!")
        return False
    
    with open(service_file, 'r') as f:
        content = f.read()
    
    # Add the recursive methods before the last EOF
    if 'list_target_finance_files_recursive' not in content:
        # Find the end of the class (before the last line)
        lines = content.split('\n')
        
        # Insert the new methods before the end
        lines.insert(-1, recursive_method)
        
        updated_content = '\n'.join(lines)
        
        # Write back
        with open(service_file, 'w') as f:
            f.write(updated_content)
        
        print("✅ Added recursive search methods to GoogleDriveService")
    else:
        print("✅ Recursive search methods already exist")
    
    return True

if __name__ == "__main__":
    update_google_drive_for_recursive_search()
