"""Tests for HudLocalService port contract — 验证端口防泄漏契约.

对标 design.md Decision 1 — Port Anti-Leakage。

验证:
- HudLocalService 是 HudServiceProtocol 的运行时实例 (isinstance check)
- 所有返回值均为纯 dict / list[dict]，不含 HudState 枚举、QWidget 等领域对象
- transition_to() 将内部 IllegalTransitionError 包装为 ValueError（外部永远不见内部异常类型）
- list_plugins() 返回结构化 list[dict]
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication
import sys

# 必须在任何 Qt 对象之前创建 QApplication
_app = QApplication.instance() or QApplication(sys.argv)

from flow_hud.core.app import HudApp
from flow_hud.core.config import HudConfig
from flow_hud.core.service import HudLocalService, HudServiceProtocol
from flow_hud.adapters.debug_text_plugin import DebugTextPlugin


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hud_app():
    """创建一个干净的 HudApp 实例（safe_mode，不扫描 entry_points）。"""
    config = HudConfig(safe_mode=False)
    app = HudApp(config=config)
    yield app
    app.shutdown()


@pytest.fixture
def service(hud_app):
    """创建 HudLocalService。"""
    return HudLocalService(hud_app)


# ---------------------------------------------------------------------------
# 端口契约协议测试
# ---------------------------------------------------------------------------

class TestHudServiceProtocol:
    def test_local_service_is_instance_of_protocol(self, service):
        """HudLocalService 必须通过 isinstance(service, HudServiceProtocol) 检查。"""
        assert isinstance(service, HudServiceProtocol)

    def test_protocol_has_required_methods(self):
        """HudServiceProtocol 必须声明全部 4 个契约方法。"""
        for method_name in ["get_status", "transition_to", "register_widget", "list_plugins"]:
            assert hasattr(HudServiceProtocol, method_name), f"Missing method: {method_name}"


# ---------------------------------------------------------------------------
# get_status — 纯 dict 返回测试
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_returns_dict(self, service):
        result = service.get_status()
        assert isinstance(result, dict)

    def test_state_is_string(self, service):
        result = service.get_status()
        assert "state" in result
        assert isinstance(result["state"], str), "state must be a plain str, not HudState enum"

    def test_initial_state_is_ghost(self, service):
        result = service.get_status()
        assert result["state"] == "ghost"

    def test_contains_extra_fields(self, service):
        result = service.get_status()
        assert "safe_mode" in result
        assert "data_dir" in result
        assert isinstance(result["safe_mode"], bool)
        assert isinstance(result["data_dir"], str)

    def test_active_plugins_is_list_of_strings(self, service):
        result = service.get_status()
        assert "active_plugins" in result
        assert isinstance(result["active_plugins"], list)
        for item in result["active_plugins"]:
            assert isinstance(item, str), "active_plugins items must be plain strings"

    def test_no_domain_objects_in_return(self, service):
        """返回值中不得包含 HudState 枚举或任何域对象。"""
        from flow_hud.core.state_machine import HudState
        result = service.get_status()

        # 递归检查：没有任何值是 HudState 实例
        def has_domain_obj(val):
            if isinstance(val, HudState):
                return True
            if isinstance(val, dict):
                return any(has_domain_obj(v) for v in val.values())
            if isinstance(val, (list, tuple)):
                return any(has_domain_obj(v) for v in val)
            return False

        assert not has_domain_obj(result), "get_status() returned an internal domain object!"


# ---------------------------------------------------------------------------
# transition_to — 状态转换 + 错误包装测试
# ---------------------------------------------------------------------------

class TestTransitionTo:
    def test_valid_transition_returns_dict(self, service):
        result = service.transition_to("pulse")
        assert isinstance(result, dict)
        assert result["old_state"] == "ghost"
        assert result["new_state"] == "pulse"

    def test_old_and_new_state_are_strings(self, service):
        result = service.transition_to("pulse")
        assert isinstance(result["old_state"], str)
        assert isinstance(result["new_state"], str)

    def test_invalid_target_raises_value_error(self, service):
        """非法目标状态应抛出 ValueError，而非 IllegalTransitionError（内部实现细节不泄漏）。"""
        with pytest.raises(ValueError) as exc_info:
            service.transition_to("flying")
        # 错误信息应提示合法选项
        assert "flying" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower() or "无效" in str(exc_info.value)

    def test_illegal_transition_raises_value_error_not_domain_error(self, service):
        """非法状态跳转应被包装为 ValueError，外部不可见 IllegalTransitionError 实现。"""
        from flow_hud.core.state_machine import IllegalTransitionError
        # GHOST 不能直接到 COMMAND  
        with pytest.raises(ValueError) as exc_info:
            service.transition_to("command")
        # 错误类型必须是 ValueError（领域异常类型不泄漏）
        assert type(exc_info.value) is ValueError

    def test_transition_updates_state(self, service):
        service.transition_to("pulse")
        state_after = service.get_status()
        assert state_after["state"] == "pulse"


# ---------------------------------------------------------------------------
# register_widget — 纯 dict 返回
# ---------------------------------------------------------------------------

class TestRegisterWidget:
    def test_returns_dict(self, service):
        result = service.register_widget("test-widget", "top_right")
        assert isinstance(result, dict)

    def test_echoes_name_and_slot(self, service):
        result = service.register_widget("my-widget", "center")
        assert result["name"] == "my-widget"
        assert result["slot"] == "center"

    def test_registered_is_bool(self, service):
        result = service.register_widget("x", "y")
        assert isinstance(result["registered"], bool)


# ---------------------------------------------------------------------------
# list_plugins — list[dict] 返回
# ---------------------------------------------------------------------------

class TestListPlugins:
    def test_returns_list(self, service):
        result = service.list_plugins()
        assert isinstance(result, list)

    def test_each_element_is_dict(self, service, hud_app):
        # 注册一个插件
        plugin = DebugTextPlugin()
        hud_app.plugins.register(plugin)

        result = service.list_plugins()
        for item in result:
            assert isinstance(item, dict)

    def test_each_dict_has_required_keys(self, service, hud_app):
        plugin = DebugTextPlugin()
        hud_app.plugins.register(plugin)

        result = service.list_plugins()
        for item in result:
            assert "name" in item
            assert "version" in item
            assert "description" in item

    def test_all_values_are_primitive(self, service, hud_app):
        """list_plugins 返回值中不得有任何非基础类型。"""
        plugin = DebugTextPlugin()
        hud_app.plugins.register(plugin)

        result = service.list_plugins()
        for item in result:
            for k, v in item.items():
                assert isinstance(v, (str, int, float, bool, list, dict, type(None))), \
                    f"Non-primitive value in list_plugins: {k}={v!r}"
