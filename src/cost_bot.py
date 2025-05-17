import os
import json
import boto3
import requests
from datetime import datetime, timedelta

# グローバル初期化（コールドスタート対策）
region = os.environ.get("AWS_REGION", "ap-northeast-1")
secret_name = os.environ.get("SECRET_NAME", "linebot/credentials")

secrets_client = boto3.client('secretsmanager', region_name=region)
secret_dict = json.loads(secrets_client.get_secret_value(SecretId=secret_name)['SecretString'])
LINE_ACCESS_TOKEN = secret_dict['LINE_ACCESS_TOKEN']

# サービス名の略称
SERVICE_NAME_MAP = {
    "Amazon Elastic Compute Cloud - Compute": "EC2",
    "Amazon Simple Storage Service": "S3",
    "Amazon Relational Database Service": "RDS",
    "AWS Lambda": "Lambda",
    "AWS Cost Explorer": "Cost Explorer",
    "Amazon CloudWatch": "CloudWatch",
    "Amazon DynamoDB": "DynamoDB",
    "Amazon Route 53": "Route53",
    "Amazon Virtual Private Cloud": "VPC",
    "Amazon API Gateway": "API Gateway",
    "Amazon Simple Notification Service": "SNS",
    "Amazon Simple Queue Service": "SQS",
    "Amazon Kinesis": "Kinesis",
    "Amazon CloudFront": "CloudFront",
    "Amazon Elastic Block Store": "EBS",
    "Amazon Elastic File System": "EFS",
    "Amazon Redshift": "Redshift",
    "Amazon Elastic Load Balancing": "ELB",
    "Amazon Simple Email Service": "SES",
    "Amazon Elastic Container Service": "ECS",
    "Amazon Elastic Container Registry": "ECR",
    "Amazon Elastic Container Service for Kubernetes": "EKS",
    "Amazon Simple DB": "SimpleDB",
    "Amazon CloudTrail": "CloudTrail",
    "Amazon Elastic Kubernetes Service": "EKS",

    # 必要に応じてここに追加していく
}

# ───────────────────────────────────
# 請求書風メッセージを作成する関数
# ───────────────────────────────────
def build_invoice_message(billing_month: str, total: float, breakdown: list[tuple[str, float]], diff: float) -> str:
    """
    請求書スタイルでメッセージを組み立て（セパレータ幅は固定）
    """
    fixed_width = 13  # 固定幅

    sep = "─" * fixed_width
    # 差額符号を付与
    diff_line = f"{'+' if diff >= 0 else '-'}${abs(diff):.2f}"

    header = [
        f"【請求期間】",
        f"{billing_month}",
        f"",
        f"【合計金額】",
        f"${total:.2f}"
        f"",
        f"【前月差額】",
        f"{diff_line}"
    ]

    lines = []
    for name, amt in breakdown:
        short_name = SERVICE_NAME_MAP.get(name, name)
        lines.append(f"  ・{short_name:<5} : $ {amt:>0.2f}")

    parts = [sep]
    parts.append("AWS利用料請求書".center(fixed_width))
    parts.append(sep)
    parts += header
    parts.append(sep)
    parts.append("【内訳】")
    parts += lines
    parts.append(sep)

    return "\n".join(parts)

# ───────────────────────────────────
# メインLambdaハンドラー
# ───────────────────────────────────
def lambda_handler(event, context):
    try:
        # webhookリクエスト受信とreplytoken抽出
        body = json.loads(event["body"])
        reply_token = body["events"][0]["replyToken"]

        today = datetime.today()

        # 当月
        start_date = today.replace(day=1).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        billing_month = today.strftime("%Y年%m月分")
        # 先月
        first_of_month = today.replace(day=1)
        last_day_prev_month = first_of_month - timedelta(days=1)
        start_prev = last_day_prev_month.replace(day=1).strftime("%Y-%m-%d")
        end_prev = last_day_prev_month.strftime("%Y-%m-%d")
        

         # Cost Explorer API 呼び出し
        ce = boto3.client("ce", region_name="us-east-1")  # Cost Explorerはus-east-1固定
        
        # 当月コスト取得
        total_cost_data = ce.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["BlendedCost"]
        )
        amount = float(total_cost_data["ResultsByTime"][0]["Total"]["BlendedCost"]["Amount"])

        # 先月コスト取得
        prev_cost_data = ce.get_cost_and_usage(
            TimePeriod={"Start": start_prev, "End": end_prev},
            Granularity="MONTHLY",
            Metrics=["BlendedCost"]
        )
        prev_amount = float(prev_cost_data["ResultsByTime"][0]["Total"]["BlendedCost"]["Amount"])

        # 差額を計算
        diff = amount - prev_amount

        # サービス別内訳取得
        service_cost_data = ce.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["BlendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]
        )
        services = sorted(
            [(g["Keys"][0], float(g["Metrics"]["BlendedCost"]["Amount"])) for g in service_cost_data["ResultsByTime"][0]["Groups"]],
            key=lambda x: x[1], reverse=True
        )[:5]  # 上位5サービスだけ抽出

        # メッセージ組み立て
        invoice_text = build_invoice_message(billing_month, amount, services, diff)

        # LINEへ返信
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
        }
        payload = {
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": invoice_text}]
        }
        response = requests.post("https://api.line.me/v2/bot/message/reply", headers=headers, json=payload)

        # ステータス確認
        if response.status_code != 200:
            print(f"LINEへの送信失敗: {response.status_code}, {response.text}")
            return {"statusCode": 500, "body": "Failed to send message to LINE"}

        return {"statusCode": 200}

    except Exception as e:
        print("エラー発生:", str(e))
        return {"statusCode": 500, "body": str(e)}
