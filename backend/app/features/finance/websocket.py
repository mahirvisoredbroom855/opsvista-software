# WebSocket Service for Real-time Updates
import socketio
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Create Socket.IO server
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True
)

# Connected clients tracking
connected_clients = set()

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    connected_clients.add(sid)
    logger.info(f"🔌 Client connected: {sid} (Total: {len(connected_clients)})")
    
    # Send initial status
    await sio.emit('connection_status', {
        'status': 'connected',
        'client_id': sid,
        'server_time': datetime.now().isoformat()
    }, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    connected_clients.discard(sid)
    logger.info(f"🔌 Client disconnected: {sid} (Total: {len(connected_clients)})")

@sio.event
async def subscribe_to_finance_updates(sid, data):
    """Subscribe client to finance updates"""
    await sio.enter_room(sid, 'finance_updates')
    logger.info(f"�� Client {sid} subscribed to finance updates")
    
    await sio.emit('subscription_confirmed', {
        'room': 'finance_updates',
        'status': 'subscribed'
    }, room=sid)

@sio.event
async def request_dashboard_refresh(sid, data):
    """Client requests dashboard data refresh"""
    logger.info(f"🔄 Dashboard refresh requested by {sid}")
    
    # TODO: Get latest dashboard metrics
    # TODO: Send updated metrics to client
    
    await sio.emit('dashboard_refreshed', {
        'status': 'success',
        'timestamp': datetime.now().isoformat()
    }, room=sid)

# Broadcasting functions (called from background tasks)
async def broadcast_file_processing_started(file_name: str):
    """Broadcast when file processing starts"""
    if not connected_clients:
        return
    
    message = {
        'event': 'file_processing_started',
        'file_name': file_name,
        'timestamp': datetime.now().isoformat()
    }
    
    await sio.emit('file_processing_update', message, room='finance_updates')
    logger.info(f"📡 Broadcasted: File processing started - {file_name}")

async def broadcast_file_processing_completed(file_name: str, stats: Dict[str, Any]):
    """Broadcast when file processing completes"""
    if not connected_clients:
        return
    
    message = {
        'event': 'file_processing_completed',
        'file_name': file_name,
        'stats': stats,
        'timestamp': datetime.now().isoformat()
    }
    
    await sio.emit('file_processing_update', message, room='finance_updates')
    await sio.emit('dashboard_data_changed', {
        'reason': 'file_processed',
        'file_name': file_name
    }, room='finance_updates')
    
    logger.info(f"📡 Broadcasted: File processing completed - {file_name}")

async def broadcast_dashboard_metrics_updated(metrics: Dict[str, Any]):
    """Broadcast updated dashboard metrics"""
    if not connected_clients:
        return
    
    message = {
        'event': 'dashboard_metrics_updated',
        'metrics': metrics,
        'timestamp': datetime.now().isoformat()
    }
    
    await sio.emit('dashboard_update', message, room='finance_updates')
    logger.info(f"📡 Broadcasted: Dashboard metrics updated")

async def broadcast_error(error_type: str, message: str, details: Dict[str, Any] = None):
    """Broadcast error to all clients"""
    if not connected_clients:
        return
    
    error_message = {
        'event': 'error',
        'error_type': error_type,
        'message': message,
        'details': details or {},
        'timestamp': datetime.now().isoformat()
    }
    
    await sio.emit('error_notification', error_message, room='finance_updates')
    logger.error(f"📡 Broadcasted error: {error_type} - {message}")

# Create FastAPI app with Socket.IO
from fastapi import FastAPI
import socketio

def create_socketio_app(fastapi_app: FastAPI):
    """Integrate Socket.IO with FastAPI"""
    
    # Create ASGI app
    socketio_app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
    
    return socketio_app
