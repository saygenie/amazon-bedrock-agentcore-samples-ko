# AgentCore CLI와 AgentCore Harness를 사용해 VPC 리소스를 에이전트에 연결하기

이 예제에서는 AgentCore CLI를 사용하여 VPC 구성이 적용된 AgentCore Harness를 생성합니다.

## 사전 요구 사항

시작하려면 다음 항목이 필요합니다.

- Node.js 20.x 이상
- Python 에이전트용 uv([설치](https://docs.astral.sh/uv/getting-started/installation/))

그런 다음 **AgentCore CLI를 설치**합니다.

```Bash
npm i -g @aws/agentcore@preview

# 확인
agentcore --version
```

프라이빗 서브넷, VPC 엔드포인트 등의 네트워크 구성을 준비하세요. 자세한 내용은 [AgentCore 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc.html)를 참조하세요.

## Bedrock 모델 공급자로 에이전트 생성 및 호출

이 단계별 튜토리얼에서는 AgentCore CLI 대화형 모드로 VPC 지원 구성을 안내합니다. 다음 명령을 사용해 직접 생성할 수도 있습니다.

프로젝트를 생성합니다.

```bash
agentcore create --name HarnessBedrockVPC --memory "none" --model-provider bedrock --network-mode VPC --subnets <ids> --security-groups <ids>

```

### 대화형 모드 시작

#### AgentCore Harness 구성

다음 명령을 실행합니다.

```bash
agentcore
```
<p align="left">
    <img src="images/agentcore-cli-start.png" alt="AgentCore CLI 시작 화면" width="700" />
</p> 

프로젝트 이름을 지정하고 계속 진행합니다(Return/Enter).

<p align="left">
    <img src="images/project_name.png" alt="프로젝트 이름 입력 화면" width="700" />
</p> 

생성 모드로 기본값인 "Harness"를 선택하고 계속 진행합니다.

<p align="left">
    <img src="images/harness_mode.png" alt="Harness 생성 모드 선택 화면" width="700" />
</p> 

AgentCore Harness 이름을 지정하고 계속 진행합니다(Return/Enter).

<p align="left">
    <img src="images/harness_name.png" alt="AgentCore Harness 이름 입력 화면" width="700" />
</p> 

모델 공급자로 "Bedrock"을 선택합니다.

<p align="left">
    <img src="images/model_provider.png" alt="Bedrock 모델 공급자 선택 화면" width="700" />
</p> 

컨테이너를 사용자 지정하지 않을 것이므로 "None"을 유지합니다.

<p align="left">
    <img src="images/container.png" alt="컨테이너 구성 선택 화면" width="700" />
</p> 

Memory 구성을 추가하지 않습니다.

<p align="left">
    <img src="images/memory.png" alt="Memory 구성 선택 화면" width="700" />
</p> 

VPC 구성을 추가하려면 Space 키로 "Network" 옵션을 선택하고 계속 진행합니다.

<p align="left">
    <img src="images/network.png" alt="Network 옵션 선택 화면" width="700" />
</p> 

"VPC" 모드를 선택합니다.

<p align="left">
    <img src="images/vpc.png" alt="VPC 모드 선택 화면" width="700" />
</p> 

서브넷을 쉼표로 구분하여 입력하고 계속 진행합니다. 사용 가능한 AZ에 대한 자세한 내용은 [문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-vpc.html#agentcore-supported-azs)를 참조하세요.

<p align="left">
    <img src="images/subnets.png" alt="서브넷 입력 화면" width="700" />
</p> 

보안 그룹을 추가합니다. 여러 보안 그룹을 추가하려면 쉼표로 구분하세요.

<p align="left">
    <img src="images/sg.png" alt="보안 그룹 입력 화면" width="700" />
</p>

마지막으로 AgentCore Harness 구성 요약을 확인합니다. 구성이 올바르면 계속 진행합니다(Return/Enter).

<p align="left">
    <img src="images/summary.png" alt="AgentCore Harness 구성 요약 화면" width="700" />
</p>

CLI가 프로젝트를 생성하고, 생성이 완료되면 대화형 모드가 종료됩니다.

<p align="left">
    <img src="images/ok.png" alt="프로젝트 생성 완료 화면" width="700" />
</p>

<p align="left">
    <img src="images/ok_2.png" alt="대화형 모드 종료 화면" width="700" />
</p>

다음 명령을 실행하여 구성 파일을 확인할 수 있습니다.

```bash

cat HarnessBedrockVPC/app/HarnessBedrockVPC/harness.json
```

#### AgentCore Harness 배포

**새로 생성된 폴더로 이동한 후 다음 명령을 실행하여 AgentCore Harness 에이전트를 배포합니다.**

```bash
cd HarnessBedrockVPC

agentcore deploy

```

<p align="left">
    <img src="images/deploy.png" alt="AgentCore Harness 배포 화면" width="700" />
</p>

에이전트가 배포되면 확인 메시지가 표시됩니다.
CloudFormation 콘솔에서 배포 상태를 확인할 수도 있습니다.

#### 테스트

`invoke` 명령으로 AgentCore Harness를 호출할 수 있습니다.

```bash

agentcore invoke --harness HarnessBedrockVPC "Hello!"
```
