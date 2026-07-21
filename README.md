# Python Procountor Library

A Python library for interacting with the Procountor API.

## Installation

```bash
pip install git+https://github.com/remodoy/procountorlib.git
```

## Usage

```python
p = ProcountorAPIClient(
    redirect_uri="https://myapp.example.com/callback",
    client_id="myclientid",
    client_secret="myclientsecret",
)
# Login using M2M API Key
p.login_m2m(api_key="apikey")

# OR with oauth flow
url, expected_state = p.login_oauth_redirect()
# redirect user to redirect url and wait for callback
p.login_oauth_callback(code=code_from_response, state=state_from_response, expected_state=expected_state)

# OR use existing oauth tokens
p.set_access_token(access_token="your_access_token", refresh_token="your_refresh_token")
p.refresh_access_token_if_needed()

# Execute API Calls
p.get_products()

```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This library is not officially affiliated with Procountor. Use at your own risk.
Always refer to the official Procountor API [documentation](https://dev.procountor.com/api-reference/) for the most accurate and up-to-date information.

