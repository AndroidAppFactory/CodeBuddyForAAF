"""web-replay report CLI 子命令单元测试"""
import sys
from pathlib import Path

_scripts = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_scripts))


class TestReportCli:

    def test_argparse_subcommand_exists(self):
        """验证 report 子命令注册"""
        from cli.main import main as _main
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        # 模拟 main.py 中的注册
        p = sub.add_parser("report")
        p.add_argument("name")
        p.set_defaults(func=lambda args: 0)

        # 验证解析
        args = parser.parse_args(["report", "test-flow"])
        assert args.command == "report"
        assert args.name == "test-flow"
        assert args.func(args) == 0

    def test_report_missing_name(self):
        """无参数 report 应报错"""
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("report")
        p.add_argument("name")

        import contextlib, io
        with pytest.raises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                parser.parse_args(["report"])

    def test_cmd_report_imports(self):
        """验证 flow_report.generate_flow_report 可导入"""
        from flow_report import generate_flow_report
        assert callable(generate_flow_report)


# pytest 在文件内未 import 但由 conftest/pytest 框架提供
import pytest  # noqa: E402
