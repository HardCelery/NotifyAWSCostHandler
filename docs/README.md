### ✨ 目的

ユーザーがLINE Botにメッセージを送ると、LambdaがAWS Cost Explorer APIを使用して**AWSのコスト**を取得し、請求書風のメッセージとしてLINEへ返信します。サーバーレス設計によりコスト効率が高く、**イベント駆動型で課金最小化**を実現しています。

---

### ⛏️ 構成概要

1. ユーザーがLINE Botにメッセージを送信
2. LINEはMessagin APIを通じて、Webhook URLにデータ（JSON）をPOST
3. API Gateway経由でLambdaがWebhookリクエストを受信
4. Lambda関数がコードを実行し、メッセージ内容を解析
5. Cost Explorer APIで当月の合計利用料と上位5サービスの内訳を取得
6. Secrets ManagerからLINEトークンを取得
7. 請求書形式のメッセージを生成し、LINEトークンを使ってLINEに返信

---

### 🛠️ 技術スタック

| 項目           | 内容                                                |
| -------------- | --------------------------------------------------- |
| 言語           | Python 3.11                                         |
| 使用ライブラリ | boto3, requests, json, datetime, os                 |
| AWSサービス    | Lambda, API Gateway, Secrets Manager, Cost Explorer |
| メッセージAPI  | LINE Messaging API（Webhook, replyToken使用）       |

---

### 🏠 実装内容

#### 1. Secrets Managerからトークン取得（グローバル初期化）

```python
region = os.environ.get("AWS_REGION", "ap-northeast-1")
secret_name = os.environ.get("SECRET_NAME", "linebot/credentials")
secrets_client = boto3.client('secretsmanager', region_name=region)
secret = secrets_client.get_secret_value(SecretId=secret_name)
LINE_ACCESS_TOKEN = json.loads(secret['SecretString'])['LINE_ACCESS_TOKEN']
```

### 2.  請求書風メッセージ作成

```python
# ───────────────────────────────────
# 請求書風メッセージを作成する関数
# ───────────────────────────────────
def build_invoice_message(billing_month: str, total: float, breakdown: list[tuple[str, float]]) -> str:
    """
    請求書スタイルでメッセージを組み立て（セパレータ幅は固定）
    """
    fixed_width = 13  # 固定幅

    sep = "─" * fixed_width
    header = [
        f"【請求期間】",
        f"{billing_month}",
        f"",
        f"【合計金額】",
        f"${total:.2f}"
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
```

---

#### 3. 【メインLambdaハンドラー】Webhookリクエスト受信とreplyToken抽出

```python
# ───────────────────────────────────
# メインLambdaハンドラー
# ───────────────────────────────────
def lambda_handler(event, context):
    try:
        # webhookリクエスト受信とreplytoken抽出
        body = json.loads(event["body"])
        reply_token = body["events"][0]["replyToken"]

        # Cost Explorer API 呼び出し
        ce = boto3.client("ce", region_name="us-east-1")  # Cost Explorerはus-east-1固定
        today = datetime.today()
        start_date = today.replace(day=1).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        billing_month = today.strftime("%Y年%m月分")

        # 合計コスト取得
        total_cost_data = ce.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["BlendedCost"]
        )
        amount = float(total_cost_data["ResultsByTime"][0]["Total"]["BlendedCost"]["Amount"])

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
        invoice_text = build_invoice_message(billing_month, amount, services)

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

```

---

### 📄 請求書メッセージ例（LINE返信形式）

![](https://storage.googleapis.com/zenn-user-upload/a960c2fa7040-20250430.png =500x)
*LINEのスタイルに「おいしい牛乳」を使用しているため、「乳」がはみでてしまっています。お気になさらずに*

---

### ✅ 修正履歴まとめ

| 日付       | 項目               | 内容                                          |
| ---------- | ------------------ | --------------------------------------------- |
| 2025/04/28 | 初版作成 | コード及び環境の構築、ドキュメント作成        |
| 2025/04/30 | 請求書関数改善 | セパレーター固定、サービス略称表示の導入      |
| 2025/04/30 | 内訳抽出処理追加 | GroupBy=SERVICE による上位5件取得を実装       |
| 2025/04/30 | `us-east-1` 明示 | Cost Explorerはこのリージョン固定のため明示化 |
| 2025/04/30 | コード整理 | グローバル変数と関数の明確な分離・簡潔化      |
| 2025/05/02 | ドキュメント編集 | 技術概要を編集 |
