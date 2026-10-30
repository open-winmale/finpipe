"""共享假客户端：单源自包内演示客户端（wmshare._demo.demo_client），示例测试端到端跑 main(cli)。

罐头值一律基础单位口径（率/分位=小数、金额=元、量=股），与真实返回同构——
示例测试因此同时是「返回长这样」的可执行文档；README 首跑演示块也用同一个
真实 DemoClient 执行（零凭证、不联网）。签名校验由 test_docs 的 AST 门禁负责。
"""
from __future__ import annotations

from wmshare._demo import demo_client


def fake_client():
    """覆盖全部示例 cli.* 调用面的演示客户端（离线罐头数据，非真实行情）。"""
    return demo_client()
