# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.5] - 2025-09-12

### Added
- OAuth2 user authentication with JWT session management
- Automatic rate limiting with exponential backoff and retry logic
- Sample structure with learning progression (01-04)
- Environment variable support for all OAuth2 configuration
- Rate limit monitoring endpoints and error handling

### Changed
- Migrated from requests to httpx for async HTTP operations
- Restructured samples into numbered progression
- Updated README with detailed OAuth2 and rate limiting documentation
- Consistent issue auto-closing across all samples

### Removed
- Deprecated cruel_closer and oauth2_example samples

### Breaking Changes
- OAuth2 routes now require oauth_session_secret parameter
- Rate limiting parameters added to GitHubApp constructor

## [0.2.0] - 2025-09-11

### Added
- OAuth2 integration with GitHub Apps for user authentication
- HTTP client migration to httpx from requests

### Changed
- Improved async support for HTTP operations

## [0.1.3] - 2025-07-02

### Added
- Async function support for event hook calls

### Changed
- Updated version in pyproject.toml
- Enhanced async event handling capabilities

## [0.1.2] - 2025-05-29

### Fixed
- Broken tests in CI pipeline
- Inaccuracies in README documentation
- References to pipenv in README (updated to poetry)
- CI configuration to not fail on single version failure

### Changed
- Updated CI configuration
- Improved test reliability

## [0.1.1] - 2025-05-29

### Changed
- Version increment for release consistency

## [0.1.0] - 2025-05-29

### Added
- Initial release of FastAPI-GitHubApp
- Basic GitHub App webhook handling
- FastAPI integration
- GitHub API client support
- Event-based hook system with `@on` decorator
- Installation token management
- Webhook payload verification

### Infrastructure
- Initial CI/CD pipeline setup
- PyPI publishing workflow
- Poetry-based dependency management
