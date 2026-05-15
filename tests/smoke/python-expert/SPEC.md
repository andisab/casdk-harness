# Smoke: python-expert single-resource optimization

## Resource

- **Type:** agent
- **File:** python-expert.md

## Optimization Goals

- Improve async/await pattern guidance with modern Python 3.12+ features
- Add better error handling examples using exception groups and ExceptionGroup
- Strengthen type hint recommendations with TypedDict and Protocol patterns
- Include practical asyncio.TaskGroup usage examples

## Target Improvements

- [ ] Add async context manager patterns (`async with` best practices)
- [ ] Include exception chaining examples (`raise ... from` patterns)
- [ ] Document Protocol vs ABC tradeoffs for structural typing
- [ ] Add asyncio.TaskGroup examples for concurrent task management
- [ ] Include typing.Self usage for fluent interfaces

## Evaluation Criteria

The optimized resource should demonstrate:

- **Correctness**: Code examples must be syntactically valid and runnable
- **Modernity**: Use Python 3.12+ features where appropriate
- **Completeness**: Cover common async patterns developers encounter
- **Clarity**: Explanations should be concise but comprehensive
- **Best Practices**: Follow PEP 8, type hints, and async conventions

## Constraints

- Do NOT remove existing content that's working well
- Preserve the overall structure and section organization
- Keep code examples under 30 lines each
- Avoid introducing dependencies beyond the standard library

## Success Metrics

| Metric | Target |
|--------|--------|
| Code example validity | 100% syntactically correct |
| Modern feature coverage | At least 5 Python 3.10+ features |
| Example completeness | Each pattern has usage + output |
| Documentation clarity | No ambiguous instructions |
