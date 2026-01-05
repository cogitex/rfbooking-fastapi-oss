# Contributing to RFBooking FastAPI OSS

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

Be respectful and constructive. We welcome contributors of all experience levels.

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/otokmakov/rfbooking-fastapi-oss/issues) first
2. Create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, Docker version)

### Suggesting Features

Open an issue with:
- Use case description
- Proposed solution
- Alternatives considered

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests and linting
5. Commit with clear messages
6. Push and create a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/rfbooking-fastapi-oss.git
cd rfbooking-fastapi-oss

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy config
cp config/config.example.yaml config/config.yaml

# Run development server
python -m app.main
```

## Code Style

- **Python**: Follow PEP 8, use Black formatter (line length 100)
- **Imports**: Use isort, group by standard/third-party/local
- **Docstrings**: Google style for public functions
- **Type hints**: Required for function signatures

```bash
# Format code
black --line-length 100 app/
isort app/

# Check style
flake8 app/
```

## Commit Messages

Format: `type: short description`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

Examples:
```
feat: add equipment search filter
fix: resolve booking conflict detection
docs: update API reference
```

## Project Structure

```
app/
├── models/      # SQLAlchemy models
├── routes/      # API endpoints
├── services/    # Business logic
├── middleware/  # Auth, CSRF
└── utils/       # Helpers
```

## Testing

```bash
# Run tests (when available)
pytest

# With coverage
pytest --cov=app
```

## License

By contributing, you agree that your contributions will be licensed under the AGPLv3 license.

## Questions?

Open an issue or contact the maintainer.

---

Copyright (C) 2025 Oleg Tokmakov
