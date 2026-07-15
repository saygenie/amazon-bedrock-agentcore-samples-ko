#!/usr/bin/env node

/**
 * React 앱에서 사용할 임시 AWS 자격 증명을 가져오는 도우미 스크립트
 * 이 스크립트는 AWS CLI 구성을 사용하여 브라우저 환경에서
 * 사용할 수 있는 임시 자격 증명을 가져옵니다.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

async function getTemporaryCredentials() {
  try {
    console.log('🔑 Setting up AWS configuration for the dashboard...');

    // 먼저 AWS에 액세스할 수 있는지 확인
    try {
      const identity = execSync('aws sts get-caller-identity --output json', { encoding: 'utf8' });
      const identityData = JSON.parse(identity);
      console.log(`✅ AWS Identity confirmed: ${identityData.Arn}`);
    } catch (error) {
      throw new Error('AWS CLI not configured or no valid credentials found');
    }

    // 현재 AWS 리전 가져오기
    let region = null;
    try {
      const configOutput = execSync('aws configure get region', { encoding: 'utf8' });
      region = configOutput.trim();
      if (!region) {
        throw new Error('No AWS region configured. Run: aws configure set region <your-region>');
      }
    } catch (error) {
      throw new Error('AWS region not configured. Run: aws configure set region <your-region>');
    }

    // 프런트엔드 구성용 환경 변수 내용 생성
    const envContent = `
# AgentCore Memory Dashboard - Frontend Configuration
# Generated on: ${new Date().toISOString()}
# 
# Note: This dashboard uses a backend proxy approach for AWS credentials
# since browser applications cannot directly use AWS CLI credentials for security reasons.

# Backend API URL
REACT_APP_BACKEND_URL=http://localhost:8000

# Dashboard Settings
REACT_APP_MAX_MEMORY_ENTRIES=50
REACT_APP_REFRESH_INTERVAL=5000
REACT_APP_DEBUG_MODE=true

# Note: Memory ID, Actor ID, and Session ID are entered by users through the UI
# No hardcoded values needed here
`.trim();

    // .env 파일에 쓰기
    const envPath = path.join(__dirname, '..', '.env');
    fs.writeFileSync(envPath, envContent);

    console.log('✅ Frontend configuration saved to .env file');
    console.log('🔧 Dashboard configured to use backend proxy for AWS credentials');
    console.log('🚀 You can now run: npm run dev');
    console.log('');
    console.log('📝 Note: Memory ID, Actor ID, and Session ID will be entered through the UI');
    console.log('   No hardcoded values are stored in configuration files.');

  } catch (error) {
    console.error('❌ Error setting up configuration:');
    console.error(error.message);
    console.error('\n💡 Troubleshooting:');
    console.error('1. Run: aws configure list');
    console.error('2. Run: aws sts get-caller-identity');
    console.error('3. Make sure you have AWS CLI installed and configured');
    console.error('4. Ensure your AWS credentials have Bedrock AgentCore permissions');
    process.exit(1);
  }
}

// 스크립트 실행
getTemporaryCredentials();
