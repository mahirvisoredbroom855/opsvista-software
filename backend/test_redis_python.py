import redis
import json

def test_redis_integration():
    print("🔴 Testing Redis + Python Integration")
    print("=" * 50)
    
    try:
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Test 1: Basic connection
        pong = r.ping()
        print(f"1️⃣ Redis ping: {'✅ PONG' if pong else '❌ Failed'}")
        
        # Test 2: Set and get string
        r.set('test_key', 'Hello OpsVista!')
        value = r.get('test_key')
        print(f"2️⃣ String operations: {'✅ Success' if value == 'Hello OpsVista!' else '❌ Failed'}")
        
        # Test 3: List operations (for task queues)
        r.delete('task_queue')  # Clear any existing data
        r.lpush('task_queue', 'task1', 'task2', 'task3')
        queue_length = r.llen('task_queue')
        print(f"3️⃣ Queue operations: {'✅ Success' if queue_length == 3 else '❌ Failed'} (Length: {queue_length})")
        
        # Test 4: JSON data (for complex tasks)
        task_data = {
            'id': 'file_123',
            'type': 'process_excel',
            'priority': 'high',
            'data': {'filename': 'cash_book.xlsx', 'size': 1024}
        }
        
        r.set('complex_task', json.dumps(task_data))
        retrieved = json.loads(r.get('complex_task'))
        print(f"4️⃣ JSON operations: {'✅ Success' if retrieved['id'] == 'file_123' else '❌ Failed'}")
        
        # Test 5: Simulate task processing
        # Producer adds task
        r.lpush('work_queue', json.dumps({'task': 'process_file', 'file_id': '456'}))
        
        # Consumer gets task
        task_json = r.rpop('work_queue')
        if task_json:
            task = json.loads(task_json)
            print(f"5️⃣ Task simulation: {'✅ Success' if task['task'] == 'process_file' else '❌ Failed'}")
        else:
            print("5️⃣ Task simulation: ❌ Failed - No task retrieved")
        
        # Cleanup
        r.delete('test_key', 'task_queue', 'complex_task', 'work_queue')
        
        print("\n🎉 Redis integration test completed successfully!")
        return True
        
    except redis.ConnectionError:
        print("❌ Cannot connect to Redis. Make sure Redis is running on port 6379")
        return False
    except Exception as e:
        print(f"❌ Error during Redis test: {str(e)}")
        return False

if __name__ == "__main__":
    # Install redis package if needed
    try:
        import redis
    except ImportError:
        print("Installing redis package...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'redis'])
        import redis
    
    test_redis_integration()
