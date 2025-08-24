"""
Updated Google Drive Scanner for RAG

- Uses folder-person mapping to infer department/role
- Prioritizes filename keyword matching for classification
- Prepares for content-based embedding classification
- Flags unclassified documents
"""

import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from ..models.schemas import (
    FileType,
    DocumentCategory,
    AnalysisStatus,
)


class GoogleDriveScanner:
    def __init__(self, credentials_path: str, database_client=None):
        self.credentials_path = credentials_path
        self.db_client = database_client
        self.drive_service = None
        self.logger = logging.getLogger(__name__)

        self.folder_role_map = {
            "Riaz Uddin Sarker": "Admin",
            "Md. Mizanur Rahman (PTIL)": "Commercial Manager",
            "Khorshed Alam Babu": "Maintenance Manager",
            "Md. Mozammel Haque": "Manager",
            "Zahedul Islam Nizam": "Accounting Assistant",
            "Md. Alamin": "Assistant Commercial Manager",
        }

        self.folder_department_map = {
            "Riaz Uddin Sarker": "Admin",
            "Md. Mizanur Rahman (PTIL)": "Finance",
            "Khorshed Alam Babu": "Maintenance",
            "Md. Mozammel Haque": "HR",
            "Zahedul Islam Nizam": "Accounting",
            "Md. Alamin": "Commercial",
        }

        self.category_keywords = {
            DocumentCategory.FINANCE: ["payment", "budget", "transaction", "bank", "balance"],
            DocumentCategory.LC: ["lc", "letter of credit", "shipment", "export", "import"],
            DocumentCategory.HR: ["employee", "salary", "attendance", "hr", "leave"],
            DocumentCategory.INVOICE: ["invoice", "receipt", "bill", "voucher"],
            DocumentCategory.INVENTORY: ["stock", "warehouse", "inventory", "store"],
        }

        self.mime_to_filetype = {
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': FileType.EXCEL,
            'application/vnd.ms-excel': FileType.EXCEL,
            'application/pdf': FileType.PDF,
            'text/csv': FileType.CSV,
            'application/msword': FileType.DOC,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': FileType.DOCX,
        }

    async def authenticate(self) -> bool:
        try:
            scopes = ['https://www.googleapis.com/auth/drive.readonly']
            credentials = Credentials.from_service_account_file(
                self.credentials_path, scopes=scopes
            )
            self.drive_service = build('drive', 'v3', credentials=credentials)
            about = self.drive_service.about().get(fields='user').execute()
            self.logger.info(f"Authenticated as: {about.get('user', {}).get('emailAddress')}")
            return True
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            return False

    def classify_by_filename(self, filename: str) -> DocumentCategory:
        name_lower = filename.lower()
        for category, keywords in self.category_keywords.items():
            if any(kw in name_lower for kw in keywords):
                return category
        return DocumentCategory.UNKNOWN

    def infer_department(self, folder_name: str) -> Optional[str]:
        return self.folder_department_map.get(folder_name)

    def classify_document(self, filename: str, folder_name: str, content_text: Optional[str] = None) -> DocumentCategory:
        category = self.classify_by_filename(filename)
        if category != DocumentCategory.UNKNOWN:
            return category

        if content_text:
            content_lower = content_text.lower()
            for cat, keywords in self.category_keywords.items():
                if any(kw in content_lower for kw in keywords):
                    return cat

        if "lc" in folder_name.lower():
            return DocumentCategory.LC
        if "invoice" in folder_name.lower():
            return DocumentCategory.INVOICE

        return DocumentCategory.UNKNOWN

    async def process_file(self, file_metadata: Dict, folder_name: str) -> Dict:
        file_name = file_metadata['name']
        file_size = int(file_metadata.get('size', 0)) if 'size' in file_metadata else None
        google_drive_id = file_metadata['id']
        mime_type = file_metadata.get('mimeType', '')
        modified_time = file_metadata.get('modifiedTime')
        file_type = self.mime_to_filetype.get(mime_type, FileType.UNKNOWN)

        last_modified = None
        if modified_time:
            last_modified = datetime.fromisoformat(modified_time.replace('Z', '+00:00'))

        file_hash = file_metadata.get('md5Checksum')
        if not file_hash:
            raw = f"{file_name}_{file_size}_{google_drive_id}"
            file_hash = hashlib.md5(raw.encode()).hexdigest()

        department = self.infer_department(folder_name)
        category = self.classify_document(file_name, folder_name)

        return {
            'file_path': f"{folder_name}/{file_name}",
            'file_name': file_name,
            'file_type': file_type,
            'file_size': file_size,
            'google_drive_id': google_drive_id,
            'file_hash': file_hash,
            'document_category': category,
            'department': department,
            'analysis_status': AnalysisStatus.PENDING,
            'last_modified': last_modified,
            'priority_level': self._calculate_priority(category, file_type),
        }

    def _calculate_priority(self, category: DocumentCategory, file_type: FileType) -> int:
        category_priority = {
            DocumentCategory.LC: 1,
            DocumentCategory.FINANCE: 2,
            DocumentCategory.INVOICE: 3,
            DocumentCategory.HR: 4,
            DocumentCategory.INVENTORY: 5,
            DocumentCategory.REPORTS: 6,
            DocumentCategory.UNKNOWN: 8,
        }
        base = category_priority.get(category, 8)
        if file_type == FileType.EXCEL:
            return max(1, base - 1)
        return base


async def test_scanner_setup(credentials_path: str, db_client=None) -> Dict:
    scanner = GoogleDriveScanner(credentials_path, db_client)
    results = {
        'authentication': False,
        'errors': [],
        'folder_owner_roles': scanner.folder_role_map,
        'department_map': scanner.folder_department_map,
    }
    
    try:
        auth_success = await scanner.authenticate()
        results['authentication'] = auth_success

        if not auth_success:
            results['errors'].append("Google Drive authentication failed")
            return results

        # Optional: You can check folder access, listing or file metadata here if needed

        if db_client:
            try:
                db_client.table('rag_system.document_inventory_rag').select('id').limit(1).execute()
                results['database_connection'] = True
            except Exception as e:
                results['database_connection'] = False
                results['errors'].append(f"Database connection failed: {str(e)}")

    except Exception as e:
        results['errors'].append(f"Test setup failed: {str(e)}")

    return results
