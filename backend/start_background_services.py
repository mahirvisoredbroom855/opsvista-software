#!/usr/bin/env python3
# Start All Background Services
import os
import subprocess
import sys
import signal
import time
from multiprocessing import Process

def start_redis():
    """Start Redis server"""
    print("🔴 Starting Redis server...")
    try:
        # Try to start Redis (different commands for different systems)
        redis_commands = [
            ["redis-server"],
            ["redis-server", "/usr/local/etc/redis.conf"],
            ["sudo", "systemctl", "start", "redis"],
        ]
        
        for cmd in redis_commands:
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                print("✅ Redis started successfully")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        print("⚠️ Could not start Redis automatically")
        print("   Please start Redis manually: redis-server")
        return False
        
    except Exception as e:
        print(f"❌ Error starting Redis: {str(e)}")
        return False

def start_celery_worker():
    """Start Celery worker"""
    print("⚙️ Starting Celery worker...")
    
    cmd = [
        "celery", "-A", "app.core.celery_app", "worker",
        "--loglevel=info",
        "--queues=finance",
        "--concurrency=2",
        "--hostname=worker@%h"
    ]
    
    return subprocess.Popen(cmd)

def start_celery_beat():
    """Start Celery beat scheduler"""
    print("⏰ Starting Celery beat scheduler...")
    
    cmd = [
        "celery", "-A", "app.core.celery_app", "beat",
        "--loglevel=info",
        "--schedule=/tmp/celerybeat-schedule"
    ]
    
    return subprocess.Popen(cmd)

def start_fastapi():
    """Start FastAPI server"""
    print("🚀 Starting FastAPI server...")
    
    cmd = [
        "uvicorn", "app.main:socketio_app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    
    return subprocess.Popen(cmd)

def main():
    print("🚀 OpsVista Finance - Background Services Startup")
    print("=" * 60)
    
    processes = []
    
    try:
        # Start Redis
        if not start_redis():
            print("❌ Redis is required for background tasks")
            sys.exit(1)
        
        time.sleep(2)  # Wait for Redis to be ready
        
        # Start Celery worker
        worker_process = start_celery_worker()
        processes.append(("Celery Worker", worker_process))
        
        time.sleep(3)  # Wait for worker to be ready
        
        # Start Celery beat
        beat_process = start_celery_beat()
        processes.append(("Celery Beat", beat_process))
        
        time.sleep(2)  # Wait for beat to be ready
        
        # Start FastAPI
        api_process = start_fastapi()
        processes.append(("FastAPI Server", api_process))
        
        print("\n✅ All services started successfully!")
        print("\n📊 Service Status:")
        print("   🔴 Redis: Running")
        print("   ⚙️ Celery Worker: Running (Queue: finance)")
        print("   ⏰ Celery Beat: Running (Schedule: every 3 minutes)")
        print("   🚀 FastAPI Server: Running (http://localhost:8000)")
        print("\n🎯 System Features:")
        print("   • Automatic Google Drive monitoring")
        print("   • Background Excel processing")
        print("   • Real-time WebSocket updates")
        print("   • Scheduled cleanup tasks")
        
        print("\n📋 Useful Commands:")
        print("   • View API docs: http://localhost:8000/docs")
        print("   • Task status: http://localhost:8000/api/v1/system/tasks/status")
        print("   • Manual sync: POST http://localhost:8000/api/v1/system/tasks/trigger-sync")
        
        print("\n⚠️ Press Ctrl+C to stop all services")
        
        # Wait for interruption
        while True:
            time.sleep(1)
            
            # Check if any process died
            for name, process in processes:
                if process.poll() is not None:
                    print(f"❌ {name} stopped unexpectedly")
    
    except KeyboardInterrupt:
        print("\n🛑 Shutting down all services...")
        
        for name, process in processes:
            print(f"   Stopping {name}...")
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"   Force killing {name}...")
                process.kill()
        
        print("✅ All services stopped")

if __name__ == "__main__":
    main()
