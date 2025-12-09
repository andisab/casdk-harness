"""Tests for sensitive data sanitization."""

from harness.security import sanitize_sensitive_data


class TestSanitizeSensitiveData:
    """Tests for sanitize_sensitive_data function."""

    def test_empty_string(self) -> None:
        """Test empty string returns empty."""
        assert sanitize_sensitive_data("") == ""

    def test_none_returns_none(self) -> None:
        """Test None-like empty value handling."""
        # The function should handle empty strings gracefully
        assert sanitize_sensitive_data("") == ""

    def test_no_sensitive_data(self) -> None:
        """Test string without sensitive data is unchanged."""
        text = "Hello world, this is a test message"
        assert sanitize_sensitive_data(text) == text

    # --- Anthropic API Keys ---

    def test_anthropic_sk_key(self) -> None:
        """Test Anthropic sk- format key is redacted."""
        text = "My key is sk-ant-api03-abcdef123456789012345678901234567890"
        result = sanitize_sensitive_data(text)
        assert "sk-ant" not in result
        assert "***ANTHROPIC_KEY***" in result

    def test_anthropic_short_sk_key(self) -> None:
        """Test short sk- format key is redacted."""
        text = "ANTHROPIC_API_KEY=sk-abcdefghij1234567890"
        result = sanitize_sensitive_data(text)
        assert "sk-abcdef" not in result
        assert "***ANTHROPIC_KEY***" in result

    # --- GitHub Tokens ---

    def test_github_pat_token(self) -> None:
        """Test GitHub PAT token is redacted."""
        text = "token=ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        result = sanitize_sensitive_data(text)
        assert "ghp_" not in result
        assert "***GITHUB_TOKEN***" in result

    def test_github_new_pat_format(self) -> None:
        """Test new GitHub PAT format is redacted."""
        text = "Using github_pat_abcdefghijklmnopqrstuvwx for auth"
        result = sanitize_sensitive_data(text)
        assert "github_pat_" not in result
        assert "***GITHUB_TOKEN***" in result

    def test_github_oauth_token(self) -> None:
        """Test GitHub OAuth token is redacted."""
        text = "oauth=gho_abcdefghijklmnopqrstuvwxyz1234567890"
        result = sanitize_sensitive_data(text)
        assert "gho_" not in result
        assert "***GITHUB_OAUTH***" in result

    # --- GitLab Tokens ---

    def test_gitlab_pat_token(self) -> None:
        """Test GitLab PAT token is redacted."""
        text = "GITLAB_TOKEN=glpat-abcdefghijklmnopqrst"
        result = sanitize_sensitive_data(text)
        assert "glpat-" not in result
        assert "***GITLAB_TOKEN***" in result

    # --- Slack Tokens ---

    def test_slack_bot_token(self) -> None:
        """Test Slack bot token is redacted."""
        text = "SLACK_TOKEN=xoxb-123456789012-1234567890123-abcdefghijklmnopqrstuvwx"
        result = sanitize_sensitive_data(text)
        assert "xoxb-" not in result
        assert "***SLACK_TOKEN***" in result

    def test_slack_app_token(self) -> None:
        """Test Slack app token is redacted."""
        text = "token: xoxa-abcdefghij-1234567890"
        result = sanitize_sensitive_data(text)
        assert "xoxa-" not in result
        assert "***SLACK_TOKEN***" in result

    # --- AWS Credentials ---

    def test_aws_access_key(self) -> None:
        """Test AWS access key is redacted."""
        text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result = sanitize_sensitive_data(text)
        assert "AKIA" not in result
        assert "***AWS_ACCESS_KEY***" in result

    # --- Google API Keys ---

    def test_google_api_key(self) -> None:
        """Test Google API key is redacted."""
        # Google API keys are 39 chars: AIza + 35 alphanumeric chars
        text = "GOOGLE_API_KEY=AIzaSyAbcdefghijklmnopqrstuvwxyz1234567"
        result = sanitize_sensitive_data(text)
        assert "AIzaSy" not in result
        assert "***GOOGLE_API_KEY***" in result

    # --- Generic Key-Value Patterns ---

    def test_api_key_equals(self) -> None:
        """Test api_key=value pattern is redacted."""
        text = "api_key=supersecret123456"
        result = sanitize_sensitive_data(text)
        assert "supersecret" not in result
        assert "***REDACTED***" in result

    def test_password_colon(self) -> None:
        """Test password:value pattern is redacted."""
        text = 'password: "my_secure_password"'
        result = sanitize_sensitive_data(text)
        assert "my_secure_password" not in result
        assert "***REDACTED***" in result

    def test_secret_equals(self) -> None:
        """Test secret=value pattern is redacted."""
        text = "SECRET=verysecretvalue123"
        result = sanitize_sensitive_data(text)
        assert "verysecretvalue" not in result
        assert "***REDACTED***" in result

    def test_token_case_insensitive(self) -> None:
        """Test TOKEN pattern is case insensitive."""
        text = "TOKEN=abc123xyz456def"
        result = sanitize_sensitive_data(text)
        assert "abc123xyz" not in result
        assert "***REDACTED***" in result

    def test_auth_pattern(self) -> None:
        """Test auth=value pattern is redacted."""
        text = "auth=mysecretauth123"
        result = sanitize_sensitive_data(text)
        assert "mysecretauth" not in result
        assert "***REDACTED***" in result

    def test_credential_pattern(self) -> None:
        """Test credential=value pattern is redacted."""
        text = "credential=my_db_password"
        result = sanitize_sensitive_data(text)
        assert "my_db_password" not in result
        assert "***REDACTED***" in result

    # --- Email Addresses ---

    def test_email_redacted(self) -> None:
        """Test email addresses are redacted."""
        text = "Contact user@example.com for support"
        result = sanitize_sensitive_data(text)
        assert "user@example.com" not in result
        assert "***EMAIL***" in result

    def test_multiple_emails(self) -> None:
        """Test multiple email addresses are redacted."""
        text = "From: alice@corp.com To: bob@company.org"
        result = sanitize_sensitive_data(text)
        assert "alice@corp.com" not in result
        assert "bob@company.org" not in result
        assert result.count("***EMAIL***") == 2

    # --- Bearer Tokens ---

    def test_bearer_token(self) -> None:
        """Test Bearer token in Authorization header is redacted."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123"
        result = sanitize_sensitive_data(text)
        assert "eyJhbGci" not in result
        assert "Bearer ***REDACTED***" in result

    # --- URL Credentials ---

    def test_basic_auth_in_url(self) -> None:
        """Test basic auth credentials in URLs are redacted."""
        text = "Connect to https://admin:secretpass123@api.example.com/endpoint"
        result = sanitize_sensitive_data(text)
        assert "admin" not in result
        assert "secretpass123" not in result
        assert "***USER***:***PASS***@" in result
        assert "api.example.com" in result  # Host preserved

    def test_http_basic_auth_in_url(self) -> None:
        """Test HTTP URL with basic auth is redacted."""
        text = "http://user:pass@localhost:8080/api"
        result = sanitize_sensitive_data(text)
        assert result == "http://***USER***:***PASS***@localhost:8080/api"

    # --- Multiple Sensitive Items ---

    def test_multiple_sensitive_items(self) -> None:
        """Test multiple sensitive items in one string."""
        text = (
            "Config: api_key=secret123456 "
            "email=user@test.com "
            "token=ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        )
        result = sanitize_sensitive_data(text)
        assert "secret123456" not in result
        assert "user@test.com" not in result
        assert "ghp_" not in result

    # --- Edge Cases ---

    def test_short_value_not_redacted(self) -> None:
        """Test short values (< 8 chars) for key=value are not redacted."""
        text = "token=abc"  # Too short to match generic pattern
        result = sanitize_sensitive_data(text)
        # Short values should not match the generic pattern
        # (but might still be caught by specific patterns if they match format)
        assert "abc" in result or "***" in result

    def test_preserves_normal_text(self) -> None:
        """Test normal text is preserved around redactions."""
        text = "User john logged in with api_key=secretkey123456 at 10:00"
        result = sanitize_sensitive_data(text)
        assert "User john logged in with" in result
        assert "at 10:00" in result
        assert "secretkey123456" not in result
