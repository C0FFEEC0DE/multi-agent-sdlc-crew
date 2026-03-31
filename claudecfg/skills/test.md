# /test

Run testing session with the Tester agent.

## When to use
- Need to write tests
- Check existing ones
- Coverage dropped
- Regression

## Usage
```
/test [what to test]
```

## Examples
```
/test the auth module
/test write unit tests for user service
/test check coverage for payment gateway
```

## Agent
Invokes @tester (Paranoid) who will:
1. Analyze what needs testing
2. Write or run Unit → Integration → E2E tests
3. Use AAA pattern (Arrange, Act, Assert)
4. Cover edge cases
5. Report pass/fail, coverage, and gaps

In feature, bugfix, and refactor workflows, use this when successful verification has not already been recorded or when you want an explicit tester handoff anyway.
