from celery import Celery
import time

# Create Celery app
app = Celery('opsvista_test')
app.conf.broker_url = 'redis://localhost:6379/0'
app.conf.result_backend = 'redis://localhost:6379/0'

@app.task
def test_task(message):
    """Simple test task"""
    print(f"Processing: {message}")
    time.sleep(2)  # Simulate work
    return f"Completed: {message}"

@app.task
def add_numbers(x, y):
    """Simple math task"""
    result = x + y
    print(f"Calculating {x} + {y} = {result}")
    return result

if __name__ == "__main__":
    print("🔧 Celery Test Tasks Defined")
    print("To test, run in separate terminals:")
    print("1. celery -A test_celery worker --loglevel=info")
    print("2. python -c \"from test_celery import test_task; result = test_task.delay('Hello World'); print(result.get())\"")
