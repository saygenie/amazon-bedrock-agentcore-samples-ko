"""
Search Tool - Gateway용 모의 검색 기능입니다.

이 도구는 모의 결과를 사용하는 검색 엔진을 시뮬레이션합니다.
"""

import json
from datetime import datetime


# 모의 검색 index
MOCK_SEARCH_INDEX = {
    "documents": [
        {
            "id": "doc1",
            "title": "Introduction to Amazon Bedrock",
            "content": "Amazon Bedrock is a fully managed service that offers foundation models...",
            "url": "https://aws.amazon.com/bedrock",
            "keywords": ["bedrock", "aws", "ai", "foundation models"],
        },
        {
            "id": "doc2",
            "title": "AgentCore Runtime Guide",
            "content": "AgentCore Runtime provides serverless execution for AI agents...",
            "url": "https://docs.aws.amazon.com/agentcore",
            "keywords": ["agentcore", "runtime", "agents", "serverless"],
        },
        {
            "id": "doc3",
            "title": "MCP Gateway Documentation",
            "content": "The Model Context Protocol Gateway enables tool integration...",
            "url": "https://docs.aws.amazon.com/gateway",
            "keywords": ["mcp", "gateway", "tools", "protocol"],
        },
        {
            "id": "doc4",
            "title": "Lambda Interceptors Best Practices",
            "content": "Lambda interceptors allow you to transform requests and responses...",
            "url": "https://docs.aws.amazon.com/lambda",
            "keywords": ["lambda", "interceptor", "aws", "serverless"],
        },
        {
            "id": "doc5",
            "title": "DynamoDB Query Patterns",
            "content": "DynamoDB provides fast and flexible NoSQL database services...",
            "url": "https://aws.amazon.com/dynamodb",
            "keywords": ["dynamodb", "database", "nosql", "aws"],
        },
        {
            "id": "doc6",
            "title": "Strands Agent Framework",
            "content": "Strands is a powerful framework for building AI agents with tools...",
            "url": "https://strands.dev",
            "keywords": ["strands", "agents", "framework", "ai"],
        },
        {
            "id": "doc7",
            "title": "IAM Permissions for AgentCore",
            "content": "Configure IAM roles and policies for AgentCore resources...",
            "url": "https://docs.aws.amazon.com/iam",
            "keywords": ["iam", "permissions", "security", "aws"],
        },
        {
            "id": "doc8",
            "title": "Tool Invocation in Agents",
            "content": "Agents can invoke tools through the MCP protocol...",
            "url": "https://docs.tools.dev",
            "keywords": ["tools", "invocation", "mcp", "agents"],
        },
    ]
}


def search_documents(query, max_results=10):
    """
    query 문자열로 모의 문서를 검색합니다.

    인자:
        query: 검색 query 문자열
        max_results: 반환할 최대 결과 수

    반환:
        관련도 점수가 포함된 일치 문서 목록
    """
    query_lower = query.lower()
    query_terms = query_lower.split()

    results = []

    for doc in MOCK_SEARCH_INDEX["documents"]:
        score = 0

            # title 확인
        if query_lower in doc["title"].lower():
            score += 10

            # content 확인
        if query_lower in doc["content"].lower():
            score += 5

            # keyword 확인
        for keyword in doc["keywords"]:
            if keyword in query_lower:
                score += 3

            # 개별 term 확인
        for term in query_terms:
            if term in doc["title"].lower():
                score += 2
            if term in doc["content"].lower():
                score += 1
            if term in doc["keywords"]:
                score += 2

        if score > 0:
            results.append({"document": doc, "relevance_score": score})

    # 관련도 점수로 정렬
    results.sort(key=lambda x: x["relevance_score"], reverse=True)

    return results[:max_results]


def lambda_handler(event, context):
    """
    search tool용 Lambda 핸들러입니다.

    예상 입력:
    {
        "query": "search terms",
        "max_results": 10 (optional),
        "filter_keywords": ["keyword1", "keyword2"] (optional)
    }

    관련도 점수가 포함된 검색 결과를 반환합니다.
    """
    print(f"Search tool received event: {json.dumps(event)}")

        # 입력 파싱
    body = event if isinstance(event, dict) else json.loads(event)
    query = body.get("query", "")
    max_results = body.get("max_results", 10)
    filter_keywords = body.get("filter_keywords", [])

        # query 검증
    if not query:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "tool": "search_tool",
                    "error": "Query parameter is required",
                    "success": False,
                }
            ),
        }

        # 검색 수행
    results = search_documents(query, max_results)

        # 제공된 경우 keyword filter 적용
    if filter_keywords:
        results = [r for r in results if any(kw in r["document"]["keywords"] for kw in filter_keywords)]

        # 결과 형식 지정
    formatted_results = []
    for item in results:
        doc = item["document"]
        formatted_results.append(
            {
                "id": doc["id"],
                "title": doc["title"],
                "snippet": doc["content"][:200] + "...",
                "url": doc["url"],
                "keywords": doc["keywords"],
                "relevance_score": item["relevance_score"],
            }
        )

    search_result = {
        "query": query,
        "result_count": len(formatted_results),
        "max_results": max_results,
        "filter_keywords": filter_keywords,
        "results": formatted_results,
        "search_timestamp": datetime.utcnow().isoformat(),
    }

    response = {
        "statusCode": 200,
        "body": json.dumps({"tool": "search_tool", "result": search_result, "success": True}),
    }

    print(f"Search tool response: {len(formatted_results)} results for query '{query}'")
    return response


# Gateway 등록용 MCP Tool Definition
TOOL_DEFINITION = {
    "name": "search_tool",
    "description": "Search for documents and information using keywords. Returns relevant results with snippets and URLs.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string (keywords or phrases)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return, between 1 and 100 (default: 10)",
            },
            "filter_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of keywords to filter results",
            },
        },
        "required": ["query"],
    },
}


if __name__ == "__main__":
# 로컬에서 도구 테스트
    test_cases = [
        {"query": "bedrock"},
        {"query": "lambda interceptor", "max_results": 5},
        {"query": "aws", "filter_keywords": ["aws", "lambda"]},
        {"query": "agent tools", "max_results": 3},
    ]

    for i, test_event in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"Test Case {i}: {test_event}")
        print(f"{'=' * 80}")
        result = lambda_handler(test_event, None)
        print(f"{json.dumps(result, indent=2)}")
