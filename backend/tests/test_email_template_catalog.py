from app.services.email_templates import DEFAULT_EMAIL_TEMPLATES


def test_mock_email_catalog_includes_campaign_training_presets():
    expected_keys = {
        "mock_phishing",
        "account_notice",
        "invoice_review",
        "shared_document",
        "delivery_notice",
        "payroll_update",
        "security_policy_reminder",
        "cloud_storage_alert",
        "benefits_enrollment",
        "travel_reimbursement",
        "shared_drive_access",
    }

    assert expected_keys.issubset(DEFAULT_EMAIL_TEMPLATES)
    for key in expected_keys:
        template = DEFAULT_EMAIL_TEMPLATES[key]
        assert template["name"]
        assert template["subject"]
        assert template["body_text"]
        assert template["body_html"]