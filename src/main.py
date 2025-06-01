import json
import requests #type:ignore
from datetime import datetime, timedelta
import boto3 #type:ignore
from dateutil.relativedelta import relativedelta #type:ignore

from secrets import get_line_access_token
from billing import get_cost_data, extract_total_amount, extract_service_breakdown
from message import build_invoice_message

LINE_ACCESS_TOKEN = get_line_access_token()

def lambda_handler(event, context):
    try:
        body = json.loads(event["body"])
        reply_token = body["events"][0]["replyToken"]
        user_message = body["events"][0]["message"]["text"].strip().lower()

        # ヘルプモード
        if user_message in ("help", "ヘルプ", "使い方"):
            help_text = (
                "【目的】\n"
                "AWSのコストを請求書形式のメッセージで通知します\n"
                "\n"
                "【使い方】\n"
                "- 「コスト」：今月のコストを確認\n"
                "- 「先月」：先月のコストを確認\n"
                "\n"
                "【コマンド】\n"
                "- '先月' → 先月の請求書のみを表示\n"
                "- '内訳' → 詳細な内訳をすべて表示（今後対応予定）\n"
            )
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
            }
            payload = {
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": help_text}]
            }
            requests.post("https://api.line.me/v2/bot/message/reply", headers=headers, json=payload)
            return {"statusCode": 200}

        today = datetime.today()
        ce = boto3.client("ce", region_name="us-east-1")

        # 請求データ取得対象の初期化（デフォルトは今月）
        if user_message == "先月":
            # 先月のデータのみを表示
            start_dt = (today.replace(day=1) - relativedelta(months=1))
            end_dt = today.replace(day=1)
            billing_month = start_dt.strftime("%Y年%m月分")
            show_diff = False
        else:
            # 今月データ＋前月との差分表示
            start_dt = today.replace(day=1)
            end_dt = start_dt + relativedelta(months=1)
            billing_month = start_dt.strftime("%Y年%m月分")
            show_diff = True

        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

        current_total = extract_total_amount(get_cost_data(ce, start_date, end_date))

        if show_diff:
            prev_start = start_dt - relativedelta(months=1)
            prev_end = start_dt
            prev_total = extract_total_amount(get_cost_data(ce, prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d")))
            diff = current_total - prev_total
        else:
            diff = 0.0

        service_breakdown = extract_service_breakdown(
            get_cost_data(ce, start_date, end_date, group_by_service=True)
        )

        invoice_text = build_invoice_message(billing_month, current_total, service_breakdown, diff)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
        }
        payload = {
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": invoice_text}]
        }
        response = requests.post("https://api.line.me/v2/bot/message/reply", headers=headers, json=payload)

        if response.status_code != 200:
            print(f"LINEへの送信失敗: {response.status_code}, {response.text}")
            return {"statusCode": 500, "body": "Failed to send message to LINE"}

        return {"statusCode": 200}

    except Exception as e:
        print("エラー発生:", str(e))
        return {"statusCode": 500, "body": str(e)}
