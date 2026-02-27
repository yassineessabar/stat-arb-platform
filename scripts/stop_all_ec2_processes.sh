#!/bin/bash

# ============================================================================
# EC2 Process Termination Script
# Stops all running strategy executors and related background processes
# ============================================================================

echo "======================================"
echo "EC2 PROCESS TERMINATION SCRIPT"
echo "======================================"
echo "Started at: $(date)"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter for terminated processes
TERMINATED_COUNT=0

echo -e "${YELLOW}🔍 Searching for running processes...${NC}"
echo "--------------------------------------"

# 1. Kill all Python strategy executors
echo -e "${YELLOW}Checking for strategy executor processes...${NC}"
EXECUTOR_PIDS=$(pgrep -f "strategy_executor.py|enhanced_executor.py|simple_working_executor.py|backtest_v6.py")
if [ ! -z "$EXECUTOR_PIDS" ]; then
    echo -e "${RED}Found strategy executor processes:${NC}"
    ps aux | grep -E "strategy_executor|enhanced_executor|simple_working_executor|backtest_v6" | grep -v grep

    for PID in $EXECUTOR_PIDS; do
        echo -e "${RED}  Killing PID $PID...${NC}"
        kill -9 $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✅ Successfully killed PID $PID${NC}"
            ((TERMINATED_COUNT++))
        fi
    done
else
    echo -e "${GREEN}  ✅ No strategy executor processes found${NC}"
fi

echo ""

# 2. Kill all stat-arb-platform related Python processes
echo -e "${YELLOW}Checking for stat-arb-platform Python processes...${NC}"
PLATFORM_PIDS=$(pgrep -f "python.*stat-arb-platform")
if [ ! -z "$PLATFORM_PIDS" ]; then
    echo -e "${RED}Found stat-arb-platform processes:${NC}"
    ps aux | grep "python.*stat-arb-platform" | grep -v grep

    for PID in $PLATFORM_PIDS; do
        echo -e "${RED}  Killing PID $PID...${NC}"
        kill -9 $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✅ Successfully killed PID $PID${NC}"
            ((TERMINATED_COUNT++))
        fi
    done
else
    echo -e "${GREEN}  ✅ No stat-arb-platform processes found${NC}"
fi

echo ""

# 3. Kill any Python processes running trading scripts
echo -e "${YELLOW}Checking for trading-related Python scripts...${NC}"
TRADING_KEYWORDS="binance|trading|executor|backtest|strategy|position|order"
TRADING_PIDS=$(ps aux | grep -E "python.*($TRADING_KEYWORDS)" | grep -v grep | awk '{print $2}')
if [ ! -z "$TRADING_PIDS" ]; then
    echo -e "${RED}Found trading-related processes:${NC}"
    ps aux | grep -E "python.*($TRADING_KEYWORDS)" | grep -v grep

    for PID in $TRADING_PIDS; do
        echo -e "${RED}  Killing PID $PID...${NC}"
        kill -9 $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✅ Successfully killed PID $PID${NC}"
            ((TERMINATED_COUNT++))
        fi
    done
else
    echo -e "${GREEN}  ✅ No trading-related processes found${NC}"
fi

echo ""

# 4. Kill any screen sessions running strategies
echo -e "${YELLOW}Checking for screen sessions...${NC}"
SCREEN_SESSIONS=$(screen -ls | grep -E "strategy|executor|trading" | awk '{print $1}')
if [ ! -z "$SCREEN_SESSIONS" ]; then
    echo -e "${RED}Found screen sessions:${NC}"
    screen -ls | grep -E "strategy|executor|trading"

    for SESSION in $SCREEN_SESSIONS; do
        echo -e "${RED}  Terminating screen session $SESSION...${NC}"
        screen -S $SESSION -X quit 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✅ Successfully terminated $SESSION${NC}"
            ((TERMINATED_COUNT++))
        fi
    done
else
    echo -e "${GREEN}  ✅ No strategy screen sessions found${NC}"
fi

echo ""

# 5. Kill any tmux sessions running strategies
echo -e "${YELLOW}Checking for tmux sessions...${NC}"
TMUX_SESSIONS=$(tmux ls 2>/dev/null | grep -E "strategy|executor|trading" | cut -d: -f1)
if [ ! -z "$TMUX_SESSIONS" ]; then
    echo -e "${RED}Found tmux sessions:${NC}"
    tmux ls 2>/dev/null | grep -E "strategy|executor|trading"

    for SESSION in $TMUX_SESSIONS; do
        echo -e "${RED}  Killing tmux session $SESSION...${NC}"
        tmux kill-session -t $SESSION 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✅ Successfully killed $SESSION${NC}"
            ((TERMINATED_COUNT++))
        fi
    done
else
    echo -e "${GREEN}  ✅ No strategy tmux sessions found${NC}"
fi

echo ""

# 6. Clean up any nohup processes
echo -e "${YELLOW}Checking for nohup processes...${NC}"
NOHUP_PIDS=$(ps aux | grep "nohup python" | grep -v grep | awk '{print $2}')
if [ ! -z "$NOHUP_PIDS" ]; then
    echo -e "${RED}Found nohup processes:${NC}"
    ps aux | grep "nohup python" | grep -v grep

    for PID in $NOHUP_PIDS; do
        echo -e "${RED}  Killing PID $PID...${NC}"
        kill -9 $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✅ Successfully killed PID $PID${NC}"
            ((TERMINATED_COUNT++))
        fi
    done
else
    echo -e "${GREEN}  ✅ No nohup processes found${NC}"
fi

echo ""

# 7. Clean up log files (optional)
echo -e "${YELLOW}Cleaning up log files...${NC}"
if [ -d "/home/ubuntu/stat-arb-platform/logs" ]; then
    LOG_SIZE=$(du -sh /home/ubuntu/stat-arb-platform/logs 2>/dev/null | cut -f1)
    echo "  Current log directory size: $LOG_SIZE"

    # Archive old logs
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    if [ "$(ls -A /home/ubuntu/stat-arb-platform/logs 2>/dev/null)" ]; then
        mkdir -p /home/ubuntu/stat-arb-platform/logs_archive
        tar -czf /home/ubuntu/stat-arb-platform/logs_archive/logs_$TIMESTAMP.tar.gz -C /home/ubuntu/stat-arb-platform/logs . 2>/dev/null

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✅ Logs archived to logs_archive/logs_$TIMESTAMP.tar.gz${NC}"

            # Clear active logs
            rm -f /home/ubuntu/stat-arb-platform/logs/*.log 2>/dev/null
            echo -e "${GREEN}  ✅ Active log files cleared${NC}"
        fi
    else
        echo -e "${GREEN}  ✅ No log files to clean${NC}"
    fi
else
    echo -e "${GREEN}  ✅ No log directory found${NC}"
fi

echo ""
echo "======================================"
echo -e "${GREEN}TERMINATION COMPLETE${NC}"
echo "======================================"
echo "Total processes terminated: $TERMINATED_COUNT"
echo "Completed at: $(date)"
echo ""

# Final verification
echo -e "${YELLOW}Final verification of running processes:${NC}"
REMAINING=$(ps aux | grep -E "python.*(strategy|executor|trading|binance)" | grep -v grep | wc -l)
if [ $REMAINING -eq 0 ]; then
    echo -e "${GREEN}✅ SUCCESS: No trading processes are running${NC}"
    exit 0
else
    echo -e "${RED}⚠️  WARNING: $REMAINING processes may still be running:${NC}"
    ps aux | grep -E "python.*(strategy|executor|trading|binance)" | grep -v grep
    echo ""
    echo -e "${YELLOW}Run 'ps aux | grep python' to verify manually${NC}"
    exit 1
fi