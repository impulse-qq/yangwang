from kanban_gateway.policy import PolicyEngine, AGENT_POLICY


def test_valid_transition():
    p = PolicyEngine()
    assert p.check_transition("Pending", "Vice") is True
    assert p.check_transition("Strategy", "AuditReview") is True


def test_invalid_transition():
    p = PolicyEngine()
    assert p.check_transition("Doing", "Vice") is False
    assert p.check_transition("Done", "Strategy") is False


def test_agent_permission():
    p = PolicyEngine()
    assert p.check_permission("vice", "create") is True
    assert p.check_permission("finance", "create") is False
    assert p.check_permission("unknown", "create") is True  # forward compat


def test_title_sanitization():
    p = PolicyEngine()
    assert p.sanitize_title("/Users/bingsen/project") == ""
    assert "Conversation" not in p.sanitize_title("Hello\nConversation info")
    assert "https" not in p.sanitize_title("Check https://example.com")


def test_valid_task_title():
    p = PolicyEngine()
    ok, _ = p.validate_task_title("调研工业数据分析方案")
    assert ok is True
    ok2, _ = p.validate_task_title("/Users/bingsen/")
    assert ok2 is False
    ok3, _ = p.validate_task_title("好")
    assert ok3 is False


def test_high_risk_transition():
    p = PolicyEngine()
    assert p.is_high_risk("AuditReview", "Done") is True
    assert p.is_high_risk("Strategy", "AuditReview") is False
