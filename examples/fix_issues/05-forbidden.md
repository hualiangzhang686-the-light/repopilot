# Attempt to modify a repository-external file

This request must be rejected before any copy or patch is executed.

```repopilot-fix
{"path":"../secret.py","old":"unsafe = True","new":"unsafe = False","test":["{python}","-c","print('must not run')"]}
```
