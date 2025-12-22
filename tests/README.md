# ANTS Test Suite

Comprehensive testing for the AI-Agent Native Tactical System (ANTS).

## Test Structure

```
tests/
├── unit/              # Unit tests for individual components
├── integration/       # Integration tests for component interactions
├── e2e/              # End-to-end workflow tests
├── policy/           # OPA policy tests
└── fixtures/         # Shared test fixtures
```

## Test Categories

### Unit Tests
- Individual function and class testing
- Mocked dependencies
- Fast execution (<1s per test)
- Run continuously during development

### Integration Tests
- Multi-component testing
- Real database connections (test DB)
- Moderate execution time (1-10s per test)
- Run before commits

**Key Integration Tests:**
- `test_data_pipeline.py`: Bronze→Silver→Gold pipeline
- `test_agent_framework.py`: Agent lifecycle, memory, orchestration
- `test_api_gateway.py`: Authentication, authorization, rate limiting

### E2E Tests
- Complete workflow testing
- Full stack integration
- Slower execution (10s-60s per test)
- Run before releases

**Key E2E Scenarios:**
- Financial reconciliation workflow
- Security incident response
- Multi-agent collaboration
- Agent sleep/wake lifecycle
- GDPR compliance
- Cost optimization validation

### Policy Tests
- OPA/Rego policy validation
- Test policy decisions across scenarios
- Fast execution
- Run with every policy change

## Running Tests

### All Tests
```bash
pytest tests/
```

### Unit Tests Only
```bash
pytest tests/unit/
```

### Integration Tests
```bash
pytest tests/integration/
```

### E2E Tests
```bash
pytest tests/e2e/ -m e2e
```

### Specific Test File
```bash
pytest tests/integration/test_data_pipeline.py -v
```

### With Coverage
```bash
pytest tests/ --cov=src --cov=data --cov=services --cov-report=html
```

### Slow Tests (Performance)
```bash
pytest tests/ -m slow
```

## Test Markers

- `@pytest.mark.e2e`: End-to-end tests
- `@pytest.mark.slow`: Long-running tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.policy`: Policy tests

## Test Requirements

### Prerequisites
```bash
pip install -r requirements-test.txt
```

Required packages:
- pytest>=7.4.0
- pytest-asyncio>=0.21.0
- pytest-cov>=4.1.0
- pytest-mock>=3.11.0
- httpx>=0.24.0
- faker>=19.0.0

### Test Database Setup

For integration tests, you need a PostgreSQL test database:

```bash
# Create test database
createdb ants_test

# Run migrations
python scripts/migrate.py --env test

# Install pgvector extension
psql ants_test -c "CREATE EXTENSION vector;"
```

### Spark Setup

For data pipeline tests, ensure Spark is configured:

```bash
# Install PySpark with Delta Lake
pip install pyspark[sql]==3.5.0
pip install delta-spark==3.0.0
```

## Test Data

### Fixtures
Common fixtures are defined in `tests/conftest.py`:
- `db_client`: Test database connection
- `spark_session`: Spark session for pipeline tests
- `temp_lakehouse`: Temporary directory structure
- `auth_service`: Authentication service
- `agent_registry`: Agent registry

### Sample Data
Sample datasets are in `tests/fixtures/`:
- `sample_transactions.json`: Transaction records
- `sample_agents.json`: Agent configurations
- `sample_policies.rego`: Test policies

## Continuous Integration

Tests run automatically on:
- Pull requests (unit + integration)
- Main branch commits (all tests)
- Release tags (all tests + E2E)

### GitHub Actions Workflow
```yaml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest tests/ --cov --junitxml=test-results.xml
```

## Performance Benchmarks

Expected test execution times:
- Unit tests: <30 seconds total
- Integration tests: <5 minutes total
- E2E tests: <10 minutes total
- Full suite: <15 minutes

## Test Coverage Goals

Target coverage by component:
- Core agent framework: >90%
- Memory substrate: >85%
- Policy engine: >95%
- Data pipeline: >80%
- API gateway: >85%
- MCP servers: >75%

## Writing New Tests

### Test Naming Convention
```python
def test_<component>_<action>_<expected_result>():
    """Test that <component> <action> results in <expected_result>."""
    pass
```

### Async Tests
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result is not None
```

### Parametrized Tests
```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6)
])
def test_doubles_input(input, expected):
    assert double(input) == expected
```

## Policy Testing

Test OPA policies using the OPA test framework:

```bash
# Test all policies
opa test platform/policies/ants/ tests/policy/

# Test specific policy
opa test platform/policies/ants/financial_controls.rego tests/policy/test_financial_controls.rego
```

## Troubleshooting

### Database Connection Errors
```bash
# Check PostgreSQL is running
pg_isready

# Verify test database exists
psql -l | grep ants_test
```

### Spark Errors
```bash
# Verify PySpark installation
python -c "import pyspark; print(pyspark.__version__)"

# Check Java version (required for Spark)
java -version
```

### Import Errors
```bash
# Install package in editable mode
pip install -e .
```

## Test Maintenance

- Run full suite before major releases
- Update fixtures when schema changes
- Review and update test coverage quarterly
- Archive obsolete tests
- Keep test execution time under 15 minutes

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [OPA Testing](https://www.openpolicyagent.org/docs/latest/policy-testing/)
- [PySpark Testing Best Practices](https://spark.apache.org/docs/latest/api/python/getting_started/testing_pyspark.html)
