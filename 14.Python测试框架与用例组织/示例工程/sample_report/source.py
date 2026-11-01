"""公开的教学读取接口，测试通过替身提供数据。"""


def read_label(case_id: str) -> dict[str, str]:
    raise RuntimeError("教学接口没有真实数据源，请注入测试替身")
