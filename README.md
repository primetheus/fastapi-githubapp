# FastAPI-GithubApp

FastAPI extension for rapid Github app development in Python, in the spirit of [probot](https://probot.github.io/)

GitHub Apps help automate GitHub workflows. Examples include preventing merging of pull requests with "WIP" in the title or closing stale issues and pull requests.

## Getting Started

### Create GitHub App

Follow GitHub's docs on [creating a github app](https://developer.github.com/apps/building-github-apps/creating-a-github-app/).

> You can, in principle, register any type of payload to be sent to the app!

Once you do this, please note down the GitHub app Id, the GitHub app secret, and make sure to [create a private key](https://docs.github.com/en/developers/apps/authenticating-with-github-apps#generating-a-private-key) for it! These three elements are **required** to run your app.

#### Build the FastAPI App

The GithubApp package has a decorator, `@on`, that will allow you to register events, and actions, to specific functions.
For instance,

```python
@github_app.on('issues.opened')
def cruel_closer():
    #do stuff here
```

Will trigger whenever the app receives a Github payload with the `X-Github-Event` header set to `issues`, and an `action` field in the payload field containing `opened`

Following this logic, you can make your app react in a unique way for every combination of event and action. Refer to the Github documentation for all the details about events and the actions they support, as well as for sample payloads for each.
You can also have something like

```python
@github_app.on('issues')
def issue_tracker():
    #do stuff here
```

The above function will do `stuff here` for _every_ `issues` event received. This can be useful for specific workflows, to bring developers in early.

Inside the function, you can access the received request via the conveniently named `request` variable. You can access its payload by simply getting it: `request.payload`

You can find a complete example (containing this cruel_closer function), in the samples folder of this repo. It is a fully functioning FastAPI Github App.

#### Run it locally

For quick iteration, you can set up your environment as follows:

```bash
EXPORT GITHUBAPP_WEBHOOK_SECRET=False # this will circumvent request verification
```

This will make your FastAPI application run in debug mode. This means that, as you try sending payloads and tweak functions, fix issues, etc., as soon as you save the python code, the FastAPI application will reload itself and run the new code immediately.
Once that is in place, run your github app

```bash
pipenv run uvicorn app:app --host=0.0.0.0 --port=5005 --reload
```

Now, you can send requests! The port is 5005 by default but that can also be overridden. Check `pipenv run uvicorn app:app --help` for more details. Anyway! Now, on to sending test payloads!

```bash
curl -H "X-GitHub-Event: <your_event>" -H "Content-Type: application/json" -X POST -d @./path/to/payload.json http://localhost:5005
```

#### Install your GitHub App

**Settings** > **Applications** > **Configure**

> If you were to install the cruel closer app, any repositories that you give the GitHub app access to will cruelly close all new issues, be careful.

#### Deploy your GitHub App

Bear in mind that you will need to run the app _somewhere_. It is possible, and fairly easy, to host the app in something like Kubernetes, or simply containerised, in a machine somewhere. You will need to be careful to expose the FastAPI app port to the outside world so the app can receive the payloads from Github. The deployed FastAPI app will need to be reachable from the same URL you set as the `webhook url`. However, this is getting a little bit into Docker/Kubernetes territory so we will not go too deep.

## Usage

### `GitHubApp` Instance Attributes

`payload`: In the context of a hook request, a Python dict representing the hook payload (raises a `RuntimeError`
outside a hook context).

`installation_token`: The token used to authenticate as the app installation. This can be used to call api's not supported by `GhApi` like [Github's GraphQL API](https://docs.github.com/en/graphql/reference)

### `GithubApp` Instance Methods

`client`: a [GhApi](https://ghapi.fast.ai/) client authenticated as the app installation (raises a `RuntimeError` inside a hook context without a valid request)

## Configuration

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GITHUBAPP_ID` | :white_check_mark: | `None` | GitHub App ID as an integer |
| `GITHUBAPP_PRIVATE_KEY` | :white_check_mark: | `None` | Private key used to sign access token requests as bytes or utf-8 encoded string |
| `GITHUBAPP_WEBHOOK_SECRET` | :white_check_mark: | `False` | Secret used to secure webhooks as bytes or utf-8 encoded string. Set to `False` to disable verification. |
| `GITHUBAPP_WEBHOOK_PATH` | | `/webhooks/github/` | Path used for GitHub hook requests as a string. |
| `GITHUBAPP_URL` | | `None` | URL of GitHub instance (used for GitHub Enterprise Server) as a string |

You can find an example on how to init all these config variables in the [cruel_closer sample app](./samples/cruel_closer)

#### Cruel Closer

The cruel-closer sample app will use information of the received payload (which is received every time an issue is opened), will find said issue and **close it** without regard.

### Inspiration
This was inspired by the following projects:
- https://github.com/ffalor/flask-githubapplication
- https://github.com/bradshjg/flask-githubapp
- https://github.com/probot/probot
