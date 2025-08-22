from mcp.types import GetPromptResult


def get_vm_from_network(network: str) -> GetPromptResult:
    """指定したグローバルネットワークに属するVMを検索します。"""

    return [
        {
            "role": "user",
            "content": f"""
・IPAddressをAdvancedSearchで次の条件で検索してください。Networkに{network}が設定されている。
・LBVirtualServerをAdvancedSearchで次の条件で検索してください。LBServiceGroupに値が設定されている。IPアドレスに上記IPAddressの検索結果のIPをパイプでOR検索。
・LBSericeGroupをAdvancedSearchで次の条件で検索してください。LBServerに値が設定されている。アイテム名の絞り込みに上記検索結果のLBServiceGroupをパイプでOR検索。
・LBServerをAdvancedSearchで次の条件で検索してください。IPアドレスに値が設定されている。アイテム名の絞り込みに上記検索結果のLBServerをパイプでOR検索。
・tsuchinoko-vmをAdvancedSearchで次の条件で検索してください。大分類に値が設定されている。IPアドレスに上記LBServerの検索結果のIPをパイプでOR検索。
・上記結果から次のカラムで表を作成してください。グローバルIP、LBVirtualServer、LBServiceGroup、LBServer、プライベートIP、tsuchinoko-vm、大分類
""",
        }
    ]


"""
PROMPT_LB_ROUTERS = {
    "ネットワークに属するVMを調査": PromptHandler(
        handler=get_vm_from_network,
        desc="指定したグローバルネットワークに属するVMを検索します。",
        args=[
            PromptArgument(
                name="network",
                description="例: 1.12.123.0/24",
                required=True,
            )
        ],
    )
}
"""

LB_LIST = [
    ("ネットワークに属するVMを調査", get_vm_from_network),
]
