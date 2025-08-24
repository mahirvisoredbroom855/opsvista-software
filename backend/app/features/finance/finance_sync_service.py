# Finance Sync Service - Only monitors target files
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any

from .google_drive_service import GoogleDriveService
from .excel_processor import ExcelProcessor
from .models import FinanceFileProcessing
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class FinanceSyncService:
    """Service that monitors and processes only target finance files"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.drive_service = GoogleDriveService()
        self.excel_processor = ExcelProcessor(db_session)
        
        # Our 3 target files
        self.TARGET_FILES = [
            "1.Cash Book_2025.xlsx",
            "Cash Party Due Bill_2024-2025.xlsx", 
            "PTIL Expenditure LC & Other 2019-2020-2021-22-23-24.xlsx"
        ]
    
    def sync_target_files(self) -> Dict[str, Any]:
        """Sync only the 3 target finance files"""
        logger.info("🔄 Starting sync of target finance files...")
        
        sync_results = {
            'files_checked': 0,
            'files_processed': 0,
            'files_skipped': 0,
            'errors': []
        }
        
        try:
            # Find PTIL folder
            folder_id = self.drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
            
            if not folder_id:
                error_msg = "PTIL folder not found"
                logger.error(f"❌ {error_msg}")
                sync_results['errors'].append(error_msg)
                return sync_results
            
            # Get only target files
            target_files = self.drive_service.list_target_finance_files(folder_id)
            sync_results['files_checked'] = len(target_files)
            
            logger.info(f"📊 Found {len(target_files)} target files to check")
            
            # Process each target file
            for file in target_files:
                try:
                    should_process = self._should_process_file(file)
                    
                    if should_process:
                        logger.info(f"⚙️ Processing: {file['name']}")
                        self._process_single_file(file)
                        sync_results['files_processed'] += 1
                    else:
                        logger.info(f"⏭️ Skipping (already processed): {file['name']}")
                        sync_results['files_skipped'] += 1
                        
                except Exception as e:
                    error_msg = f"Failed to process {file['name']}: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    sync_results['errors'].append(error_msg)
            
            logger.info(f"✅ Sync completed: {sync_results['files_processed']} processed, {sync_results['files_skipped']} skipped")
            return sync_results
            
        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            sync_results['errors'].append(error_msg)
            return sync_results
    
    def _should_process_file(self, file: Dict[str, Any]) -> bool:
        """Check if file needs processing based on modification time"""
        
        file_name = file['name']
        file_modified = datetime.fromisoformat(file['modified_time'].replace('Z', '+00:00'))
        
        # Check if we've processed this file version before
        existing_processing = self.db.query(FinanceFileProcessing).filter(
            FinanceFileProcessing.source_file == file_name,
            FinanceFileProcessing.status == 'completed'
        ).order_by(FinanceFileProcessing.processing_completed.desc()).first()
        
        if not existing_processing:
            logger.info(f"🆕 New file: {file_name}")
            return True
        
        # Compare modification times
        last_processed = existing_processing.processing_completed
        
        if file_modified > last_processed:
            logger.info(f"🔄 File modified since last processing: {file_name}")
            logger.info(f"   File modified: {file_modified}")
            logger.info(f"   Last processed: {last_processed}")
            return True
        
        return False
    
    def _process_single_file(self, file: Dict[str, Any]):
        """Process a single target file"""
        
        file_name = file['name']
        file_id = file['id']
        
        # Create processing record
        processing_record = FinanceFileProcessing(
            source_file=file_name,
            file_type=self._detect_file_type_from_name(file_name),
            status='processing',
            processing_started=datetime.now()
        )
        
        self.db.add(processing_record)
        self.db.commit()
        self.db.refresh(processing_record)
        
        try:
            # Download file
            logger.info(f"📥 Downloading: {file_name}")
            file_content = self.drive_service.download_file(file_id)
            
            if not file_content:
                raise Exception("Downloaded file is empty")
            
            # Process file
            logger.info(f"⚙️ Processing: {file_name}")
            result = self.excel_processor.process_file(file_content, file_name, processing_record.id)
            
            if result['status'] == 'success':
                # Update processing record
                processing_record.status = 'completed'
                processing_record.processing_completed = datetime.now()
                processing_record.rows_processed = result['stats']['rows_processed']
                processing_record.rows_successful = result['stats']['rows_successful']
                processing_record.rows_failed = result['stats']['rows_failed']
                
                logger.info(f"✅ Successfully processed: {file_name}")
                logger.info(f"   Rows processed: {result['stats']['rows_processed']}")
                logger.info(f"   Successful: {result['stats']['rows_successful']}")
                
            else:
                # Mark as failed
                processing_record.status = 'failed'
                processing_record.error_details = {'error': result.get('error')}
                
                logger.error(f"❌ Processing failed: {file_name}")
                logger.error(f"   Error: {result.get('error')}")
            
            self.db.commit()
            
        except Exception as e:
            # Mark as failed
            processing_record.status = 'failed' 
            processing_record.error_details = {'error': str(e)}
            self.db.commit()
            
            logger.error(f"❌ Exception processing {file_name}: {str(e)}")
            raise
    
    def _detect_file_type_from_name(self, file_name: str) -> str:
        """Detect file type from name"""
        if "Cash Book" in file_name:
            return "cash_book"
        elif "Party Due Bill" in file_name:
            return "party_due_bill"
        elif "Expenditure" in file_name:
            return "expenditure_summary"
        else:
            return "unknown"
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status for target files"""
        
        status = {
            'target_files': self.TARGET_FILES,
            'last_sync_times': {},
            'processing_status': {}
        }
        
        for target_file in self.TARGET_FILES:
            # Get last processing record
            last_processing = self.db.query(FinanceFileProcessing).filter(
                FinanceFileProcessing.source_file.contains(target_file.split('.')[0])  # Match base name
            ).order_by(FinanceFileProcessing.created_at.desc()).first()
            
            if last_processing:
                status['last_sync_times'][target_file] = last_processing.processing_completed
                status['processing_status'][target_file] = last_processing.status
            else:
                status['last_sync_times'][target_file] = None
                status['processing_status'][target_file] = 'never_processed'
        
        return status
