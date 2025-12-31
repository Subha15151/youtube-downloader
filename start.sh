#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

clear

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}     YOUTUBE DOWNLOADER v2.0${NC}"
echo -e "${YELLOW}         Created by SUBHA${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Python installation
echo -e "[1] ${BLUE}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "[${RED}ERROR${NC}] Python3 is not installed!"
    echo ""
    echo "Please install Python 3.8+:"
    echo "Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "Mac: brew install python"
    echo "Or download from: https://www.python.org/downloads/"
    exit 1
fi

python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "[${GREEN}OK${NC}] Python $python_version detected"

# Check/Install dependencies
echo -e "[2] ${BLUE}Checking/Installing dependencies...${NC}"
pip3 install --upgrade pip --quiet
pip3 install -r requirements.txt --quiet

# Create necessary folders
echo -e "[3] ${BLUE}Creating necessary folders...${NC}"
mkdir -p downloads
mkdir -p logs

# Check if port 5000 is available
echo -e "[4] ${BLUE}Checking port 5000...${NC}"
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "[${YELLOW}WARNING${NC}] Port 5000 is already in use!"
    read -p "Do you want to try a different port? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter port number (default: 5001): " PORT
        PORT=${PORT:-5001}
    else
        echo -e "[${RED}ERROR${NC}] Please free port 5000 or choose another port"
        exit 1
    fi
else
    PORT=5000
fi

# Start server
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}     Server is starting...${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Open your browser and go to:"
echo -e "${YELLOW}http://localhost:$PORT${NC}"
echo ""
echo -e "Press ${RED}Ctrl+C${NC} to stop the server"
echo ""

sleep 2

# Run the server
python3 server.py --port $PORT

# Check if server started successfully
if [ $? -ne 0 ]; then
    echo ""
    echo -e "[${RED}ERROR${NC}] Server failed to start!"
    echo "Possible reasons:"
    echo "1. Port $PORT is already in use"
    echo "2. Missing dependencies"
    echo "3. Python script error"
    echo ""
    echo "Check logs/youtube_downloader.log for details:"
    echo -e "${YELLOW}tail -f logs/youtube_downloader.log${NC}"
    exit 1
fi