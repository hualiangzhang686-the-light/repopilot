# Give requests a safe default timeout

`request_timeout()` should return 30 seconds instead of disabling the timeout.

```repopilot-fix
{"path":"config.py","old":"DEFAULT_TIMEOUT_SECONDS = 0","new":"DEFAULT_TIMEOUT_SECONDS = 30","test":["{python}","-c","from config import request_timeout; assert request_timeout() == 30"]}
```
