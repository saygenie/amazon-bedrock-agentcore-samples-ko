"""Registry 검색 응답에서 Agent Skill을 로드하는 유틸리티입니다.

레지스트리 레코드를 파싱하고 GitHub 리포지토리 참조에서 모든 스킬 파일을
다운로드하며, 로컬 폴더 구조를 생성하고 선언된 패키지를 설치합니다.

사용법:
    from util.skill_loader import load_skill_from_registry

    skill_dir, skill_md = load_skill_from_registry(search_response, base_dir="./skills")
"""

import json
import os
import subprocess
import urllib.request
import urllib.error


# GitHub API 기본 URL
GITHUB_API = "https://api.github.com/repos"


def _parse_github_url(url):
    """GitHub 트리 URL에서 소유자, 리포지토리, 브랜치 및 경로를 추출합니다.

    예: https://github.com/anthropics/skills/tree/main/skills/pdf
    반환값: ("anthropics", "skills", "main", "skills/pdf")
    """
    parts = url.replace("https://github.com/", "").split("/")
    owner, repo = parts[0], parts[1]
    # parts[2] == "tree", parts[3] == 브랜치
    branch = parts[3]
    path = "/".join(parts[4:])
    return owner, repo, branch, path


def _fetch_github_contents(owner, repo, path, branch="main"):
    """GitHub API에서 디렉터리 목록이나 파일 콘텐츠를 가져옵니다."""
    url = f"{GITHUB_API}/{owner}/{repo}/contents/{path}?ref={branch}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    if not url.startswith("https://"):  # URL 스킴 검증(bandit B310)
        raise ValueError(f"Only HTTPS URLs are allowed, got: {url}")
    with urllib.request.urlopen(req) as resp:  # nosec B310 - 위에서 URL 스킴 검증
        return json.loads(resp.read().decode())


def _download_file(download_url, dest_path):
    """원시 GitHub URL에서 단일 파일을 다운로드합니다."""
    if not download_url.startswith("https://"):  # URL 스킴 검증(bandit B310)
        raise ValueError(f"Only HTTPS URLs are allowed, got: {download_url}")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    urllib.request.urlretrieve(download_url, dest_path)  # nosec B310 - 위에서 URL 스킴 검증


def _download_github_tree(owner, repo, branch, remote_path, local_dir, root_remote_path=None):
    """GitHub 디렉터리의 모든 파일을 재귀적으로 다운로드합니다.

    매개변수:
        root_remote_path: 상대 경로 계산에 사용하는 최상위 원격 경로.
                          첫 번째 호출에서 자동으로 설정됩니다.
    """
    if root_remote_path is None:
        root_remote_path = remote_path

    contents = _fetch_github_contents(owner, repo, remote_path, branch)
    if not isinstance(contents, list):
        contents = [contents]

    for item in contents:
        # 폴더 구조를 유지하도록 최상위 원격 경로를 기준으로 상대 경로 계산
        rel_path = item["path"][len(root_remote_path) :].lstrip("/")
        local_path = os.path.join(local_dir, rel_path)

        if item["type"] == "dir":
            _download_github_tree(owner, repo, branch, item["path"], local_dir, root_remote_path)
        else:
            _download_file(item["download_url"], local_path)
            print(f"  Downloaded: {rel_path}")


def _install_packages(packages):
    """스킬 정의에 선언된 패키지를 설치합니다."""
    for pkg in packages:
        registry = pkg.get("registryType", "")
        identifier = pkg["identifier"]
        version = pkg.get("version", "")
        pkg_spec = f"{identifier}=={version}" if version else identifier

        if registry == "pypi":
            print(f"  Installing (pip): {pkg_spec}")
            subprocess.run(["pip", "install", "-q", pkg_spec], check=True)
        elif registry == "npm":
            print(f"  Installing (npm): {pkg_spec}")
            subprocess.run(["npm", "install", pkg_spec], check=True)
        else:
            print(f"  Skipping unknown registry type: {registry} for {identifier}")


def load_skill_from_registry(search_response, record_index=0, base_dir="./skills"):
    """레지스트리 검색 응답을 파싱하고 로컬에 스킬을 설정합니다.

    단계:
        1. 응답에서 skillMd 및 skillDefinition 추출
        2. GitHub 리포지토리 참조에서 모든 파일 다운로드
        3. 선언된 패키지 설치
        4. 스킬 디렉터리 경로 및 SKILL.md 콘텐츠 반환

    매개변수:
        search_response: 전체 search_registry_records 응답 딕셔너리.
        record_index: 결과가 여러 개인 경우 사용할 레코드(기본값 0).
        base_dir: 스킬 폴더를 생성할 상위 디렉터리.

    반환값:
        (skill_dir, skill_md_content) 튜플.
    """
    record = search_response["registryRecords"][record_index]
    agent_skills = record["descriptors"]["agentSkills"]

    # 1. 스킬 콘텐츠 파싱
    skill_md_content = agent_skills["skillMd"]["inlineContent"]
    skill_def = json.loads(agent_skills["skillDefinition"]["inlineContent"])

    # SKILL.md 프런트매터(`name:` 필드)에서 스킬 이름 추출
    # AgentSkills 플러그인의 디렉터리 이름과 반드시 일치해야 함
    skill_name = record["name"]
    for line in skill_md_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            skill_name = stripped[len("name:") :].strip()
            break

    print(f"Loading skill: {skill_name}")

    # 2. 로컬 스킬 디렉터리 생성(이름은 SKILL.md 프런트매터와 일치)
    skill_dir = os.path.join(base_dir, skill_name)
    os.makedirs(skill_dir, exist_ok=True)

    # 3. 로컬에 SKILL.md 작성
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md_path, "w", encoding="utf-8") as f:
        f.write(skill_md_content)
    print("  Written: SKILL.md")

    # 4. GitHub 리포지토리에서 나머지 파일 다운로드
    repo_info = skill_def.get("repository", {})
    repo_url = repo_info.get("url", "")

    if repo_url:
        owner, repo, branch, remote_path = _parse_github_url(repo_url)
        print(f"  Downloading from: {owner}/{repo}/{remote_path} (branch: {branch})")

        contents = _fetch_github_contents(owner, repo, remote_path, branch)
        for item in contents:
            # inlineContent에서 이미 작성한 SKILL.md는 건너뛰기
            if item["name"].upper() == "SKILL.MD":
                continue

            if item["type"] == "dir":
                # 상대 경로가 스킬 루트 기준이 되도록 remote_path를 루트로 전달
                _download_github_tree(owner, repo, branch, item["path"], skill_dir, remote_path)
            else:
                dest = os.path.join(skill_dir, item["name"])
                _download_file(item["download_url"], dest)
                print(f"  Downloaded: {item['name']}")

    # 5. 패키지 설치
    packages = skill_def.get("packages", [])
    if packages:
        print("  Installing packages...")
        _install_packages(packages)

    # 6. 최종 구조 출력
    print(f"\nSkill folder ready: {os.path.abspath(skill_dir)}")
    for root, dirs, files in os.walk(skill_dir):
        level = root.replace(skill_dir, "").count(os.sep)
        indent = "  " * level
        print(f"  {indent}{os.path.basename(root)}/")
        for f in files:
            print(f"  {indent}  {f}")

    return skill_dir, skill_md_content
