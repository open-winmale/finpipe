"""错误处理：按错误分类做不同处理（离线演示，不产生真实请求）。

finpipe 的所有异常都继承 FinPipeError，带 `code`（机器可读）与 HTTP `status`：
    AuthError      凭证无效 / 过期        → 检查 FINPIPE_CLIENT_ID / SECRET
    LimitError     额度或区间超限          → 缩小区间 / 调 max_limit / 稍后重试
    UsageError     参数用法错误           → 按提示修参数
    CatalogError   目录合同错误（未知函数/指标）→ cat.search() 查正确名字
    ServerError    服务端错误             → 退避重试
    TransportError 网络层错误             → 检查网络 / 代理

    python examples/error_handling.py
"""
from finpipe import (
    AuthError, CatalogError, Client, FinPipeError, LimitError, UsageError,
    load,
)


def safe_call(label: str, fn, *args, **kwargs):
    """统一捕获：分类处理，演示生产代码的推荐写法。"""
    try:
        result = fn(*args, **kwargs)
        print(f"[ok] {label}: {str(result)[:60]}")
        return result
    except AuthError as e:
        print(f"[auth] {label}: 凭证问题（code={e.code}）→ 检查环境变量或重新注册")
    except LimitError as e:
        print(f"[limit] {label}: 超限（code={e.code}）→ 缩小区间或调 max_limit：{e}")
    except UsageError as e:
        print(f"[usage] {label}: 参数错误（code={e.code}）→ {e}")
    except CatalogError as e:
        print(f"[catalog] {label}: 目录合同错误（code={e.code}）→ {e}")
    except FinPipeError as e:
        print(f"[error] {label}: code={e.code} status={getattr(e, 'status', None)} → {e}")


def main() -> None:
    cat = load()

    # 1) 目录防编造：未知指标在发出请求前就被拦下（CatalogError）
    cli = Client.from_env()
    safe_call("未知指标", cli.indicator.get, "600519", "$NOT_A_REAL_METRIC")

    # 2) 先查目录再调用——避免 CatalogError 的推荐姿势
    hits = cat.search("yield_ttm", kind="function")
    print(f"\n先查目录：{[h['name'] for h in hits]}")
    if hits:
        safe_call("TTM 股息率", cli.dividend.yield_ttm, "600519")

    # 3) 参数用法错误（UsageError）：窗口 token 拼错会显式报错，不会静默按 30 天算
    from finpipe.api import _window_days
    safe_call("未知窗口", _window_days, "2w")

    # 4) 区间超限（LimitError）：单次区间上限 5 年
    from finpipe.api import _range_bounds
    safe_call("区间超限", _range_bounds, "2010-01-01", "2026-01-01")

    print("\n提示：AuthError / LimitError / ServerError 的真实触发需要在有额度约束的"
          "\n环境中调用；生产代码建议对 FinPipeError 统一兜底并记录 e.code。")


if __name__ == "__main__":
    main()
