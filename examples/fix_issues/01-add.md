# Correct add so two integers are summed

`add(2, 3)` should return 5, but the implementation subtracts the right operand.

```repopilot-fix
{"path":"math_utils.py","old":"return left - right","new":"return left + right","test":["{python}","-c","from math_utils import add; assert add(2, 3) == 5"]}
```
