from flask import Flask, request, jsonify
import logging
import time

# 로깅 구성
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/ping", methods=["GET"])
def ping():
    """
    Health check endpoint
    Returns 200 OK if the service is healthy
    """
    logger.info("Received ping request")
    return jsonify({"status": "healthy", "message": "Service is running"}), 200


@app.route("/invocations", methods=["POST"])
def invocations():
    """
    Main invocation endpoint for processing requests
    Accepts JSON payload and returns processed response
    """
    try:
        logger.info("Received invocations request")

        # 요청에서 JSON 페이로드 가져오기
        payload = request.get_json()

        if not payload:
            logger.warning("Empty payload received")
            return jsonify({"status": "error", "message": "No payload provided"}), 400

        logger.info(f"Processing payload: {payload}")

        # 요청 처리(자리 표시자 로직)
        # 실제 구현에서는 Agent/모델을 호출함
        response = {
            "status": "success",
            "message": "Request processed successfully",
            "data": {"received": payload, "processed_by": "vpc-fargate-agent"},
            "timestamp": time.time(),
        }

        logger.info("Request processed successfully")
        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "An error has occurred when processing the request",
                }
            ),
            500,
        )


if __name__ == "__main__":
    # 8080 포트에서 실행
    logger.info("Starting Flask application on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)  # nosec  nosemgrep
