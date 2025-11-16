from django.shortcuts import render
from django.http import JsonResponse
import psutil
import threading
import time
from collections import defaultdict
from datetime import datetime

# Global variables for simulator
leak_simulator_thread = None
leak_simulator_running = False
leak_simulator_data = []
leak_start_time = None

# Memory tracking for leak detection
process_memory_history = defaultdict(list)
MEMORY_HISTORY_SIZE = 15
MEMORY_LEAK_THRESHOLD = 1.4  # 40% increase over time


def index(request):
    """Render the leak simulator page"""
    return render(request, 'leak_simulator/index.html')


def memory_leak_simulator():
    """Simulates a memory leak by accumulating data"""
    global leak_simulator_data, leak_simulator_running
    
    iteration = 0
    while leak_simulator_running:
        # Simulate memory leak by appending data (1MB per second)
        leak_simulator_data.append('x' * 1024 * 1024)
        iteration += 1
        print(f"Leak Simulator: Iteration {iteration}, Memory allocated: {iteration} MB")
        time.sleep(1)
    
    print("Leak Simulator: Stopped")


def start_simulator(request):
    """Start the memory leak simulator"""
    global leak_simulator_thread, leak_simulator_running, leak_simulator_data, leak_start_time
    
    if leak_simulator_running:
        return JsonResponse({
            'status': 'already_running',
            'message': 'Simulator is already running'
        })
    
    leak_simulator_running = True
    leak_simulator_data = []
    leak_start_time = datetime.now()
    leak_simulator_thread = threading.Thread(target=memory_leak_simulator, daemon=True)
    leak_simulator_thread.start()
    
    current_process = psutil.Process()
    
    return JsonResponse({
        'status': 'started',
        'message': 'Memory leak simulator started successfully!',
        'pid': current_process.pid,
        'process_name': current_process.name(),
        'start_time': leak_start_time.strftime('%H:%M:%S')
    })


def stop_simulator(request):
    """Stop the memory leak simulator"""
    global leak_simulator_running, leak_simulator_data, leak_start_time
    
    if not leak_simulator_running:
        return JsonResponse({
            'status': 'not_running',
            'message': 'Simulator is not running'
        })
    
    leak_simulator_running = False
    allocated_mb = len(leak_simulator_data)
    leak_simulator_data = []  # Clear data to free memory
    
    duration = (datetime.now() - leak_start_time).total_seconds() if leak_start_time else 0
    
    return JsonResponse({
        'status': 'stopped',
        'message': 'Memory leak simulator stopped and memory cleared',
        'duration_seconds': round(duration, 2),
        'memory_allocated_mb': allocated_mb
    })


def get_status(request):
    """Get current simulator status"""
    global leak_simulator_running, leak_simulator_data, leak_start_time
    
    status_data = {
        'running': leak_simulator_running,
        'memory_allocated_mb': len(leak_simulator_data),
    }
    
    if leak_simulator_running and leak_start_time:
        duration = (datetime.now() - leak_start_time).total_seconds()
        status_data['duration_seconds'] = round(duration, 2)
        status_data['start_time'] = leak_start_time.strftime('%H:%M:%S')
    
    return JsonResponse(status_data)


def detect_memory_leak(pid, current_memory):
    """Detect if a process has a memory leak"""
    history = process_memory_history[pid]
    history.append({
        'memory': current_memory,
        'timestamp': time.time()
    })
    
    # Keep only recent history
    if len(history) > MEMORY_HISTORY_SIZE:
        history.pop(0)
    
    # Need at least 8 data points to detect leak
    if len(history) < 8:
        return False, 0
    
    # Calculate memory increase rate
    first_half = [h['memory'] for h in history[:len(history)//2]]
    second_half = [h['memory'] for h in history[len(history)//2:]]
    
    first_half_avg = sum(first_half) / len(first_half)
    second_half_avg = sum(second_half) / len(second_half)
    
    if first_half_avg > 0:
        increase_ratio = second_half_avg / first_half_avg
        increase_percent = (increase_ratio - 1) * 100
        
        if increase_ratio > MEMORY_LEAK_THRESHOLD:
            return True, round(increase_percent, 1)
    
    return False, 0


def get_leak_processes(request):
    """Get all processes and detect memory leaks"""
    processes = []
    leak_count = 0
    
    try:
        current_pid = psutil.Process().pid
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'num_threads', 'create_time']):
            try:
                pinfo = proc.info
                memory_info = proc.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                
                # Detect memory leak
                has_leak, increase_percent = detect_memory_leak(pinfo['pid'], memory_mb)
                
                if has_leak:
                    leak_count += 1
                
                is_simulator = (pinfo['pid'] == current_pid and leak_simulator_running)
                
                process_data = {
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'cpu_percent': round(pinfo['cpu_percent'], 2),
                    'memory_percent': round(pinfo['memory_percent'], 2),
                    'memory_mb': round(memory_mb, 2),
                    'status': pinfo['status'],
                    'num_threads': pinfo['num_threads'],
                    'has_leak': has_leak,
                    'increase_percent': increase_percent,
                    'is_simulator': is_simulator
                }
                
                processes.append(process_data)
                
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    # Sort: simulator first, then by memory usage
    processes.sort(key=lambda x: (not x['is_simulator'], -x['memory_mb']))
    
    # System info
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    return JsonResponse({
        'processes': processes[:100],
        'leak_count': leak_count,
        'system': {
            'cpu_percent': round(cpu_percent, 2),
            'memory_percent': round(memory.percent, 2),
            'memory_used_gb': round(memory.used / (1024**3), 2),
            'memory_total_gb': round(memory.total / (1024**3), 2),
            'memory_available_gb': round(memory.available / (1024**3), 2)
        },
        'simulator_running': leak_simulator_running
    })