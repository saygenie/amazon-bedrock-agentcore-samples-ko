#!/bin/bash

# AgentCore Memory Dashboard Backend 시작
echo "🚀 Starting AgentCore Memory Dashboard Backend..."

# 올바른 디렉터리인지 확인
if [ ! -f "backend/app.py" ]; then
    echo "❌ Error: backend/app.py not found. Please run this script from the agentcore-memory-dashboard directory."
    exit 1
fi

# 가상 환경이 없으면 생성
if [ ! -d "backend/venv" ]; then
    echo "📦 Creating Python virtual environment..."
    cd backend
    python3 -m venv venv
    cd ..
fi

# 가상 환경 활성화
echo "🔧 Activating virtual environment..."
source backend/venv/bin/activate

# 종속성 설치
echo "📦 Installing Python dependencies..."
cd backend
pip install -r requirements.txt

# bedrock-agentcore 사용 가능 여부 확인
echo "🔍 Checking AgentCore Memory SDK..."
python -c "
try:
    from bedrock_agentcore.memory import MemoryClient
    print('✅ bedrock-agentcore SDK is available')
except ImportError:
    print('⚠️  bedrock-agentcore SDK not found')
    print('   The backend will use mock data for development')
    print('   To install: pip install bedrock-agentcore')
"

# 백엔드 서버 시작
echo "🚀 Starting FastAPI backend server..."
echo "📍 Backend will be available at: http://localhost:8000"
echo "📖 API documentation at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
