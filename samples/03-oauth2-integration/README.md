# OAuth2 Integration

This example demonstrates OAuth2 authentication with GitHub Apps and issue management functionality.

## Features

- GitHub OAuth2 user authentication
- Secure session management
- Protected routes requiring login
- Issue auto-closing functionality
- Web interface for user interaction

## Setup

### 1. GitHub App Configuration

Create a GitHub App with these settings:
- **Homepage URL**: `http://localhost:8000`
- **Webhook URL**: `http://localhost:8000/webhooks/github`
- **Authorization callback URL**: `http://localhost:8000/auth/github/callback`

Required permissions:
- **Issues**: Write (to close issues)
- **Metadata**: Read

Subscribe to events:
- **Issues**

### 2. Environment Setup

Copy and configure the environment file:

```bash
cp .env.example .env
```

Update `.env` with your GitHub App credentials:

```env
GITHUBAPP_ID=your-app-id
GITHUBAPP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
GITHUBAPP_WEBHOOK_SECRET=your-webhook-secret
GITHUBAPP_OAUTH_CLIENT_ID=Iv1.your-oauth-client-id
GITHUBAPP_OAUTH_CLIENT_SECRET=your-oauth-client-secret
GITHUBAPP_OAUTH_SESSION_SECRET=your-session-secret
```

### 3. Run the Application

Choose one of the two examples:

**Full-featured example with web interface:**
```bash
poetry run python app.py
```

**Simple environment-only example:**
```bash
poetry run python simple.py
```

Visit [http://localhost:8000](http://localhost:8000) to access the application.

## Examples

### 1. `app.py` - Full Web Interface

Complete OAuth2 integration with:
- HTML pages for login and dashboard
- Protected routes with authentication
- User profile and session management
- Issue closing with OAuth-aware comments

### 2. `simple.py` - Minimal Implementation

Environment-only configuration showing:
- Basic OAuth2 setup
- Simple webhook handlers
- Issue closing functionality

## Usage

### Web Interface

1. Visit `/` to see the home page
2. Click "Login with GitHub" to authenticate
3. Access protected routes like `/dashboard` and `/profile`
4. Log out using the `/logout` endpoint

### Webhook Events

When issues are opened or reopened in repositories where your app is installed:
- The app automatically closes the issue
- Adds a comment mentioning the authenticated user (in full example)
- Logs the action for monitoring

### Testing OAuth Flow

1. Start the application
2. Navigate to [http://localhost:8000](http://localhost:8000)
3. Click the login button
4. Authorize the app on GitHub
5. Access protected endpoints

## Configuration

Both examples support environment variable configuration with the `GITHUBAPP_` prefix:

- `GITHUBAPP_ID` - Your GitHub App ID
- `GITHUBAPP_PRIVATE_KEY` - Your GitHub App's private key
- `GITHUBAPP_WEBHOOK_SECRET` - Webhook verification secret
- `GITHUBAPP_OAUTH_CLIENT_ID` - OAuth2 client ID
- `GITHUBAPP_OAUTH_CLIENT_SECRET` - OAuth2 client secret
- `GITHUBAPP_OAUTH_SESSION_SECRET` - Session signing secret
- `GITHUBAPP_OAUTH_REDIRECT_URI` - OAuth callback URL
- `GITHUBAPP_OAUTH_SCOPES` - Requested OAuth scopes

## Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/` | GET | Home page | No |
| `/auth/github/login` | GET | Start OAuth flow | No |
| `/auth/github/callback` | GET | OAuth callback | No |
| `/logout` | GET | Logout user | No |
| `/dashboard` | GET | User dashboard | Yes |
| `/profile` | GET | User profile data | Yes |
| `/webhooks/github` | POST | GitHub webhooks | No |
