/**
 * Fun Facts x402 seller - Node.js AWS Lambda function입니다.
 *
 * agentcore-payments seller에서 사용하는 표준 패턴을 따릅니다
 * (backend/lambdas/sellers/crypto-price 참조).
 *
 *   - `@x402/hono`의 `paymentMiddlewareFromHTTPServer`가 전체 402 및 facilitator
 *     verify/settle handshake를 처리하므로 base64 header를 수동으로 조립하거나
 *     /verify, /settle HTTP 호출을 직접 수행할 필요가 없습니다.
 *   - Chain Agnostic Improvement Proposal 2 (CAIP-2) network 식별자를 사용합니다
 *     (Base Sepolia는 `eip155:84532`, Devnet은 `solana:…`). 짧은
 *     `base-sepolia`/`solana-devnet` 문자열이 아니라 AgentCore Payments plugin이
 *     x402 payload에 서명할 때 wire로 내보내는 값입니다.
 *   - 사람이 읽을 수 있는 USD(`"$0.01"`)로 가격을 표시하며 x402 middleware가
 *     on-chain atomic amount로 변환합니다.
 *   - 응답 형식은 AgentCore Registry가 index할 수 있는 Bazaar 친화적 schema인
 *     `{ x402_content, x402_meta }`입니다.
 *   - `declareDiscoveryExtension`을 사용하므로 Bazaar Model Context Protocol
 *     (MCP)을 통해 이 seller를 검색할 수 있습니다.
 *
 * Multi-network: `SELLER_WALLET_ADDRESS`(EVM)와
 * `SELLER_SOLANA_WALLET_ADDRESS`를 모두 설정하면 두 `accepts` 항목을 모두
 * 내보내고 agent가 instrument가 속한 network를 선택합니다.
 */
import { Hono } from "hono";
import { handle } from "hono/aws-lambda";
import {
  paymentMiddlewareFromHTTPServer,
  x402HTTPResourceServer,
  x402ResourceServer,
} from "@x402/hono";
import { HTTPFacilitatorClient } from "@x402/core/server";
import { registerExactEvmScheme } from "@x402/evm/exact/server";
// SVM은 Solana program이 실행되는 on-chain runtime인 Solana Virtual Machine입니다.
// x402 SVM scheme은 Solana에서 SPL token transfer transaction을 build하고 검증합니다.
import { registerExactSvmScheme } from "@x402/svm/exact/server";
import {
  bazaarResourceServerExtension,
  declareDiscoveryExtension,
} from "@x402/extensions/bazaar";

// ── Config(Lambda 환경 변수에서 로드) ───────────────────────────────────
// Wallet address 기본값은 "WALLET_NOT_CONFIGURED"이므로 구성되지 않은 seller는
// 402 응답에 명백히 잘못된 placeholder를 내보냅니다. Facilitator는 settlement
// 시 이를 거부하고, agent는 운영자가 `.env`의 SELLER_WALLET_ADDRESS 또는
// SELLER_SOLANA_WALLET_ADDRESS를 확인하도록 안내하는 오류를 표시합니다.
const X402_CONFIG = {
  facilitatorUrl:
    process.env.X402_FACILITATOR_URL || "https://x402.org/facilitator",
  // CAIP-2 network 식별자
  evmNetwork: "eip155:84532", // Base Sepolia
  evmPayTo: process.env.SELLER_WALLET_ADDRESS || "WALLET_NOT_CONFIGURED",
  solanaNetwork: "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1", // Devnet
  solanaPayTo:
    process.env.SELLER_SOLANA_WALLET_ADDRESS || "WALLET_NOT_CONFIGURED",
};

const PRICE = process.env.X402_PRICE || "$0.01";

// ── Fun Facts 데이터 ────────────────────────────────────────────────────
const FACTS = {
  space: [
    "A day on Venus is longer than its year — it takes 243 Earth days to rotate but only 225 days to orbit the sun.",
    "Neutron stars are so dense that a sugar-cube-sized sample would weigh about 1 billion tons on Earth.",
    "The largest known volcano in the solar system, Olympus Mons on Mars, is nearly three times taller than Mount Everest.",
    "There is a planet made largely of diamond — 55 Cancri e, about 40 light-years away.",
    "Saturn's density is so low that, hypothetically, it would float in a bathtub of water large enough to hold it.",
  ],
  oceans: [
    "More than 80 percent of the ocean has never been mapped, explored, or even seen by humans.",
    "The Mariana Trench reaches nearly 11,000 meters deep — taller than Mount Everest turned upside down.",
    "Hydrothermal vents on the ocean floor support ecosystems that never see sunlight.",
    "Blue whales' hearts are so large that a human could swim through their arteries.",
    "Plankton in the ocean produce more than half of the oxygen we breathe.",
  ],
  ai: [
    "The term 'artificial intelligence' was coined at the Dartmouth Workshop in 1956.",
    "Transformer architectures, introduced in 2017, underpin nearly every modern large language model.",
    "Reinforcement learning from human feedback (RLHF) is what made instruction-following LLMs practical.",
    "Chess AI definitively surpassed human world champions in 1997 with IBM's Deep Blue.",
    "Modern LLMs are trained on tokens measured in the trillions.",
  ],
  payments: [
    "The x402 protocol revives an HTTP status code — 402 Payment Required — that was reserved in RFC 7231 but never standardized.",
    "Stablecoins like USDC settle on-chain in seconds, versus days for traditional wire transfers.",
    "Micropayments were first proposed by Ted Nelson in the 1960s as part of his Project Xanadu vision.",
    "Account abstraction on Ethereum makes gasless agent payments possible via meta-transactions.",
    "The first cryptocurrency micropayment channel was demonstrated in 2013 by Meni Rosenfeld and Peter Todd.",
  ],
  default: [
    "Honey found in Egyptian tombs is still edible — honey does not spoil.",
    "Octopuses have three hearts and blue blood.",
    "Bananas are berries, but strawberries are not.",
    "The Eiffel Tower can grow more than 15 cm taller in summer due to thermal expansion.",
    "Wombat droppings are cube-shaped.",
  ],
};

const SUPPORTED_TOPICS = Object.keys(FACTS).filter((k) => k !== "default");

function pickFact(rawTopic) {
  const key = String(rawTopic || "").trim().toLowerCase();
  const resolved = FACTS[key] ? key : "default";
  const pool = FACTS[resolved];
  return { topic: resolved, fact: pool[Math.floor(Math.random() * pool.length)] };
}

function buildAccepts(price) {
  const NOT_CONFIGURED = "WALLET_NOT_CONFIGURED";
  const accepts = [];
  // Placeholder를 설정되지 않은 환경 변수와 동일하게 처리합니다. 402 응답의
  // 형식을 유지하도록 accepts 항목은 내보내지만 facilitator가 settlement 시
  // 모든 payment proof를 거부하고 agent가 명확한 오류 메시지를 표시합니다.
  if (X402_CONFIG.evmPayTo && X402_CONFIG.evmPayTo !== NOT_CONFIGURED) {
    accepts.push({
      scheme: "exact",
      price,
      network: X402_CONFIG.evmNetwork,
      payTo: X402_CONFIG.evmPayTo,
    });
  }
  if (X402_CONFIG.solanaPayTo && X402_CONFIG.solanaPayTo !== NOT_CONFIGURED) {
    accepts.push({
      scheme: "exact",
      price,
      network: X402_CONFIG.solanaNetwork,
      payTo: X402_CONFIG.solanaPayTo,
    });
  }
  if (!accepts.length) {
    // 구성된 wallet이 없어도 402 응답 형식을 유지하도록 EVM 항목을 내보냅니다.
    // Facilitator는 settlement 시 proof를 거부합니다. 따라서 첫 실행 설정 과정에서
    // 유용한 오류 메시지를 유지할 수 있습니다.
    accepts.push({
      scheme: "exact",
      price,
      network: X402_CONFIG.evmNetwork,
      payTo: NOT_CONFIGURED,
    });
  }
  return accepts;
}

// ── Hono app + x402 middleware ──────────────────────────────────────────
const app = new Hono();

// CloudWatch query를 재사용할 수 있도록 reference seller와 같은 형식으로
// request를 logging합니다.
app.use("*", async (c, next) => {
  const start = Date.now();
  const sig = c.req.header("payment-signature");
  console.log(
    JSON.stringify({
      event: "request_in",
      method: c.req.method,
      path: c.req.path,
      hasPaymentSignature: !!sig,
      paymentSignatureLength: sig?.length || 0,
    })
  );
  await next();
  console.log(
    JSON.stringify({
      event: "response_out",
      method: c.req.method,
      path: c.req.path,
      status: c.res.status,
      durationMs: Date.now() - start,
      hasPaymentSignature: !!sig,
    })
  );
});

// x402 server - EVM 및 SVM scheme과 Bazaar discovery extension입니다.
const facilitatorClient = new HTTPFacilitatorClient({
  url: X402_CONFIG.facilitatorUrl,
});
const server = new x402ResourceServer(facilitatorClient);
registerExactEvmScheme(server);
registerExactSvmScheme(server);
server.registerExtension(bazaarResourceServerExtension);

// 유료 route GET /facts 하나를 선언합니다. AgentCore Registry가 이 seller를
// 나열할 수 있도록 Bazaar discovery extension이 topic query parameter schema와
// 예제 출력을 노출합니다.
const routes = {
  "GET /facts": {
    accepts: buildAccepts(PRICE),
    extensions: {
      ...declareDiscoveryExtension({
        input: { topic: "space" },
        inputSchema: {
          properties: {
            topic: {
              type: "string",
              description: `One of ${SUPPORTED_TOPICS.join(", ")} (or any other string for a random general fact).`,
            },
          },
          required: [],
        },
        bodyType: "query",
        output: {
          example: {
            x402_content: {
              type: "text",
              data: '{"topic":"space","fact":"A day on Venus is longer than its year …"}',
              title: "Fun fact: space",
              mime_type: "application/json",
            },
            x402_meta: {
              seller: "pay-for-api-fun-facts",
              version: "1.0",
            },
          },
        },
      }),
    },
  },
};

const httpServer = new x402HTTPResourceServer(server, routes);
await httpServer.initialize();
app.use(
  paymentMiddlewareFromHTTPServer(httpServer, undefined, undefined, false)
);

// ── Route ───────────────────────────────────────────────────────────────

// 유료 route
app.get("/facts", (c) => {
  const topic = c.req.query("topic") || "default";
  const { topic: resolvedTopic, fact } = pickFact(topic);
  return c.json({
    x402_content: {
      type: "text",
      data: JSON.stringify({ topic: resolvedTopic, fact }),
      title: `Fun fact: ${resolvedTopic}`,
      mime_type: "application/json",
    },
    x402_meta: {
      seller: "pay-for-api-fun-facts",
      version: "1.0",
      generated_at: new Date().toISOString(),
      supported_topics: SUPPORTED_TOPICS,
    },
  });
});

// 결제가 필요 없는 public 상태 확인 endpoint입니다.
app.get("/health", (c) =>
  c.json({
    status: "ok",
    service: "pay-for-api-fun-facts",
    price: PRICE,
    networks: buildAccepts(PRICE).map((a) => a.network),
    supported_topics: SUPPORTED_TOPICS,
  })
);

// Discovery root입니다.
app.get("/", (c) =>
  c.json({
    service: "pay-for-api-fun-facts",
    paidEndpoints: ["GET /facts?topic=<topic>"],
    price: PRICE,
  })
);

export const handler = handle(app);
