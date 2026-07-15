#!/usr/bin/env python3
"""
Okta 설정 이미지의 라디오 버튼에 빨간색 강조 표시와 화살표를 추가하는 스크립트
"""

from PIL import Image, ImageDraw
import os


def add_radio_button_highlights(image_path, output_path, radio_positions):
    """
    라디오 버튼 위치에 빨간색 강조 표시를 추가합니다.
    """
    # 이미지 열기
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    # 강조 표시에 사용할 빨간색
    red_color = (255, 0, 0)

    for x, y in radio_positions:
        # 라디오 버튼 주위에 굵은 빨간색 원 그리기
        radius = 20
        for r in range(4):  # 두께를 표현하기 위해 여러 개의 원 사용
            draw.ellipse(
                [x - radius - r, y - radius - r, x + radius + r, y + radius + r],
                outline=red_color,
                width=3,
            )

    # 강조 표시된 이미지 저장
    img.save(output_path)
    print(f"Enhanced image saved: {output_path}")


def add_box_highlights(image_path, output_path, box_positions):
    """
    특정 영역에 빨간색 상자 강조 표시를 추가합니다.
    """
    # 이미지 열기
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)

    # 강조 표시에 사용할 빨간색
    red_color = (255, 0, 0)

    for x1, y1, x2, y2 in box_positions:
        # 굵은 빨간색 사각형 그리기
        for r in range(4):
            draw.rectangle([x1 - r, y1 - r, x2 + r, y2 + r], outline=red_color, width=3)

    # 강조 표시된 이미지 저장
    img.save(output_path)
    print(f"Enhanced image saved: {output_path}")


def main():
    base_dir = "/Users/suramac/amazon-bedrock-agentcore-samples/03-integrations/IDP-examples/Okta/images"

    # 2.png 이미지 - 로그인 방식 및 애플리케이션 유형 라디오 버튼
    image2_positions = [
        (388, 65),  # OIDC - OpenID Connect 라디오 버튼
        (388, 473),  # Web Application 라디오 버튼
    ]

    add_radio_button_highlights(
        os.path.join(base_dir, "2.png"),
        os.path.join(base_dir, "2_enhanced.png"),
        image2_positions,
    )

    # 5.png 이미지 - 액세스 제어 및 즉시 액세스 활성화 라디오 버튼
    image5_positions = [  # noqa: F841
        (362, 62),  # 조직 내 모든 사용자의 액세스 허용 라디오 버튼
        (362, 194),  # 즉시 액세스 활성화 체크박스(라디오 버튼으로 처리)
    ]

    # 3.png 이미지 - 권한 부여 유형의 라디오 버튼 및 체크박스
    image3_positions = [
        (408, 364),  # Authorization Code 체크박스(선택됨)
    ]

    add_radio_button_highlights(
        os.path.join(base_dir, "3.png"),
        os.path.join(base_dir, "3_enhanced.png"),
        image3_positions,
    )

    # 6.png 이미지 - 클라이언트 인증 라디오 버튼 및 클라이언트 자격 증명 강조 표시
    image6_positions = [
        (317, 391),  # Client secret 라디오 버튼(선택됨)
        (653, 289),  # Client ID 복사 버튼
        (530, 725),  # Client secret 복사 버튼
    ]

    add_radio_button_highlights(
        os.path.join(base_dir, "6.png"),
        os.path.join(base_dir, "6_enhanced.png"),
        image6_positions,
    )

    # 7.png 이미지 - Issuer Metadata URI 상자 강조 표시
    image7_boxes = [
        (20, 462, 300, 511),  # Issuer Metadata URI 레이블 상자(아래로 이동)
    ]

    add_box_highlights(
        os.path.join(base_dir, "7.png"),
        os.path.join(base_dir, "7_enhanced.png"),
        image7_boxes,
    )


if __name__ == "__main__":
    main()
