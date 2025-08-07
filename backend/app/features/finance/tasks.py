# Finance Background Tasks
from celery import shared_task
from datetime import datetime, timedelta
import logging
from typing import Dict, Any

from app.core.celery_app import celery_app
from .google_drive_service import GoogleDriveService
from .excel_processor import ExcelProcessor
from .models import FinanceFileProcessing, FactFinance
from app.core.supabase_client import get_supabase_session

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def scheduled_finance_sync(self):
    """Scheduled task: Check Google Drive every 3 minutes for file changes"""
    try:
        logger.info("🔄 Starting scheduled finance sync...")
        
        # Get database session
        db = get_supabase_session()
        
        try:
            # Initialize services
            drive_service = GoogleDriveService()
            
            # Find finance folder
            folder_id = drive_service.find_finance_folder("Md. Mizanur Rahman (PTIL)")
            
            if not folder_id:
                logger.error("❌ PTIL folder not found during scheduled sync")
                return {"status": "error", "message": "PTIL folder not found"}
            
            # Get target files
            target_files = drive_service.list_target_finance_files(folder_id)
            
            if not target_files:
                logger.info("ℹ️ No target files found during sync")
                return {"status": "success", "files_processed": 0}
            
            logger.info(f"📊 Found {len(target_files)} target files to check")
            
            sync_results = {
                "files_checked": len(target_files),
                "files_queued": 0,
                "files_skipped": 0,
                "errors": []
            }
            
            # Check each file for modifications
            for file_info in target_files:
                try:
                    should_process = check_if_file_needs_processing(db, file_info)
                    
                    if should_process:
                        # Queue file for processing
                        process_finance_file.delay(
                            file_info['id'], 
                            file_info['name'], 
                            file_info['modified_time']
                        )
                        sync_results["files_queued"] += 1
                        logger.info(f"📥 Queued file for processing: {file_info['name']}")
                    else:
                        sync_results["files_skipped"] += 1
                        logger.debug(f"⏭️ Skipped (no changes): {file_info['name']}")
                        
                except Exception as e:
                    error_msg = f"Error checking {file_info['name']}: {str(e)}"
                    sync_results["errors"].append(error_msg)
                    logger.error(f"❌ {error_msg}")
            
            logger.info(f"✅ Sync completed: {sync_results['files_queued']} queued, {sync_results['files_skipped']} skipped")
            return {"status": "success", **sync_results}
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Scheduled sync failed: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            delay = 2 ** self.request.retries * 60  # 1, 2, 4 minutes
            logger.info(f"🔄 Retrying in {delay} seconds (attempt {self.request.retries + 1})")
            raise self.retry(countdown=delay)
        
        return {"status": "error", "message": str(e)}

@shared_task(bind=True, max_retries=3)
def process_finance_file(self, file_id: str, file_name: str, modified_time: str):
    """Background task: Process individual Excel file"""
    try:
        logger.info(f"⚙️ Processing file: {file_name}")
        
        # Get database session
        db = get_supabase_session()
        
        try:
            # Create processing record
            processing_record = FinanceFileProcessing(
                source_file=file_name,
                file_type=detect_file_type_from_name(file_name),
                status='processing',
                processing_started=datetime.now()
            )
            
            db.add(processing_record)
            db.commit()
            db.refresh(processing_record)
            
            # Initialize services
            drive_service = GoogleDriveService()
            excel_processor = ExcelProcessor(db)
            
            # Download file
            logger.info(f"📥 Downloading: {file_name}")
            file_content = drive_service.download_file(file_id)
            
            if not file_content:
                raise Exception("Downloaded file is empty")
            
            logger.info(f"✅ Downloaded: {len(file_content):,} bytes")
            
            # Process file
            logger.info(f"⚙️ Processing Excel data...")
            result = excel_processor.process_file(file_content, file_name, processing_record.id)
            
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
                
                # Notify about successful processing
                notify_processing_complete.delay(file_name, result['stats'])
                
            else:
                # Mark as failed
                processing_record.status = 'failed'
                processing_record.error_details = {'error': result.get('error')}
                
                logger.error(f"❌ Processing failed: {file_name}")
                logger.error(f"   Error: {result.get('error')}")
                
                # Notify about failure
                notify_processing_failed.delay(file_name, result.get('error'))
            
            db.commit()
            
            return {
                "status": processing_record.status,
                "file_name": file_name,
                "stats": result.get('stats', {})
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ File processing failed for {file_name}: {str(e)}")
        
        # Update processing record to failed
        try:
            db = get_supabase_session()
            processing_record = db.query(FinanceFileProcessing).filter(
                FinanceFileProcessing.source_file == file_name,
                FinanceFileProcessing.status == 'processing'
            ).first()
            
            if processing_record:
                processing_record.status = 'failed'
                processing_record.error_details = {'error': str(e)}
                db.commit()
            
            db.close()
        except:
            pass
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            delay = 2 ** self.request.retries * 300  # 5, 10, 20 minutes
            logger.info(f"🔄 Retrying file processing in {delay} seconds")
            raise self.retry(countdown=delay)
        
        return {"status": "error", "file_name": file_name, "error": str(e)}

@shared_task
def notify_processing_complete(file_name: str, stats: Dict[str, Any]):
    """Notify about successful file processing"""
    try:
        logger.info(f"📢 File processing completed: {file_name}")
        
        # TODO: Send WebSocket notification to connected clients
        # TODO: Send email notification if configured
        # TODO: Update dashboard metrics cache
        
        return {"status": "notified", "file_name": file_name}
        
    except Exception as e:
        logger.error(f"❌ Notification failed for {file_name}: {str(e)}")
        return {"status": "error", "error": str(e)}

@shared_task
def notify_processing_failed(file_name: str, error: str):
    """Notify about failed file processing"""
    try:
        logger.error(f"📢 File processing failed: {file_name} - {error}")
        
        # TODO: Send error notification
        # TODO: Create alert in monitoring system
        
        return {"status": "notified", "file_name": file_name}
        
    except Exception as e:
        logger.error(f"❌ Error notification failed for {file_name}: {str(e)}")
        return {"status": "error", "error": str(e)}

@shared_task
def cleanup_old_records():
    """Daily cleanup task: Remove old processing records"""
    try:
        logger.info("🧹 Starting cleanup of old processing records...")
        
        db = get_supabase_session()
        
        try:
            # Remove records older than 30 days
            cutoff_date = datetime.now() - timedelta(days=30)
            
            old_records = db.query(FinanceFileProcessing).filter(
                FinanceFileProcessing.created_at < cutoff_date
            ).all()
            
            for record in old_records:
                db.delete(record)
            
            db.commit()
            
            logger.info(f"✅ Cleaned up {len(old_records)} old processing records")
            return {"status": "success", "cleaned_records": len(old_records)}
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {str(e)}")
        return {"status": "error", "error": str(e)}

# Helper functions
def check_if_file_needs_processing(db, file_info: Dict[str, Any]) -> bool:
    """Check if file needs processing based on modification time"""
    
    file_name = file_info['name']
    file_modified = datetime.fromisoformat(file_info['modified_time'].replace('Z', '+00:00'))
    
    # Check if we've processed this file version before
    existing_processing = db.query(FinanceFileProcessing).filter(
        FinanceFileProcessing.source_file == file_name,
        FinanceFileProcessing.status == 'completed'
    ).order_by(FinanceFileProcessing.processing_completed.desc()).first()
    
    if not existing_processing:
        logger.info(f"🆕 New file detected: {file_name}")
        return True
    
    # Compare modification times
    last_processed = existing_processing.processing_completed
    
    if file_modified > last_processed:
        logger.info(f"🔄 File modified since last processing: {file_name}")
        logger.info(f"   File modified: {file_modified}")
        logger.info(f"   Last processed: {last_processed}")
        return True
    
    return False

def detect_file_type_from_name(file_name: str) -> str:
    """Detect file type from name"""
    if "Cash Book" in file_name:
        return "cash_book"
    elif "Party Due Bill" in file_name or "Due Bill" in file_name:
        return "party_due_bill"
    elif "Expenditure" in file_name or "PTIL Expenditure" in file_name:
        return "expenditure_summary"
    else:
        return "unknown"
