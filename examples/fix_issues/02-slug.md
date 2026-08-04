# Use hyphens in slugify

`slugify("Hello World")` should return `hello-world`, not an underscore-separated value.

```repopilot-fix
{"path":"strings.py","old":"replace(\" \", \"_\")","new":"replace(\" \", \"-\")","test":["{python}","-c","from strings import slugify; assert slugify('Hello World') == 'hello-world'"]}
```
