#!/usr/bin/env bash
# =====================================================================
# Context Distiller 2.0 — Linux Service Management Script
# =====================================================================
set -e

# --- Configuration ---
BACKEND_PORT=8085
FRONTEND_PORT=5188
BACKEND_LOG="backend.log"
FRONTEND_LOG="frontend.log"
BACKEND_PID_FILE="backend.pid"
FRONTEND_PID_FILE="frontend.pid"

# --- Colors ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $*"; }
task() { echo -e "${BLUE}[TASK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure we're in a virtual environment if starting
check_venv() {
    if [ -d ".venv" ]; then
        . .venv/bin/activate
    else
        warn ".venv not found. Please run ./deploy.sh first or install dependencies manually."
    fi
}

# Helper function to find process ID by port
get_pid_by_port() {
    local port=$1
    if command -v lsof > /dev/null; then
        lsof -ti:$port 2>/dev/null || echo ""
    elif command -v fuser > /dev/null; then
        fuser -n tcp $port 2>/dev/null | awk '{print $1}' || echo ""
    else
        echo ""
    fi
}

start_service() {
    info "Starting Context Distiller services..."
    check_venv
    
    # Check if backend is already running
    local b_pid=$(get_pid_by_port $BACKEND_PORT)
    if [ -n "$b_pid" ]; then
        warn "Backend is already running on port $BACKEND_PORT (PID: $b_pid)"
    else
        task "Starting Backend Server on port $BACKEND_PORT..."
        nohup uvicorn context_distiller.api.server.app:app --host 0.0.0.0 --port $BACKEND_PORT > "$BACKEND_LOG" 2>&1 &
        local new_b_pid=$!
        echo $new_b_pid > "$BACKEND_PID_FILE"
        info "Backend started with PID: $new_b_pid (Log: $BACKEND_LOG)"
    fi

    # Check if frontend is already running
    local f_pid=$(get_pid_by_port $FRONTEND_PORT)
    if [ -n "$f_pid" ]; then
        warn "Frontend is already running on port $FRONTEND_PORT (PID: $f_pid)"
    else
        task "Starting Frontend UI (Vite) on port $FRONTEND_PORT..."
        cd context_distiller_ui
        # Permission Fix: Ensure vite is executable
        [ -f "node_modules/.bin/vite" ] && chmod +x "node_modules/.bin/vite"
        nohup npm run dev -- --host 0.0.0.0 --port $FRONTEND_PORT > "../$FRONTEND_LOG" 2>&1 &
        local new_f_pid=$!
        cd ..
        echo $new_f_pid > "$FRONTEND_PID_FILE"
        info "Frontend started with PID: $new_f_pid (Log: $FRONTEND_LOG)"
    fi
    
    echo "===================================================="
    info "Context Distiller is up and running!"
    echo -e "  Backend:  http://localhost:$BACKEND_PORT"
    echo -e "  Frontend: http://localhost:$FRONTEND_PORT"
    echo "===================================================="
}

stop_service() {
    info "Stopping Context Distiller services..."
    
    # Stop Backend
    local b_pid=$(get_pid_by_port $BACKEND_PORT)
    if [ -f "$BACKEND_PID_FILE" ] && [ -z "$b_pid" ]; then
        b_pid=$(cat "$BACKEND_PID_FILE")
    fi
    
    if [ -n "$b_pid" ]; then
        task "Stopping Backend processes..."
        kill -9 $b_pid 2>/dev/null || true
        # Also ensure port is freed
        local port_pid=$(get_pid_by_port $BACKEND_PORT)
        if [ -n "$port_pid" ]; then
            kill -9 $port_pid 2>/dev/null || true
        fi
        rm -f "$BACKEND_PID_FILE"
        info "Backend stopped."
    else
        warn "Backend is not currently running."
        rm -f "$BACKEND_PID_FILE"
    fi

    # Stop Frontend
    local f_pid=$(get_pid_by_port $FRONTEND_PORT)
    if [ -f "$FRONTEND_PID_FILE" ] && [ -z "$f_pid" ]; then
        f_pid=$(cat "$FRONTEND_PID_FILE")
    fi

    if [ -n "$f_pid" ]; then
        task "Stopping Frontend processes..."
        # Kill the node processes spawned by npm
        pkill -P $f_pid 2>/dev/null || true
        kill -9 $f_pid 2>/dev/null || true
        
        # Ensure port is freed
        local f_port_pid=$(get_pid_by_port $FRONTEND_PORT)
        if [ -n "$f_port_pid" ]; then
            kill -9 $f_port_pid 2>/dev/null || true
        fi
        rm -f "$FRONTEND_PID_FILE"
        info "Frontend stopped."
    else
        warn "Frontend is not currently running."
        rm -f "$FRONTEND_PID_FILE"
    fi
}

status_service() {
    echo "===================================================="
    info "Context Distiller Service Status"
    echo "===================================================="
    
    local b_pid=$(get_pid_by_port $BACKEND_PORT)
    if [ -n "$b_pid" ]; then
        echo -e "[ ${GREEN}RUNNING${NC} ] Backend Server  (Port: $BACKEND_PORT, PID: $b_pid)"
    else
        echo -e "[ ${RED}STOPPED${NC} ] Backend Server  (Port: $BACKEND_PORT)"
    fi

    local f_pid=$(get_pid_by_port $FRONTEND_PORT)
    if [ -n "$f_pid" ]; then
        echo -e "[ ${GREEN}RUNNING${NC} ] Frontend UI     (Port: $FRONTEND_PORT, PID: $f_pid)"
    else
        echo -e "[ ${RED}STOPPED${NC} ] Frontend UI     (Port: $FRONTEND_PORT)"
    fi
    echo "===================================================="
}

print_help() {
    echo -e "${BLUE}Usage:${NC} $0 {start|stop|restart|status}"
    echo ""
    echo "Commands:"
    echo "  start    Start the backend and frontend services in the background"
    echo "  stop     Stop all running services and forcefully free the ports"
    echo "  restart  Stop all services, then start them again"
    echo "  status   Show the current running status of the services"
    echo ""
}

case "${1:-}" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        stop_service
        sleep 2
        start_service
        ;;
    status)
        status_service
        ;;
    *)
        print_help
        exit 1
        ;;
esac
