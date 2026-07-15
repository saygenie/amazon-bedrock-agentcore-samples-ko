import os
from pydantic import BaseModel
from fastmcp import FastMCP, Context
from fastmcp.server.elicitation import AcceptedElicitation
from dynamo_utils import FinanceDB

mcp = FastMCP(name="ElicitationMCP")

# 모든 AgentCore/Lambda container에는 AWS_REGION이 안정적으로 설정됨
_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
db = FinanceDB(region_name=_region)


class AmountInput(BaseModel):
    amount: float


class DescriptionInput(BaseModel):
    description: str


class CategoryInput(BaseModel):
    category: str  # 다음 중 하나: food, transport, bills, entertainment, other


class ConfirmInput(BaseModel):
    confirm: str  # Yes 또는 No


@mcp.tool()
async def add_expense_interactive(user_alias: str, ctx: Context) -> str:
    """Interactively add a new expense using elicitation
    Args:
        user_alias: User identifier
    """
    print(f"Debug this method, user_alias: {user_alias}")
    # 1단계: 금액 요청
    result = await ctx.elicit("How much did you spend?", AmountInput)
    if not isinstance(result, AcceptedElicitation):
        return "Expense entry cancelled."
    amount = result.data.amount

    # 2단계: 설명 요청
    result = await ctx.elicit("What was it for?", DescriptionInput)
    if not isinstance(result, AcceptedElicitation):
        return "Expense entry cancelled."
    description = result.data.description

    # 3단계: Category 선택
    result = await ctx.elicit(
        "Select a category (food, transport, bills, entertainment, other):",
        CategoryInput,
    )
    if not isinstance(result, AcceptedElicitation):
        return "Expense entry cancelled."
    category = result.data.category

    # 4단계: 저장 전 확인
    confirm_msg = f"Confirm: add expense of ${amount:.2f} for {description} (category: {category})? Reply Yes or No"
    result = await ctx.elicit(confirm_msg, ConfirmInput)
    if not isinstance(result, AcceptedElicitation) or result.data.confirm != "Yes":
        return "Expense entry cancelled."

    return db.add_transaction(user_alias, "expense", -abs(amount), description, category)


@mcp.tool()
def add_expense(user_alias: str, amount: float, description: str, category: str = "other") -> str:
    """Add a new expense transaction.

    Args:
        user_alias: User identifier
        amount: Expense amount (positive number)
        description: Description of the expense
        category: Expense category (food, transport, bills, entertainment, other)
    """
    return db.add_transaction(user_alias, "expense", -abs(amount), description, category)


@mcp.tool()
async def analyze_spending(user_alias: str, ctx: Context) -> str:
    """Fetch this user's expenses from DynamoDB and use the client's LLM
    to generate a personalised financial analysis.

    Args:
        user_alias: User identifier
    """
    transactions = db.get_transactions(user_alias)
    if not transactions:
        return f"No transactions found for {user_alias}."

    lines = "\n".join(f"- {t['description']} (${abs(float(t['amount'])):.2f}, {t['category']})" for t in transactions)

    prompt = (
        f"Here are the recent expenses for a user:\n{lines}\n\n"
        f"Please analyse the spending patterns and give 3 concise, "
        f"actionable recommendations to improve their finances. "
        f"Keep the response under 120 words."
    )

    ai_analysis = "Analysis unavailable."
    try:
        response = await ctx.sample(messages=prompt, max_tokens=300)
        if hasattr(response, "text") and response.text:
            ai_analysis = response.text
    except Exception:
        pass

    return f"Spending Analysis for {user_alias}:\n\n{ai_analysis}"


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",  # nosec B104
        port=8000,
        stateless_http=False,
    )
