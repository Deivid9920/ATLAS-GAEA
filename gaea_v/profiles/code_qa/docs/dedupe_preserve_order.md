# code_qa ref: dedupe_preserve_order

Q: How do you remove duplicates keeping first occurrences?

```python
def dedupe(xs):
    return list(dict.fromkeys(xs))
```
