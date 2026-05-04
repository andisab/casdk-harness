"""Unit tests for agent definitions."""


from harness.agents.definitions import (
    AGENT_DEFINITIONS,
    AgentDefinition,
    get_agent_definition,
    get_agents_by_model,
    list_agents,
)


class TestAgentDefinition:
    """Tests for AgentDefinition dataclass."""

    def test_create_agent_definition(self) -> None:
        """Test creating an agent definition."""
        agent = AgentDefinition(
            name="test-agent",
            description="Test agent for testing",
            model="sonnet",
            tools=["Read", "Write"],
            system_prompt="You are a test agent.",
            max_turns=50,
        )

        assert agent.name == "test-agent"
        assert agent.description == "Test agent for testing"
        assert agent.model == "sonnet"
        assert "Read" in agent.tools
        assert agent.max_turns == 50

    def test_default_max_turns(self) -> None:
        """Test default max_turns value."""
        agent = AgentDefinition(
            name="test",
            description="Test",
            model="sonnet",
            tools=[],
            system_prompt="Test",
        )

        assert agent.max_turns == 100  # Default


class TestAgentRegistry:
    """Tests for agent registry functions."""

    def test_get_agent_definition_exists(self) -> None:
        """Test getting an existing agent definition."""
        agent = get_agent_definition("python-expert")

        assert agent is not None
        assert agent.name == "python-expert"
        assert "python" in agent.description.lower()

    def test_get_agent_definition_not_exists(self) -> None:
        """Test getting a nonexistent agent definition."""
        agent = get_agent_definition("nonexistent-agent")
        assert agent is None

    def test_list_agents(self) -> None:
        """Test listing all agent names."""
        agents = list_agents()

        assert len(agents) > 0
        assert "python-expert" in agents
        assert "tech-lead" in agents
        assert "sdet-expert" in agents

    def test_get_agents_by_model(self) -> None:
        """Test filtering agents by model."""
        sonnet_agents = get_agents_by_model("sonnet")
        haiku_agents = get_agents_by_model("haiku")

        assert len(sonnet_agents) > 0
        assert len(haiku_agents) > 0

        for agent in sonnet_agents:
            assert agent.model == "sonnet"

        for agent in haiku_agents:
            assert agent.model == "haiku"


class TestPredefinedAgents:
    """Tests for predefined agent definitions."""

    def test_tech_lead_agent(self) -> None:
        """Test tech lead agent configuration."""
        agent = get_agent_definition("tech-lead")

        assert agent is not None
        assert "Bash" in agent.tools
        assert "Read" in agent.tools
        assert agent.max_turns >= 50

    def test_python_expert_agent(self) -> None:
        """Test Python expert agent configuration."""
        agent = get_agent_definition("python-expert")

        assert agent is not None
        assert "python" in agent.description.lower()
        assert "Bash" in agent.tools
        assert "Write" in agent.tools
        assert "Read" in agent.tools

    def test_typescript_expert_agent(self) -> None:
        """Test TypeScript expert agent configuration."""
        agent = get_agent_definition("typescript-expert")

        assert agent is not None
        assert "typescript" in agent.description.lower()
        assert "Bash" in agent.tools

    def test_testing_agent(self) -> None:
        """Test testing agent configuration."""
        agent = get_agent_definition("sdet-expert")

        assert agent is not None
        assert agent.model == "haiku"  # Should use cheaper model
        assert "test" in agent.description.lower()

    def test_code_review_expert(self) -> None:
        """Test code review expert agent configuration."""
        agent = get_agent_definition("code-review-expert")

        assert agent is not None
        assert "review" in agent.description.lower()
        # Code review agent should have read-only tools (no Write/Edit)
        assert "Read" in agent.tools
        assert "Write" not in agent.tools
        assert "Edit" not in agent.tools


class TestAgentToolSets:
    """Tests for agent tool configurations."""

    def test_all_agents_have_required_fields(self) -> None:
        """Test all agents have required fields populated."""
        for name, agent in AGENT_DEFINITIONS.items():
            assert agent.name == name, f"Agent {name} has mismatched name"
            assert len(agent.description) > 0, f"Agent {name} missing description"
            assert agent.model in ["sonnet", "opus", "haiku"], f"Agent {name} has invalid model"
            assert len(agent.tools) > 0, f"Agent {name} has no tools"
            assert len(agent.system_prompt) > 0, f"Agent {name} missing system prompt"
            assert agent.max_turns > 0, f"Agent {name} has invalid max_turns"

    def test_no_duplicate_agent_names(self) -> None:
        """Test there are no duplicate agent names."""
        names = list_agents()
        assert len(names) == len(set(names)), "Duplicate agent names found"

    def test_expensive_models_justified(self) -> None:
        """Test that expensive models (sonnet, opus) are used for complex tasks."""
        for name, agent in AGENT_DEFINITIONS.items():
            if agent.model in ["sonnet", "opus"]:
                # Should have significant tools or complex description
                has_write_access = any(
                    tool in agent.tools
                    for tool in ["Write", "Edit", "MultiEdit"]
                )
                has_many_tools = len(agent.tools) >= 3
                assert (
                    has_write_access or has_many_tools
                ), f"Agent {name} uses expensive model without complex requirements"
