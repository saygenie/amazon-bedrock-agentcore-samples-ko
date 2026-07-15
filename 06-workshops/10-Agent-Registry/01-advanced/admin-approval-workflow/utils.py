"""Agent Registry 폴링 작업을 위한 유틸리티 헬퍼입니다."""

import time


def wait_for_registry_ready(cp_client, registry_id, poll_interval=10):
    """레지스트리가 READY 상태가 될 때까지 폴링합니다."""
    status = "Checking"
    while status.lower() != "ready":
        resp = cp_client.get_registry(registryId=registry_id)
        status = resp["status"]
        if status.lower() == "ready":
            print("Verified: Registry is in Ready state")
        else:
            print(f"Registry is in {status} state. Waiting for it to be in Ready state")
        time.sleep(poll_interval)


def wait_for_record_draft(cp_client, registry_id, record_id, poll_interval=2):
    """레지스트리 레코드가 DRAFT 상태가 될 때까지 폴링합니다."""
    status = "Checking"
    while status.lower() != "draft":
        resp = cp_client.get_registry_record(registryId=registry_id, recordId=record_id)
        status = resp["status"]
        metadata = resp.get("ResponseMetadata", {})
        if status.lower() == "draft":
            print("Verified: Registry record is in Draft state. Ready to be submitted for Approval")
            headers = metadata.get("HTTPHeaders", {})
            request_id = headers.get("x-amzn-requestid", "")
            date = headers.get("date", "")
            print(f"RequestId: {request_id}, Timestamp: {date}")
        else:
            print(f"Registry record is in {status} state. Waiting for it to be in Draft state")
        time.sleep(poll_interval)
