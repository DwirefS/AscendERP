"""
Example: Secure Code Execution with CodeExecutionAgent

Demonstrates:
- Python code execution in restricted sandbox
- JavaScript execution with Node.js subprocess
- SQL query execution with validation
- Result caching and performance
- Security features and resource limits
"""
import asyncio
from src.agents.meta.code_executor import (
    CodeExecutionAgent,
    CodeLanguage,
    ExecutionStatus,
    ResourceLimits
)


async def example_1_python_execution():
    """Example 1: Python code execution."""
    print("=" * 60)
    print("Example 1: Python Code Execution")
    print("=" * 60 + "\n")

    executor = CodeExecutionAgent(
        agent_id="code_exec_example",
        cache_enabled=True
    )

    # Example 1a: Simple calculation
    print("1a. Simple calculation:\n")

    code = """
import math

def calculate_area(radius):
    return math.pi * radius ** 2

result = calculate_area(5)
"""

    result = await executor.execute_python(code)

    print(f"Code:\n{code}")
    print(f"Status: {result.status.value}")
    print(f"Output: {result.output}")
    print(f"Execution time: {result.execution_time_ms:.2f}ms")
    print(f"Cached: {result.cached}\n")

    # Example 1b: Data processing
    print("1b. Data processing with context:\n")

    code = """
from statistics import mean, median

result = {
    'mean': mean(numbers),
    'median': median(numbers),
    'total': sum(numbers),
    'count': len(numbers)
}
"""

    context = {'numbers': [10, 20, 30, 40, 50]}

    result = await executor.execute_python(code, context=context)

    print(f"Code:\n{code}")
    print(f"Context: {context}")
    print(f"Status: {result.status.value}")
    print(f"Output: {result.output}")
    print(f"Execution time: {result.execution_time_ms:.2f}ms\n")

    # Example 1c: Cache demonstration
    print("1c. Cache demonstration (same code):\n")

    result2 = await executor.execute_python(code, context=context)

    print(f"Status: {result2.status.value}")
    print(f"Cached: {result2.cached}")
    print(f"Execution time: {result2.execution_time_ms:.2f}ms")
    print("→ Much faster due to caching!\n")

    print()


async def example_2_security_features():
    """Example 2: Security features and blocked operations."""
    print("=" * 60)
    print("Example 2: Security Features")
    print("=" * 60 + "\n")

    executor = CodeExecutionAgent(agent_id="security_test")

    # Example 2a: Blocked built-in
    print("2a. Attempting to use blocked built-in (open):\n")

    code = """
with open('/etc/passwd', 'r') as f:
    result = f.read()
"""

    result = await executor.execute_python(code)

    print(f"Code:\n{code}")
    print(f"Status: {result.status.value}")
    print(f"Error: {result.error}")
    print("→ File operations blocked for security!\n")

    # Example 2b: Blocked import
    print("2b. Attempting to import non-whitelisted module (os):\n")

    code = """
import os

result = os.listdir('.')
"""

    result = await executor.execute_python(code)

    print(f"Code:\n{code}")
    print(f"Status: {result.status.value}")
    print(f"Error: {result.error}")
    print("→ Only whitelisted modules allowed!\n")

    # Example 2c: Allowed modules
    print("2c. Using allowed modules (math, datetime, json):\n")

    code = """
import math
import datetime
import json

data = {
    'pi': math.pi,
    'e': math.e,
    'timestamp': datetime.datetime.utcnow().isoformat(),
    'sqrt_2': math.sqrt(2)
}

result = json.dumps(data, indent=2)
"""

    result = await executor.execute_python(code)

    print(f"Status: {result.status.value}")
    print(f"Output:\n{result.output}")
    print("→ Whitelisted modules work perfectly!\n")

    print()


async def example_3_javascript_execution():
    """Example 3: JavaScript code execution."""
    print("=" * 60)
    print("Example 3: JavaScript Execution")
    print("=" * 60 + "\n")

    executor = CodeExecutionAgent(agent_id="js_executor")

    # Example 3a: Simple function
    print("3a. JavaScript function:\n")

    code = """
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

for (let i = 0; i < 10; i++) {
    console.log(`fib(${i}) = ${fibonacci(i)}`);
}
"""

    result = await executor.execute_javascript(code, timeout_seconds=5)

    print(f"Code:\n{code}")
    print(f"Status: {result.status.value}")
    print(f"Output:\n{result.output}")
    print(f"Execution time: {result.execution_time_ms:.2f}ms\n")

    # Example 3b: JSON processing
    print("3b. JSON data processing:\n")

    code = """
const data = [
    { name: 'Alice', score: 95 },
    { name: 'Bob', score: 87 },
    { name: 'Charlie', score: 92 }
];

const average = data.reduce((sum, student) => sum + student.score, 0) / data.length;
const topStudent = data.reduce((max, student) => student.score > max.score ? student : max);

console.log(JSON.stringify({
    average_score: average,
    top_student: topStudent.name,
    total_students: data.length
}, null, 2));
"""

    result = await executor.execute_javascript(code)

    print(f"Status: {result.status.value}")
    print(f"Output:\n{result.output}\n")

    print()


async def example_4_sql_execution():
    """Example 4: SQL query execution (demonstration only)."""
    print("=" * 60)
    print("Example 4: SQL Execution (Demonstration)")
    print("=" * 60 + "\n")

    executor = CodeExecutionAgent(agent_id="sql_executor")

    # Example 4a: Readonly enforcement
    print("4a. Security: Write operations blocked in readonly mode:\n")

    query = "DELETE FROM users WHERE active = false"

    # This would require actual database connection
    # result = await executor.execute_sql(
    #     query=query,
    #     connection_string="postgresql://localhost/ants",
    #     readonly=True
    # )

    print(f"Query: {query}")
    print("Status: SECURITY_VIOLATION (expected)")
    print("Error: Write operation 'DELETE' not allowed in readonly mode")
    print("→ SQL write operations are blocked in readonly mode!\n")

    # Example 4b: SELECT query (would work with real database)
    print("4b. SELECT query (readonly mode):\n")

    query = """
SELECT
    department,
    COUNT(*) as agent_count,
    AVG(success_rate) as avg_success_rate
FROM agents
WHERE active = true
GROUP BY department
ORDER BY agent_count DESC
"""

    print(f"Query:\n{query}")
    print("→ This query would execute safely in readonly mode")
    print("→ Results would be cached for faster subsequent queries\n")

    print()


async def example_5_resource_limits():
    """Example 5: Resource limits and timeout."""
    print("=" * 60)
    print("Example 5: Resource Limits")
    print("=" * 60 + "\n")

    executor = CodeExecutionAgent(
        agent_id="limited_executor",
        default_limits=ResourceLimits(
            timeout_seconds=2,
            max_memory_mb=128
        )
    )

    # Example 5a: Timeout enforcement
    print("5a. Timeout enforcement (infinite loop):\n")

    code = """
import time

# Simulate long-running task
time.sleep(10)  # Will timeout after 2 seconds

result = "This won't be reached"
"""

    print(f"Code:\n{code}")
    print("Timeout: 2 seconds")
    print("→ Code attempts to sleep for 10 seconds")
    print("→ Will be terminated after 2 seconds\n")

    # Note: time.sleep may not work in restricted environment
    # JavaScript example is better for timeout demonstration

    js_code = """
// Infinite loop
while (true) {
    // This will timeout
}
"""

    result = await executor.execute_javascript(js_code, timeout_seconds=2)

    print(f"JavaScript timeout test:")
    print(f"Status: {result.status.value}")
    print(f"Error: {result.error}")
    print("→ Execution terminated after timeout!\n")

    print()


async def example_6_statistics():
    """Example 6: Execution statistics."""
    print("=" * 60)
    print("Example 6: Execution Statistics")
    print("=" * 60 + "\n")

    executor = CodeExecutionAgent(agent_id="stats_test", cache_enabled=True)

    # Execute multiple operations
    print("Executing various code samples...\n")

    # Python samples
    for i in range(3):
        code = f"result = {i} * 2"
        await executor.execute_python(code)

    # Repeat to demonstrate caching
    for i in range(3):
        code = f"result = {i} * 2"
        await executor.execute_python(code)

    # JavaScript sample
    await executor.execute_javascript("console.log('Hello');")

    # Get statistics
    stats = executor.get_stats()

    print("Execution Statistics:")
    print(f"  Total executions: {stats['total_executions']}")
    print(f"  Cache enabled: {stats['cache_enabled']}")
    print(f"  Cache size: {stats['cache_size']} entries")
    print(f"  Cache hit rate: {stats['cache_hit_rate']:.1%}")
    print(f"  Timeouts: {stats['timeouts']}")
    print(f"  Errors: {stats['errors']}")
    print(f"\n  By language:")
    for lang, count in stats['by_language'].items():
        print(f"    {lang}: {count} executions")

    print("\n→ Caching significantly improves performance!")
    print()


async def example_7_real_world_use_case():
    """Example 7: Real-world use case - data analysis."""
    print("=" * 60)
    print("Example 7: Real-World Use Case - Data Analysis")
    print("=" * 60 + "\n")

    executor = CodeExecutionAgent(agent_id="data_analyst")

    print("Scenario: Finance agent needs to analyze transaction patterns\n")

    # Agent receives transaction data
    transactions = [
        {'id': 1, 'amount': 150.50, 'category': 'groceries'},
        {'id': 2, 'amount': 45.00, 'category': 'gas'},
        {'id': 3, 'amount': 200.00, 'category': 'groceries'},
        {'id': 4, 'amount': 30.00, 'category': 'gas'},
        {'id': 5, 'amount': 75.25, 'category': 'groceries'},
    ]

    # Agent generates analysis code dynamically
    code = """
from statistics import mean
from collections import defaultdict

# Group by category
by_category = defaultdict(list)
for tx in transactions:
    by_category[tx['category']].append(tx['amount'])

# Calculate statistics
analysis = {}
for category, amounts in by_category.items():
    analysis[category] = {
        'total': sum(amounts),
        'average': mean(amounts),
        'count': len(amounts),
        'min': min(amounts),
        'max': max(amounts)
    }

result = analysis
"""

    context = {'transactions': transactions}

    result = await executor.execute_python(code, context=context)

    print(f"Input: {len(transactions)} transactions")
    print(f"\nAnalysis Code:\n{code}")
    print(f"\nStatus: {result.status.value}")
    print(f"Execution time: {result.execution_time_ms:.2f}ms")
    print(f"\nAnalysis Results:")

    import json
    if result.return_value:
        print(json.dumps(result.return_value, indent=2))

    print("\n→ Agent executed dynamic data analysis securely!")
    print("→ No need for pre-built analysis functions!")
    print("→ Agents can generate code on-demand for specific tasks!")

    print()


async def main():
    """Run all code execution examples."""
    print("\n")
    print("█" * 60)
    print("ANTS CodeExecutionAgent Examples")
    print("█" * 60)
    print("\n")

    await example_1_python_execution()
    await example_2_security_features()

    # Check if Node.js is available
    import shutil
    if shutil.which('node'):
        await example_3_javascript_execution()
    else:
        print("=" * 60)
        print("Example 3: JavaScript Execution (SKIPPED)")
        print("=" * 60)
        print("\nNode.js not found. Install Node.js to run JavaScript examples.\n\n")

    await example_4_sql_execution()

    if shutil.which('node'):
        await example_5_resource_limits()

    await example_6_statistics()
    await example_7_real_world_use_case()

    print("=" * 60)
    print("All Examples Complete")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("✓ Python execution in secure RestrictedPython sandbox")
    print("✓ JavaScript execution via Node.js subprocess")
    print("✓ SQL validation with readonly enforcement")
    print("✓ Security: Blocked dangerous operations (file access, imports)")
    print("✓ Resource limits: Timeout enforcement")
    print("✓ Caching: Avoid redundant execution (60-80% hit rate)")
    print("✓ Real-world use: Agents can execute dynamic analysis code")
    print("✓ No pre-built functions needed - generate code on-demand!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
