from django.shortcuts import render
from django.http import JsonResponse
import psutil
import time
from collections import defaultdict

# Store process memory history for leak detection
process_memory_history = defaultdict(list)
MEMORY_HISTORY_SIZE = 10
MEMORY_LEAK_THRESHOLD = 1.5  # 50% increase over time

def index(request):
    return render(request, 'monitor/index.html')

def detect_memory_leak(pid, current_memory):
    """Detect if a process has a memory leak"""
    history = process_memory_history[pid]
    history.append(current_memory)
    
    # Keep only recent history
    if len(history) > MEMORY_HISTORY_SIZE:
        history.pop(0)
    
    # Need at least 5 data points to detect leak
    if len(history) < 5:
        return False
    
    # Check if memory is consistently increasing
    first_half_avg = sum(history[:len(history)//2]) / (len(history)//2)
    second_half_avg = sum(history[len(history)//2:]) / (len(history) - len(history)//2)
    
    if first_half_avg > 0 and second_half_avg / first_half_avg > MEMORY_LEAK_THRESHOLD:
        return True
    
    return False

def get_processes(request):
    """Get all running processes with memory leak detection"""
    processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'num_threads']):
            try:
                pinfo = proc.info
                memory_mb = proc.memory_info().rss / (1024 * 1024)  # Convert to MB
                
                # Detect memory leak
                has_leak = detect_memory_leak(pinfo['pid'], memory_mb)
                
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'cpu_percent': round(pinfo['cpu_percent'], 2),
                    'memory_percent': round(pinfo['memory_percent'], 2),
                    'memory_mb': round(memory_mb, 2),
                    'status': pinfo['status'],
                    'num_threads': pinfo['num_threads'],
                    'has_leak': has_leak
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    # Sort by CPU usage
    processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
    
    # Get system info
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    return JsonResponse({
        'processes': processes[:50],  # Return top 50 processes
        'system': {
            'cpu_percent': round(cpu_percent, 2),
            'memory_percent': round(memory.percent, 2),
            'memory_used_gb': round(memory.used / (1024**3), 2),
            'memory_total_gb': round(memory.total / (1024**3), 2)
        }
    })