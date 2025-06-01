from service_map import SERVICE_NAME_MAP
from typing import List, Tuple

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
