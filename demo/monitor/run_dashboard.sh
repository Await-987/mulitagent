#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========== AIOS Workforce Visualization ==========${NC}"
echo ""
echo -e "${GREEN}[1/2] Starting API Server...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "$SCRIPT_DIR/event_api.py" &
API_PID=$!
sleep 2

echo ""
echo -e "${GREEN}[2/2] Starting Workforce Task...${NC}"
python "$SCRIPT_DIR/demo_test.py" &
TASK_PID=$!

echo ""
echo -e "${BLUE}========== Services Running ==========${NC}"
echo -e "${GREEN}✓ API Server: http://127.0.0.1:5000${NC}"
echo -e "${GREEN}✓ Task Process: PID $TASK_PID${NC}"
echo ""
echo "Press Ctrl+C to stop all services..."
echo ""

# Wait for both processes
wait $API_PID $TASK_PID
