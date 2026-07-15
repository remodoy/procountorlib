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
p.login_m2m(api_key="apikey")
# OR
url, expected_state = p.login_oauth_redirect()
# redirect user to redirect url and wait for callback
p.login_oauth_callback(code=code_from_response, state=state_from_response, expected_state=expected_state)

p.get_products()

```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This library is not officially affiliated with Procountor. Use at your own risk.
Always refer to the official Procountor API [documentation](https://dev.procountor.com/api-reference/) for the most accurate and up-to-date information.

