TEST_FAILURE
- Cause: failing pytest assertion
- Example: assert add(2, 3) == 6

INVALID_COMMAND
- Cause: invalid command in buildspec.yml
- Example: fake_command_123

DEPENDENCY_ERROR
- Cause: invalid package in requirements.txt
- Example: nieistniejaca-paczka-xyz123

PYTHON_IMPORT_ERROR
- Cause: missing Python module
- Example: python -c "import missing_module"

IAM_ERROR
- Cause: missing AWS permission
- Example: aws s3 ls without proper permissions