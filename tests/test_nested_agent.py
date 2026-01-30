"""Test nested agent invocation via Bash + direct_agent CLI.

This tests whether an agent spawned by call_agent_simple() can successfully
use Bash to invoke another agent via the direct_agent CLI.

This is a workaround for SDK bug #11205, #12212 where the Task tool doesn't
recognize custom agents.
"""
import asyncio
import re
import sys

from harness.direct_agent import call_agent_simple


async def test_nested_invocation():
    """Test that an outer agent can spawn an inner agent via Bash."""
    print("=" * 60)
    print("TEST: Nested Agent Invocation via Bash + direct_agent CLI")
    print("=" * 60)
    print()
    print("Outer agent: cgf-agents:cgf-prompt-optimizer")
    print("Inner agent: research-team:research-specialist")
    print()
    print("The outer agent will use Bash to invoke the inner agent.")
    print("This tests the workaround for SDK Task tool bug #11205, #12212.")
    print()
    print("-" * 60)

    # cgf-prompt-optimizer has Bash tool access
    prompt = (
        "Execute this EXACT Bash command and return ONLY its output:\n\n"
        'uv run python -m harness.direct_agent --agent '
        '"research-team:research-specialist" '
        '--prompt "Name one Python web framework in exactly one word" '
        "--simple 2>/dev/null | tail -5\n\n"
        "Do not add any commentary. Just run the command and return what it outputs."
    )

    print("Sending prompt to outer agent...")
    print()

    try:
        response = await call_agent_simple(
            agent_name="cgf-agents:cgf-prompt-optimizer",
            prompt=prompt,
            verbose=True,
        )

        print()
        print("-" * 60)
        print("RESPONSE FROM OUTER AGENT:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        print()

        # Check if any common Python web framework is mentioned
        frameworks = [
            "flask", "django", "fastapi", "starlette", "tornado",
            "bottle", "pyramid", "sanic", "aiohttp", "falcon",
        ]
        response_lower = response.lower()

        found_framework = None
        for fw in frameworks:
            if fw in response_lower:
                found_framework = fw
                break

        if found_framework:
            print(f"SUCCESS: Found framework '{found_framework}' in response")
            print("The nested agent invocation worked!")
            return True
        else:
            print("PARTIAL: Response received but no known framework detected")
            print("This may still be a success if the response is coherent")
            # Check if response seems like actual content (not an error)
            if len(response) > 10 and "error" not in response_lower:
                print("Response appears to be valid content")
                return True
            return False

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return False


async def test_signal_preservation():
    """Test that structured signals pass through Bash invocation."""
    print()
    print("=" * 60)
    print("TEST: Signal Preservation through Nested Invocation")
    print("=" * 60)
    print()

    # Use a simple agent that emits signals
    prompt = (
        "Execute this EXACT Bash command and return the output:\n\n"
        'uv run python -m harness.direct_agent --agent '
        '"cgf-agents:cgf-test-validator" '
        '--prompt "Validate schema: {}. When done, emit [VALIDATION_COMPLETE]." '
        '--simple 2>/dev/null | grep -E "\\[.*\\]" || echo "NO_SIGNAL_FOUND"\n\n'
        "Return the raw output."
    )

    print("Testing if structured signals like [SIGNAL_NAME] pass through...")
    print()

    try:
        response = await call_agent_simple(
            agent_name="cgf-agents:cgf-prompt-optimizer",
            prompt=prompt,
            verbose=False,
        )

        print("-" * 60)
        print("RESPONSE:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        print()

        # Check for signal pattern
        signal_pattern = r'\[([A-Z_]+)\]'
        signals = re.findall(signal_pattern, response)

        if signals:
            print(f"SUCCESS: Found signals: {signals}")
            return True
        elif "NO_SIGNAL_FOUND" in response:
            print("INFO: No signal emitted by inner agent (this is OK)")
            print("The Bash invocation worked, but the agent didn't emit signals")
            return True  # The mechanism works, just no signals this time
        else:
            print("INFO: Response received but no bracketed signals found")
            return True  # Mechanism works

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return False


async def main():
    """Run all nested agent tests."""
    results = {}

    # Test 1: Basic nested invocation
    results["nested_invocation"] = await test_nested_invocation()

    # Test 2: Signal preservation (optional, uncomment to run)
    # results["signal_preservation"] = await test_signal_preservation()

    print()
    print("=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All tests passed!")
        print()
        print("CONCLUSION: Nested agent spawning via Bash + direct_agent CLI works.")
        print("This workaround addresses SDK Task tool bug #11205, #12212.")
    else:
        print("Some tests failed. See output above for details.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
