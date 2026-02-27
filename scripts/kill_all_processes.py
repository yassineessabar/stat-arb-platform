#!/usr/bin/env python3
"""
EC2 Process Termination Script
Stops all running strategy executors and related background processes
Can be called directly or imported as a module
"""

import os
import psutil
import signal
import subprocess
import time
from datetime import datetime
from typing import List, Dict, Tuple

# ANSI color codes for terminal output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color


def print_colored(message: str, color: str = NC):
    """Print colored message to terminal"""
    print(f"{color}{message}{NC}")


def find_processes_by_keywords(keywords: List[str]) -> List[Dict]:
    """Find processes matching any of the given keywords"""
    matching_processes = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            # Get process info
            cmdline = ' '.join(proc.info['cmdline'] or [])

            # Check if any keyword matches
            for keyword in keywords:
                if keyword.lower() in cmdline.lower():
                    matching_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': cmdline[:100],  # Truncate long commands
                        'create_time': datetime.fromtimestamp(proc.info['create_time'])
                    })
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return matching_processes


def kill_process(pid: int, force: bool = False) -> bool:
    """Kill a process by PID"""
    try:
        proc = psutil.Process(pid)

        # Try graceful termination first
        if not force:
            proc.terminate()
            time.sleep(0.5)

        # Force kill if still running
        if proc.is_running():
            proc.kill()

        # Wait for process to die
        proc.wait(timeout=3)
        return True
    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
        return True  # Process already dead or killed
    except psutil.AccessDenied:
        # Try using sudo kill as fallback
        try:
            subprocess.run(['sudo', 'kill', '-9', str(pid)], check=True, capture_output=True)
            return True
        except:
            return False


def kill_screen_sessions():
    """Kill all screen sessions related to trading"""
    try:
        result = subprocess.run(['screen', '-ls'], capture_output=True, text=True)
        sessions = []

        for line in result.stdout.split('\n'):
            if any(kw in line.lower() for kw in ['strategy', 'executor', 'trading']):
                # Extract session name
                session = line.split()[0] if line.strip() else None
                if session:
                    sessions.append(session)

        killed = 0
        for session in sessions:
            try:
                subprocess.run(['screen', '-S', session, '-X', 'quit'], check=True)
                killed += 1
            except:
                pass

        return killed
    except:
        return 0


def kill_tmux_sessions():
    """Kill all tmux sessions related to trading"""
    try:
        result = subprocess.run(['tmux', 'ls'], capture_output=True, text=True)
        sessions = []

        for line in result.stdout.split('\n'):
            if any(kw in line.lower() for kw in ['strategy', 'executor', 'trading']):
                # Extract session name
                session = line.split(':')[0] if ':' in line else None
                if session:
                    sessions.append(session)

        killed = 0
        for session in sessions:
            try:
                subprocess.run(['tmux', 'kill-session', '-t', session], check=True)
                killed += 1
            except:
                pass

        return killed
    except:
        return 0


def clean_log_files(log_dir: str = "/home/ubuntu/stat-arb-platform/logs") -> Tuple[bool, str]:
    """Archive and clean log files"""
    try:
        if not os.path.exists(log_dir):
            return True, "No log directory found"

        # Get current size
        total_size = sum(os.path.getsize(os.path.join(log_dir, f))
                        for f in os.listdir(log_dir)
                        if os.path.isfile(os.path.join(log_dir, f)))

        if total_size == 0:
            return True, "No log files to clean"

        # Create archive
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = os.path.join(os.path.dirname(log_dir), "logs_archive")
        os.makedirs(archive_dir, exist_ok=True)

        archive_path = os.path.join(archive_dir, f"logs_{timestamp}.tar.gz")
        subprocess.run(['tar', '-czf', archive_path, '-C', log_dir, '.'], check=True)

        # Clear logs
        for file in os.listdir(log_dir):
            if file.endswith('.log'):
                os.remove(os.path.join(log_dir, file))

        size_mb = total_size / (1024 * 1024)
        return True, f"Archived {size_mb:.2f}MB of logs to {archive_path}"
    except Exception as e:
        return False, str(e)


def main():
    """Main execution function"""
    print("=" * 50)
    print_colored("EC2 PROCESS TERMINATION SCRIPT", YELLOW)
    print("=" * 50)
    print(f"Started at: {datetime.now()}")
    print()

    terminated_count = 0
    errors = []

    # 1. Kill strategy executors
    print_colored("🔍 Searching for strategy executor processes...", YELLOW)
    executor_keywords = [
        'strategy_executor.py',
        'enhanced_executor.py',
        'simple_working_executor.py',
        'backtest_v6.py',
        'stat-arb-platform'
    ]

    executors = find_processes_by_keywords(executor_keywords)
    if executors:
        print_colored(f"Found {len(executors)} executor processes:", RED)
        for proc in executors:
            print(f"  PID {proc['pid']}: {proc['name']} - {proc['cmdline']}")

            if kill_process(proc['pid']):
                print_colored(f"  ✅ Successfully killed PID {proc['pid']}", GREEN)
                terminated_count += 1
            else:
                error = f"Failed to kill PID {proc['pid']}"
                print_colored(f"  ❌ {error}", RED)
                errors.append(error)
    else:
        print_colored("  ✅ No executor processes found", GREEN)

    print()

    # 2. Kill trading-related Python processes
    print_colored("🔍 Searching for trading-related processes...", YELLOW)
    trading_keywords = [
        'binance',
        'trading',
        'executor',
        'backtest',
        'strategy',
        'position',
        'order'
    ]

    trading_procs = find_processes_by_keywords(trading_keywords)
    # Filter to only Python processes
    trading_procs = [p for p in trading_procs if 'python' in p['name'].lower() or 'python' in p['cmdline'].lower()]

    if trading_procs:
        print_colored(f"Found {len(trading_procs)} trading processes:", RED)
        for proc in trading_procs:
            print(f"  PID {proc['pid']}: {proc['cmdline']}")

            if kill_process(proc['pid']):
                print_colored(f"  ✅ Successfully killed PID {proc['pid']}", GREEN)
                terminated_count += 1
            else:
                error = f"Failed to kill PID {proc['pid']}"
                print_colored(f"  ❌ {error}", RED)
                errors.append(error)
    else:
        print_colored("  ✅ No trading processes found", GREEN)

    print()

    # 3. Kill screen sessions
    print_colored("🔍 Checking for screen sessions...", YELLOW)
    screen_killed = kill_screen_sessions()
    if screen_killed > 0:
        print_colored(f"  ✅ Terminated {screen_killed} screen sessions", GREEN)
        terminated_count += screen_killed
    else:
        print_colored("  ✅ No screen sessions found", GREEN)

    print()

    # 4. Kill tmux sessions
    print_colored("🔍 Checking for tmux sessions...", YELLOW)
    tmux_killed = kill_tmux_sessions()
    if tmux_killed > 0:
        print_colored(f"  ✅ Terminated {tmux_killed} tmux sessions", GREEN)
        terminated_count += tmux_killed
    else:
        print_colored("  ✅ No tmux sessions found", GREEN)

    print()

    # 5. Clean log files
    print_colored("🔍 Cleaning up log files...", YELLOW)
    success, message = clean_log_files()
    if success:
        print_colored(f"  ✅ {message}", GREEN)
    else:
        print_colored(f"  ❌ {message}", RED)
        errors.append(f"Log cleanup: {message}")

    print()
    print("=" * 50)
    print_colored("TERMINATION COMPLETE", GREEN)
    print("=" * 50)
    print(f"Total processes terminated: {terminated_count}")

    if errors:
        print_colored(f"Errors encountered: {len(errors)}", RED)
        for error in errors:
            print(f"  - {error}")

    print(f"Completed at: {datetime.now()}")
    print()

    # Final verification
    print_colored("Final verification...", YELLOW)
    remaining = find_processes_by_keywords(['strategy', 'executor', 'trading', 'binance'])
    remaining = [p for p in remaining if 'python' in p['name'].lower() or 'python' in p['cmdline'].lower()]

    if not remaining:
        print_colored("✅ SUCCESS: No trading processes are running", GREEN)
        return 0
    else:
        print_colored(f"⚠️  WARNING: {len(remaining)} processes may still be running:", RED)
        for proc in remaining:
            print(f"  PID {proc['pid']}: {proc['cmdline']}")
        return 1


if __name__ == "__main__":
    exit(main())