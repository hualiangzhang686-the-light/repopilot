# Demonstrate a patch whose verification still fails

The patch changes add, but the supplied expected value remains deliberately impossible.

```repopilot-fix
{"path":"math_utils.py","old":"return left - right","new":"return left + right","test":["{python}","-c","from math_utils import add; assert add(2, 3) == 99"]}
```
