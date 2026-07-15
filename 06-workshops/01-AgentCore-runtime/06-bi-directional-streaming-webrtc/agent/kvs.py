"""KVS Signaling Channel 관리입니다.

KVS Signaling Channel 생성/검색과 WebRTC 연결용 TURN/ICE Server
자격 증명 조회를 처리합니다.
"""

import boto3
from loguru import logger

# 모듈 상태 - init()을 통해 한 번 초기화
channel_arn = None
_https_endpoint = None


def init(channel_name, region):
    """KVS를 초기화합니다. Signaling Channel을 찾거나 생성하고 HTTPS 엔드포인트를 확인합니다."""
    global channel_arn, _https_endpoint
    client = boto3.client("kinesisvideo", region_name=region)

    # 기존 Channel을 찾거나 새로 생성
    try:
        resp = client.describe_signaling_channel(ChannelName=channel_name)
        channel_arn = resp["ChannelInfo"]["ChannelARN"]
    except client.exceptions.ResourceNotFoundException:
        resp = client.create_signaling_channel(ChannelName=channel_name, ChannelType="SINGLE_MASTER")
        channel_arn = resp["ChannelARN"]
    logger.info(f"Signaling channel: {channel_arn}")

    # ICE Server 요청용 HTTPS 엔드포인트 확인
    resp = client.get_signaling_channel_endpoint(
        ChannelARN=channel_arn,
        SingleMasterChannelEndpointConfiguration={
            "Protocols": ["HTTPS"],
            "Role": "MASTER",
        },
    )
    _https_endpoint = resp["ResourceEndpointList"][0]["ResourceEndpoint"]


def get_ice_servers(region, client_id=None):
    """KVS에서 원시 ICE Server 구성을 가져옵니다."""
    client = boto3.client("kinesis-video-signaling", region_name=region, endpoint_url=_https_endpoint)
    params = {"ChannelARN": channel_arn, "Service": "TURN"}
    if client_id:
        params["ClientId"] = client_id
    return client.get_ice_server_config(**params)["IceServerList"]


def get_rtc_ice_servers(region, client_id=None, turn_only=False):
    """KVS에서 ICE Server를 가져와 RTCIceServer 객체로 반환합니다."""
    from aiortc import RTCIceServer

    servers = []
    for s in get_ice_servers(region, client_id):
        urls = [u for u in s["Uris"] if u.startswith("turn:")] if turn_only else s["Uris"]
        if urls:
            servers.append(RTCIceServer(urls=urls, username=s.get("Username"), credential=s.get("Password")))
    return servers
